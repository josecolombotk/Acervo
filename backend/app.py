import logging, os, secrets, time
from contextlib import contextmanager
from datetime import date, timedelta
from decimal import Decimal
from functools import wraps
import pymysql
from flask import Flask, jsonify, request, session
from werkzeug.exceptions import HTTPException
from werkzeug.security import check_password_hash, generate_password_hash
import logic
from dotenv import load_dotenv
load_dotenv()

PROD = os.getenv("ACERVO_ENV", "development") == "production"
MAX_INTENTOS, BLOQUEO = 5, 300           # 5 fallos de login -> bloqueo de 5 minutos (por IP + usuario)
FALLOS = {}
DUMMY_HASH = generate_password_hash("no-es-una-clave")   # iguala el tiempo de respuesta si el usuario no existe

class Bad(Exception):
    def __init__(self, msg, code=400):
        super().__init__(msg); self.msg, self.code = msg, code

def conn():
    return pymysql.connect(host=os.getenv("DB_HOST", "localhost"), port=int(os.getenv("DB_PORT", 3306)),
        user=os.getenv("DB_USER", "root"), password=os.getenv("DB_PASS", ""), database=os.getenv("DB_NAME", "acervo"),
        charset="utf8mb4", connect_timeout=5, cursorclass=pymysql.cursors.DictCursor)

def _cv(v):
    if hasattr(v, "isoformat"): return v.isoformat()
    return int(v) if isinstance(v, Decimal) else v

def run(sql, args=(), one=False, write=False):
    c = conn()
    try:
        with c.cursor() as cur:
            cur.execute(sql, args)
            if write:
                c.commit(); return cur.lastrowid
            rows = [{k: _cv(v) for k, v in r.items()} for r in cur.fetchall()]
        return (rows[0] if rows else None) if one else rows
    finally:
        c.close()

@contextmanager
def tx():
    """Transacción: confirma al salir bien y deshace todo si hay un error (o un Bad)."""
    c = conn()
    try:
        yield c.cursor(); c.commit()
    except Exception:
        c.rollback(); raise
    finally:
        c.close()

def S(d, k):
    v = d.get(k)
    return v.strip() if isinstance(v, str) and v.strip() else None

def check(errs):
    if errs: raise Bad("; ".join(errs))

def body():
    d = request.get_json(silent=True)
    if not isinstance(d, dict): raise Bad("El cuerpo de la solicitud debe ser un JSON válido")
    return d

def _audit_logger():
    lg = logging.getLogger("acervo.audit")
    if not lg.handlers:
        h = logging.FileHandler(os.path.join(os.path.dirname(os.path.abspath(__file__)), "audit.log"), encoding="utf8")
        h.setFormatter(logging.Formatter("%(asctime)s %(message)s")); lg.addHandler(h); lg.setLevel(logging.INFO)
    return lg

