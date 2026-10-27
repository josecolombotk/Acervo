import os
from datetime import date
from decimal import Decimal
from functools import wraps
import pymysql
from flask import Flask, jsonify, request, session
from werkzeug.security import check_password_hash
import logic

def conn():
    return pymysql.connect(host=os.getenv("DB_HOST", "localhost"), port=int(os.getenv("DB_PORT", 3306)),
        user=os.getenv("DB_USER", "root"), password=os.getenv("DB_PASS", ""),
        database=os.getenv("DB_NAME", "acervo"), charset="utf8mb4", cursorclass=pymysql.cursors.DictCursor)

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

def create_app():
    app = Flask(__name__)
    app.secret_key = os.getenv("SECRET_KEY", "acervo-dev-key")
    err = lambda m, c=400: (jsonify(error=m), c)
    B = ("Bibliotecaria",)

    def auth(*roles):
        def deco(f):
            @wraps(f)
            def w(*a, **k):
                if "uid" not in session: return err("Debe iniciar sesión", 401)
                if roles and session["rol"] not in roles: return err("No tiene permiso para esta acción", 403)
                return f(*a, **k)
            return w
        return deco

    @app.errorhandler(pymysql.IntegrityError)
    def _dup(e): return err("Registro duplicado (DNI, nº de afiliado o código ya existente) o referencia inválida", 409)
    @app.errorhandler(pymysql.MySQLError)
    def _db(e): return err("Error de conexión con la base de datos. Verifique que MySQL de XAMPP esté iniciado", 503)

    def mark():
        run("UPDATE prestamos SET estado='Vencido' WHERE estado='Activo' AND fecha_vencimiento<CURDATE()", write=True)

    def upd(table, idc, i, d, fields):
        sets = [f for f in fields if f in d]
        if sets: run(f"UPDATE {table} SET {','.join(f+'=%s' for f in sets)} WHERE {idc}=%s", [d[f] for f in sets] + [i], write=True)

    # Autenticación (CU01)
    @app.post("/api/login")
    def login():
        d = request.get_json() or {}
        u = run("SELECT * FROM usuarios WHERE username=%s", (d.get("username", ""),), one=True)
        if not u or not check_password_hash(u["password_hash"], d.get("password", "")):
            return err("Usuario o contraseña incorrectos", 401)
        session.update(uid=u["id_usuario"], rol=u["rol"], nombre=u["nombre"])
        return jsonify(nombre=u["nombre"], rol=u["rol"])

    @app.post("/api/logout")
    def logout():
        session.clear(); return jsonify(ok=True)

    @app.get("/api/me")
    @auth()
    def me(): return jsonify(nombre=session["nombre"], rol=session["rol"])

    # Dashboard (CU10)
    def vencidos(lim=500):
        return run("""SELECT p.id_prestamo, CONCAT(s.nombre,' ',s.apellido) socio, s.telefono, l.titulo, e.codigo_inventario,
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

    # Catálogo (CU02, CU03, CU04)
    @app.get("/api/libros")
    @auth()
    def libros_get():
        q = f"%{request.args.get('q', '')}%"
        return jsonify(run("""SELECT l.*, COUNT(e.id_ejemplar) ejemplares, IFNULL(SUM(e.estado_disponibilidad='Disponible'),0) disponibles
            FROM libros l LEFT JOIN ejemplares e ON e.id_libro=l.id_libro AND e.estado_disponibilidad<>'Inactivo'
            WHERE l.activo=1 AND (l.titulo LIKE %s OR l.autor LIKE %s OR l.categoria LIKE %s)
            GROUP BY l.id_libro ORDER BY l.titulo""", (q, q, q)))

    @app.post("/api/libros")
    @auth(*B)
    def libros_post():
        d = request.get_json() or {}
        falta = [c for c in ("titulo", "autor", "categoria", "ubicacion_fisica") if not str(d.get(c) or "").strip()]
        if falta: return err("Campos obligatorios: " + ", ".join(falta))
        i = run("INSERT INTO libros(isbn,titulo,autor,editorial,categoria,ubicacion_fisica) VALUES(%s,%s,%s,%s,%s,%s)",
                (d.get("isbn") or None, d["titulo"].strip(), d["autor"].strip(), d.get("editorial"), d["categoria"], d["ubicacion_fisica"]), write=True)
        for k in range(1, int(d.get("cantidad", 0) or 0) + 1):
            run("INSERT INTO ejemplares(id_libro,codigo_inventario) VALUES(%s,%s)", (i, f"L{i:04d}-{k}"), write=True)
        return jsonify(id_libro=i), 201

    @app.put("/api/libros/<int:i>")
    @auth(*B)
    def libros_put(i):
        d = request.get_json() or {}
        if "titulo" in d and not str(d["titulo"]).strip(): return err("El título no puede estar vacío")
        upd("libros", "id_libro", i, d, ["isbn", "titulo", "autor", "editorial", "categoria", "ubicacion_fisica"])
        return jsonify(ok=True)

    @app.delete("/api/libros/<int:i>")  # baja lógica
    @auth(*B)
    def libros_del(i):
        if run("SELECT COUNT(*) n FROM ejemplares WHERE id_libro=%s AND estado_disponibilidad='Prestado'", (i,), one=True)["n"]:
            return err("No se puede dar de baja: tiene ejemplares prestados", 409)
        run("UPDATE ejemplares SET estado_disponibilidad='Inactivo' WHERE id_libro=%s", (i,), write=True)
        run("UPDATE libros SET activo=0 WHERE id_libro=%s", (i,), write=True)
        return jsonify(ok=True)

    @app.get("/api/libros/<int:i>/ejemplares")
    @auth()
    def ej_get(i): return jsonify(run("SELECT * FROM ejemplares WHERE id_libro=%s", (i,)))

    @app.post("/api/libros/<int:i>/ejemplares")
    @auth(*B)
    def ej_post(i):
        cod = str((request.get_json() or {}).get("codigo_inventario", "")).strip()
        if not cod: return err("El código de inventario es obligatorio")
        return jsonify(id_ejemplar=run("INSERT INTO ejemplares(id_libro,codigo_inventario) VALUES(%s,%s)", (i, cod), write=True)), 201

    @app.delete("/api/ejemplares/<int:i>")  # baja lógica
    @auth(*B)
    def ej_del(i):
        e = run("SELECT * FROM ejemplares WHERE id_ejemplar=%s", (i,), one=True)
        if not e: return err("Ejemplar inexistente", 404)
        if e["estado_disponibilidad"] == "Prestado": return err("No se puede dar de baja un ejemplar prestado", 409)
        run("UPDATE ejemplares SET estado_disponibilidad='Inactivo' WHERE id_ejemplar=%s", (i,), write=True)
        return jsonify(ok=True)

    # Socios (CU07) 
    @app.get("/api/socios")
    @auth()
    def socios_get():
        q = f"%{request.args.get('q', '')}%"
        return jsonify(run("""SELECT s.*, (SELECT COUNT(*) FROM prestamos p WHERE p.id_socio=s.id_socio AND p.estado IN ('Activo','Vencido')) prestamos_activos
            FROM socios s WHERE s.dni LIKE %s OR s.nro_afiliado LIKE %s OR s.nombre LIKE %s OR s.apellido LIKE %s ORDER BY s.apellido""", (q, q, q, q)))

    @app.post("/api/socios")
    @auth(*B)
    def socios_post():
        d = request.get_json() or {}
        e = logic.validar_socio(d)
        if e: return err("; ".join(e))
        i = run("INSERT INTO socios(dni,nombre,apellido,telefono,email,tipo_socio,nro_afiliado) VALUES(%s,%s,%s,%s,%s,%s,%s)",
                (d["dni"].strip(), d["nombre"].strip(), d["apellido"].strip(), d.get("telefono"), d.get("email"),
                 d["tipo_socio"], (d.get("nro_afiliado") or "").strip() or None), write=True)
        return jsonify(id_socio=i), 201

    @app.put("/api/socios/<int:i>")
    @auth(*B)
    def socios_put(i):
        d = request.get_json() or {}
        actual = run("SELECT * FROM socios WHERE id_socio=%s", (i,), one=True)
        if not actual: return err("Socio inexistente", 404)
        e = logic.validar_socio({**actual, **d})
        if e: return err("; ".join(e))
        if "nro_afiliado" in d: d["nro_afiliado"] = (d["nro_afiliado"] or "").strip() or None
        upd("socios", "id_socio", i, d, ["dni", "nombre", "apellido", "telefono", "email", "tipo_socio", "nro_afiliado", "estado"])
        return jsonify(ok=True)

    @app.delete("/api/socios/<int:i>")  # baja lógica = Inhabilitado
    @auth(*B)
    def socios_del(i):
        if run("SELECT COUNT(*) n FROM prestamos WHERE id_socio=%s AND estado IN ('Activo','Vencido')", (i,), one=True)["n"]:
            return err("No se puede dar de baja: el socio tiene préstamos sin devolver", 409)
        run("UPDATE socios SET estado='Inhabilitado' WHERE id_socio=%s", (i,), write=True)
        return jsonify(ok=True)

    @app.get("/api/socios/<int:i>/prestamos")
    @auth()
    def socio_hist(i):
        return jsonify(run("""SELECT p.*, l.titulo FROM prestamos p JOIN ejemplares e ON e.id_ejemplar=p.id_ejemplar
            JOIN libros l ON l.id_libro=e.id_libro WHERE p.id_socio=%s ORDER BY p.fecha_salida DESC""", (i,)))

    # Préstamos, devoluciones y avisos (CU05, CU06, CU08, CU09)
    @app.get("/api/prestamos")
    @auth()
    def prestamos_get():
        mark()
        est = request.args.get("estado")
        return jsonify(run("""SELECT p.*, CONCAT(s.nombre,' ',s.apellido) socio, l.titulo, e.codigo_inventario,
            IF(p.estado='Vencido',DATEDIFF(CURDATE(),p.fecha_vencimiento),0) dias_atraso
            FROM prestamos p JOIN socios s ON s.id_socio=p.id_socio JOIN ejemplares e ON e.id_ejemplar=p.id_ejemplar
            JOIN libros l ON l.id_libro=e.id_libro WHERE (%s IS NULL OR p.estado=%s) ORDER BY p.fecha_vencimiento""", (est, est)))

    @app.post("/api/prestamos")
    @auth()
    def prestar():
        d = request.get_json() or {}
        dni, cod = str(d.get("dni", "")).strip(), str(d.get("codigo_inventario", "")).strip()
        if not dni or not cod: return err("El DNI del socio y el código del ejemplar son obligatorios")
        mark()
        s = run("SELECT * FROM socios WHERE dni=%s", (dni,), one=True)
        e = run("SELECT * FROM ejemplares WHERE codigo_inventario=%s", (cod,), one=True)
        if not s: return err("No existe un socio con ese DNI", 404)
        if not e: return err("No existe un ejemplar con ese código", 404)
        venc = run("SELECT COUNT(*) n FROM prestamos WHERE id_socio=%s AND estado='Vencido'", (s["id_socio"],), one=True)["n"] > 0
        ok, msg = logic.puede_prestar(s["estado"], venc, e["estado_disponibilidad"])
        if not ok: return err(msg, 409)
        hoy = date.today()
        c = conn()
        try:  # transaccion: prestamo + cambio de estado del ejemplar
            with c.cursor() as cur:
                cur.execute("INSERT INTO prestamos(id_socio,id_ejemplar,id_usuario,fecha_salida,fecha_vencimiento) VALUES(%s,%s,%s,%s,%s)",
                            (s["id_socio"], e["id_ejemplar"], session["uid"], hoy, logic.calcular_vencimiento(hoy)))
                pid = cur.lastrowid
                cur.execute("UPDATE ejemplares SET estado_disponibilidad='Prestado' WHERE id_ejemplar=%s", (e["id_ejemplar"],))
            c.commit()
        except Exception:
            c.rollback(); raise
        finally:
            c.close()
        return jsonify(id_prestamo=pid, fecha_vencimiento=logic.calcular_vencimiento(hoy).isoformat()), 201

    @app.post("/api/prestamos/<int:i>/devolucion")
    @auth()
    def devolver(i):
        p = run("SELECT * FROM prestamos WHERE id_prestamo=%s", (i,), one=True)
        if not p: return err("Préstamo inexistente", 404)
        if p["estado"] == "Devuelto": return err("El préstamo ya fue devuelto", 409)
        run("UPDATE prestamos SET estado='Devuelto', fecha_devolucion=CURDATE() WHERE id_prestamo=%s", (i,), write=True)
        run("UPDATE ejemplares SET estado_disponibilidad='Disponible' WHERE id_ejemplar=%s", (p["id_ejemplar"],), write=True)
        return jsonify(ok=True)

    @app.get("/api/vencidos")
    @auth()
    def vencidos_get():
        mark(); return jsonify(vencidos())

    @app.post("/api/prestamos/<int:i>/aviso")
    @auth(*B)
    def aviso(i):
        mark()
        v = next((x for x in vencidos() if x["id_prestamo"] == i), None)
        if not v: return err("El préstamo no está vencido", 409)
        if not v["avisado"]:
            run("INSERT INTO avisos_vencimiento(id_prestamo,fecha_emision,medio_notificacion) VALUES(%s,NOW(),'Plantilla')", (i,), write=True)
        return jsonify(texto=logic.texto_aviso(v["socio"], v["telefono"], v["titulo"], v["fecha_vencimiento"], v["dias_atraso"]))

    return app

if __name__ == "__main__":
    create_app().run(debug=True, port=5000)