def create_app():
    app = Flask(__name__)
    key = os.getenv("SECRET_KEY")
    if not key:
        if PROD: raise RuntimeError("Defina la variable de entorno SECRET_KEY (clave aleatoria de 32 bytes o más).")
        key = secrets.token_hex(32)
        print("AVISO: SECRET_KEY no definida; se usa una clave temporal (las sesiones se pierden al reiniciar).")
    if PROD and os.getenv("DB_USER", "root") == "root":
        raise RuntimeError("En producción no se permite DB_USER=root: use un usuario con permisos mínimos.")
    app.config.update(SECRET_KEY=key, SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=PROD or os.getenv("ACERVO_HTTPS") == "1", PERMANENT_SESSION_LIFETIME=timedelta(hours=8),
        MAX_CONTENT_LENGTH=64 * 1024)
    alog = _audit_logger()
    audit = lambda m: alog.info("uid=%s rol=%s ip=%s %s", session.get("uid"), session.get("rol"), request.remote_addr, m)
    err = lambda m, c=400: (jsonify(error=m), c)
    B = ("Bibliotecaria",)

    
    @app.before_request
    def _csrf():  # una cabecera personalizada obliga al navegador a hacer preflight CORS: bloquea CSRF entre sitios
        if request.method in ("POST", "PUT", "PATCH", "DELETE") and request.headers.get("X-Requested-With") != "acervo":
            return err("Solicitud no permitida", 403)

    @app.after_request
    def _headers(r):
        r.headers.update({"X-Content-Type-Options": "nosniff", "X-Frame-Options": "DENY", "Referrer-Policy": "no-referrer",
            "Content-Security-Policy": "default-src 'none'; frame-ancestors 'none'", "Cache-Control": "no-store", "Server": "Acervo"})
        return r

    @app.errorhandler(Bad)
    def _bad(e): return err(e.msg, e.code)
    @app.errorhandler(pymysql.IntegrityError)
    def _dup(e): return err("Registro duplicado (DNI, nº de afiliado o código ya existente) o referencia inválida", 409)
    @app.errorhandler(pymysql.OperationalError)
    def _conn(e): return err("No se pudo conectar con la base de datos. Verifique que MySQL de XAMPP esté iniciado", 503)
    @app.errorhandler(pymysql.MySQLError)
    def _db(e):
        app.logger.exception(e); return err("Error en la base de datos", 500)
    @app.errorhandler(Exception)
    def _any(e):
        if isinstance(e, HTTPException): return err(e.description, e.code)
        app.logger.exception(e); return err("Error interno del servidor", 500)   # sin trazas hacia el cliente

    def auth(*roles):
        def deco(f):
            @wraps(f)
            def w(*a, **k):
                if "uid" not in session: return err("Debe iniciar sesión", 401)
                if roles and session["rol"] not in roles: return err("No tiene permiso para esta acción", 403)
                return f(*a, **k)
            return w
        return deco

    def mark():
        run("UPDATE prestamos SET estado='Vencido' WHERE estado='Activo' AND fecha_vencimiento<CURDATE()", write=True)

    def upd(table, idc, i, d):
        if d: run(f"UPDATE {table} SET {','.join(c+'=%s' for c in d)} WHERE {idc}=%s", [*d.values(), i], write=True)

    #  Autenticación (CU01) 
    @app.post("/api/login")
    def login():
        d = body()
        user, pw = str(d.get("username", ""))[:50], str(d.get("password", ""))[:200]
        k, ahora = f"{request.remote_addr}|{user.lower()}", time.time()
        if len(FALLOS) > 5000: FALLOS.clear()
        f = FALLOS.get(k, [0, 0])
        if f[1] > ahora: raise Bad(f"Demasiados intentos fallidos. Intente nuevamente en {int((f[1] - ahora) // 60) + 1} minuto(s)", 429)
        u = run("SELECT * FROM usuarios WHERE username=%s", (user,), one=True)
        ok = check_password_hash(u["password_hash"] if u else DUMMY_HASH, pw) and u is not None
        if not ok:
            f[0] += 1
            FALLOS[k] = [0, ahora + BLOQUEO] if f[0] >= MAX_INTENTOS else f
            audit(f"login fallido usuario={user!r}")
            raise Bad("Usuario o contraseña incorrectos", 401)
        FALLOS.pop(k, None); session.clear(); session.permanent = True
        session.update(uid=u["id_usuario"], rol=u["rol"], nombre=u["nombre"]); audit("login correcto")
        return jsonify(nombre=u["nombre"], rol=u["rol"])

    @app.post("/api/logout")
    def logout():
        audit("logout"); session.clear(); return jsonify(ok=True)

    @app.get("/api/me")
    @auth()
    def me(): return jsonify(nombre=session["nombre"], rol=session["rol"])

    #  Dashboard (CU10) 
    def vencidos(lim=500, tel=False):
        t = "s.telefono," if tel else ""
        return run(f"""SELECT p.id_prestamo, CONCAT(s.nombre,' ',s.apellido) socio, {t} l.titulo, e.codigo_inventario,
            p.fecha_vencimiento, DATEDIFF(CURDATE(),p.fecha_vencimiento) dias_atraso,
            (SELECT COUNT(*) FROM avisos_vencimiento a WHERE a.id_prestamo=p.id_prestamo) avisado
            FROM prestamos p JOIN socios s ON s.id_socio=p.id_socio JOIN ejemplares e ON e.id_ejemplar=p.id_ejemplar
            JOIN libros l ON l.id_libro=e.id_libro WHERE p.estado='Vencido' ORDER BY dias_atraso DESC LIMIT %s""", (lim,))

    @app.get("/api/dashboard")
    @auth()
    def dashboard():
        mark()
        n = lambda s: run(s, one=True)["n"]
        return jsonify(
            disponibles=n("SELECT COUNT(*) n FROM ejemplares WHERE estado_disponibilidad='Disponible'"),
            prestados=n("SELECT COUNT(*) n FROM ejemplares WHERE estado_disponibilidad='Prestado'"),
            activos=n("SELECT COUNT(*) n FROM prestamos WHERE estado IN ('Activo','Vencido')"),
            vencidos=n("SELECT COUNT(*) n FROM prestamos WHERE estado='Vencido'"),
            socios=n("SELECT COUNT(*) n FROM socios WHERE estado='Habilitado'"),
            vencidos_lista=vencidos(5))

    #  Catálogo (CU02, CU03, CU04)
    @app.get("/api/libros")
    @auth()
    def libros_get():
        q = f"%{request.args.get('q', '')[:100]}%"
        return jsonify(run("""SELECT l.*, COUNT(e.id_ejemplar) ejemplares, IFNULL(SUM(e.estado_disponibilidad='Disponible'),0) disponibles
            FROM libros l LEFT JOIN ejemplares e ON e.id_libro=l.id_libro AND e.estado_disponibilidad<>'Inactivo'
            WHERE l.activo=1 AND (l.titulo LIKE %s OR l.autor LIKE %s OR l.categoria LIKE %s)
            GROUP BY l.id_libro ORDER BY l.titulo LIMIT 500""", (q, q, q)))

    @app.post("/api/libros")
    @auth(*B)
    def libros_post():
        d = body(); check(logic.validar_libro(d))
        n, e = logic.validar_cantidad(d.get("cantidad")); check(e)
        with tx() as cur:   # libro + todos sus ejemplares en una sola transacción
            cur.execute("INSERT INTO libros(isbn,titulo,autor,editorial,categoria,ubicacion_fisica) VALUES(%s,%s,%s,%s,%s,%s)",
                        (S(d, "isbn"), S(d, "titulo"), S(d, "autor"), S(d, "editorial"), S(d, "categoria"), S(d, "ubicacion_fisica")))
            i = cur.lastrowid
            if n: cur.executemany("INSERT INTO ejemplares(id_libro,codigo_inventario) VALUES(%s,%s)", [(i, f"L{i:04d}-{k}") for k in range(1, n + 1)])
        audit(f"alta libro id={i} ejemplares={n}")
        return jsonify(id_libro=i), 201

    @app.put("/api/libros/<int:i>")
    @auth(*B)
    def libros_put(i):
        d = body(); check(logic.validar_libro(d, parcial=True))
        upd("libros", "id_libro", i, {k: S(d, k) for k in ("isbn", "titulo", "autor", "editorial", "categoria", "ubicacion_fisica") if k in d})
        audit(f"edición libro id={i}"); return jsonify(ok=True)

    @app.delete("/api/libros/<int:i>")  # baja lógica
    @auth(*B)
    def libros_del(i):
        with tx() as cur:
            cur.execute("SELECT id_libro FROM libros WHERE id_libro=%s", (i,))
            if not cur.fetchone(): raise Bad("Libro inexistente", 404)
            cur.execute("SELECT COUNT(*) n FROM ejemplares WHERE id_libro=%s AND estado_disponibilidad='Prestado' FOR UPDATE", (i,))
            if cur.fetchone()["n"]: raise Bad("No se puede dar de baja: tiene ejemplares prestados", 409)
            cur.execute("UPDATE ejemplares SET estado_disponibilidad='Inactivo' WHERE id_libro=%s", (i,))
            cur.execute("UPDATE libros SET activo=0 WHERE id_libro=%s", (i,))
        audit(f"baja libro id={i}"); return jsonify(ok=True)

    @app.get("/api/libros/<int:i>/ejemplares")
    @auth()
    def ej_get(i): return jsonify(run("SELECT * FROM ejemplares WHERE id_libro=%s", (i,)))

    @app.post("/api/libros/<int:i>/ejemplares")
    @auth(*B)
    def ej_post(i):
        cod = body().get("codigo_inventario"); check(logic.validar_codigo(cod))
        new = run("INSERT INTO ejemplares(id_libro,codigo_inventario) VALUES(%s,%s)", (i, cod.strip()), write=True)
        audit(f"alta ejemplar id={new} libro={i}"); return jsonify(id_ejemplar=new), 201

    @app.delete("/api/ejemplares/<int:i>")  # baja lógica
    @auth(*B)
    def ej_del(i):
        with tx() as cur:
            cur.execute("UPDATE ejemplares SET estado_disponibilidad='Inactivo' WHERE id_ejemplar=%s AND estado_disponibilidad='Disponible'", (i,))
            if cur.rowcount == 0:
                cur.execute("SELECT estado_disponibilidad e FROM ejemplares WHERE id_ejemplar=%s", (i,)); r = cur.fetchone()
                if not r: raise Bad("Ejemplar inexistente", 404)
                raise Bad(f"Solo se puede dar de baja un ejemplar disponible (estado actual: {r['e']})", 409)
        audit(f"baja ejemplar id={i}"); return jsonify(ok=True)

    # Socios (CU07) 
    @app.get("/api/socios")
    @auth()
    def socios_get():  # el Colaborador no recibe teléfono ni email (minimización de datos personales)
        cols = "s.*" if session["rol"] in B else "s.id_socio,s.dni,s.nombre,s.apellido,s.tipo_socio,s.nro_afiliado,s.estado"
        q = f"%{request.args.get('q', '')[:100]}%"
        return jsonify(run(f"""SELECT {cols}, (SELECT COUNT(*) FROM prestamos p WHERE p.id_socio=s.id_socio AND p.estado IN ('Activo','Vencido')) prestamos_activos
            FROM socios s WHERE s.dni LIKE %s OR s.nro_afiliado LIKE %s OR s.nombre LIKE %s OR s.apellido LIKE %s
            ORDER BY s.apellido LIMIT 200""", (q, q, q, q)))

    @app.post("/api/socios")
    @auth(*B)
    def socios_post():
        d = body(); check(logic.validar_socio(d))
        i = run("INSERT INTO socios(dni,nombre,apellido,telefono,email,tipo_socio,nro_afiliado) VALUES(%s,%s,%s,%s,%s,%s,%s)",
                (S(d, "dni"), S(d, "nombre"), S(d, "apellido"), S(d, "telefono"), S(d, "email"), d["tipo_socio"], S(d, "nro_afiliado")), write=True)
        audit(f"alta socio id={i}"); return jsonify(id_socio=i), 201

    @app.put("/api/socios/<int:i>")
    @auth(*B)
    def socios_put(i):
        d = body()
        actual = run("SELECT * FROM socios WHERE id_socio=%s", (i,), one=True)
        if not actual: raise Bad("Socio inexistente", 404)
        check(logic.validar_socio({**actual, **d}))
        upd("socios", "id_socio", i, {k: (d[k] if k in ("tipo_socio", "estado") else S(d, k))
            for k in ("dni", "nombre", "apellido", "telefono", "email", "tipo_socio", "nro_afiliado", "estado") if k in d})
        audit(f"edición socio id={i}"); return jsonify(ok=True)

    @app.delete("/api/socios/<int:i>")  # baja lógica = Inhabilitado
    @auth(*B)
    def socios_del(i):
        with tx() as cur:
            cur.execute("SELECT id_socio FROM socios WHERE id_socio=%s FOR UPDATE", (i,))   # bloquea al socio: evita préstamos simultáneos
            if not cur.fetchone(): raise Bad("Socio inexistente", 404)
            cur.execute("SELECT COUNT(*) n FROM prestamos WHERE id_socio=%s AND estado IN ('Activo','Vencido')", (i,))
            if cur.fetchone()["n"]: raise Bad("No se puede dar de baja: el socio tiene préstamos sin devolver", 409)
            cur.execute("UPDATE socios SET estado='Inhabilitado' WHERE id_socio=%s", (i,))
        audit(f"baja socio id={i}"); return jsonify(ok=True)

    @app.get("/api/socios/<int:i>/prestamos")
    @auth()
    def socio_hist(i):
        return jsonify(run("""SELECT p.*, l.titulo FROM prestamos p JOIN ejemplares e ON e.id_ejemplar=p.id_ejemplar
            JOIN libros l ON l.id_libro=e.id_libro WHERE p.id_socio=%s ORDER BY p.fecha_salida DESC""", (i,)))

    # Préstamos, devoluciones y avisos (CU05, CU06, CU08, CU09)
    @app.get("/api/prestamos")
    @auth()
    def prestamos_get():
        mark(); est = request.args.get("estado")
        if est not in (None, "Activo", "Vencido", "Devuelto"): raise Bad("Estado de préstamo inválido")
        return jsonify(run("""SELECT p.*, CONCAT(s.nombre,' ',s.apellido) socio, l.titulo, e.codigo_inventario,
            IF(p.estado='Vencido',DATEDIFF(CURDATE(),p.fecha_vencimiento),0) dias_atraso
            FROM prestamos p JOIN socios s ON s.id_socio=p.id_socio JOIN ejemplares e ON e.id_ejemplar=p.id_ejemplar
            JOIN libros l ON l.id_libro=e.id_libro WHERE (%s IS NULL OR p.estado=%s) ORDER BY p.fecha_vencimiento LIMIT 1000""", (est, est)))

    @app.post("/api/prestamos")
    @auth()
    def prestar():
        d = body()
        dni, cod = str(d.get("dni", "")).strip()[:15], str(d.get("codigo_inventario", "")).strip()[:50]
        if not dni or not cod: raise Bad("El DNI del socio y el código del ejemplar son obligatorios")
        mark(); hoy = date.today()
        with tx() as cur:   # filas bloqueadas (FOR UPDATE): dos pedidos simultáneos por el mismo ejemplar se serializan
            cur.execute("SELECT * FROM socios WHERE dni=%s FOR UPDATE", (dni,)); s = cur.fetchone()
            if not s: raise Bad("No existe un socio con ese DNI", 404)
            cur.execute("SELECT * FROM ejemplares WHERE codigo_inventario=%s FOR UPDATE", (cod,)); e = cur.fetchone()
            if not e: raise Bad("No existe un ejemplar con ese código", 404)
            cur.execute("SELECT COUNT(*) n FROM prestamos WHERE id_socio=%s AND estado='Vencido'", (s["id_socio"],))
            ok, msg = logic.puede_prestar(s["estado"], cur.fetchone()["n"] > 0, e["estado_disponibilidad"])
            if not ok: raise Bad(msg, 409)
            cur.execute("UPDATE ejemplares SET estado_disponibilidad='Prestado' WHERE id_ejemplar=%s AND estado_disponibilidad='Disponible'", (e["id_ejemplar"],))
            if cur.rowcount != 1: raise Bad("El ejemplar ya no está disponible", 409)
            cur.execute("INSERT INTO prestamos(id_socio,id_ejemplar,id_usuario,fecha_salida,fecha_vencimiento) VALUES(%s,%s,%s,%s,%s)",
                        (s["id_socio"], e["id_ejemplar"], session["uid"], hoy, logic.calcular_vencimiento(hoy)))
            pid = cur.lastrowid
        audit(f"préstamo id={pid} socio={s['id_socio']} ejemplar={e['id_ejemplar']}")
        return jsonify(id_prestamo=pid, fecha_vencimiento=logic.calcular_vencimiento(hoy).isoformat()), 201

    @app.post("/api/prestamos/<int:i>/devolucion")
    @auth()
    def devolver(i):
        with tx() as cur:
            cur.execute("SELECT * FROM prestamos WHERE id_prestamo=%s FOR UPDATE", (i,)); p = cur.fetchone()
            if not p: raise Bad("Préstamo inexistente", 404)
            if p["estado"] == "Devuelto": raise Bad("El préstamo ya fue devuelto", 409)
            cur.execute("UPDATE prestamos SET estado='Devuelto', fecha_devolucion=CURDATE() WHERE id_prestamo=%s", (i,))
            cur.execute("UPDATE ejemplares SET estado_disponibilidad='Disponible' WHERE id_ejemplar=%s", (p["id_ejemplar"],))
        audit(f"devolución préstamo id={i}"); return jsonify(ok=True)

    @app.get("/api/vencidos")
    @auth()
    def vencidos_get():
        mark(); return jsonify(vencidos())

    @app.post("/api/prestamos/<int:i>/aviso")
    @auth(*B)
    def aviso(i):
        mark()
        v = next((x for x in vencidos(tel=True) if x["id_prestamo"] == i), None)
        if not v: raise Bad("El préstamo no está vencido", 409)
        run("INSERT IGNORE INTO avisos_vencimiento(id_prestamo,fecha_emision,medio_notificacion) VALUES(%s,NOW(),'Plantilla')", (i,), write=True)
        audit(f"aviso préstamo id={i}")
        return jsonify(texto=logic.texto_aviso(v["socio"], v["telefono"], v["titulo"], v["fecha_vencimiento"], v["dias_atraso"]))

    return app

if __name__ == "__main__":
    # debug solo si se pide explícitamente (ACERVO_DEBUG=1) y siempre escuchando únicamente en localhost
    create_app().run(host="127.0.0.1", port=5000, debug=os.getenv("ACERVO_DEBUG") == "1")
