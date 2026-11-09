"""Pruebas de integración: API + lógica + MySQL real (base 'acervo_test'). Requiere XAMPP con MySQL iniciado."""
import os, threading, pytest
os.environ["DB_NAME"] = "acervo_test"
os.environ["ACERVO_ADMIN_PASS"] = "Test-Admin-1234"
os.environ["ACERVO_COLAB_PASS"] = "Test-Colab-1234"
import init_db, app as appmod

H = "acervo"   # valor de la cabecera anti-CSRF

def nuevo_cliente(usuario=None, clave=None):
    c = appmod.create_app().test_client()
    c.environ_base["HTTP_X_REQUESTED_WITH"] = H
    if usuario: assert c.post("/api/login", json={"username": usuario, "password": clave}).status_code == 200
    return c

@pytest.fixture(scope="module")
def cli():
    init_db.init("acervo_test", force=True)
    return nuevo_cliente("encargada", "Test-Admin-1234")

def test_crear_socio_impacta_en_bd_y_se_recupera(cli):
    nuevo = {"dni": "35111222", "nombre": "Julia", "apellido": "Ríos", "tipo_socio": "Particular"}
    assert cli.post("/api/socios", json=nuevo).status_code == 201
    assert cli.post("/api/socios", json=nuevo).status_code == 409                   # DNI duplicado
    assert any(s["dni"] == "35111222" for s in cli.get("/api/socios?q=35111222").get_json())
    assert appmod.run("SELECT COUNT(*) n FROM socios WHERE dni='35111222'", one=True)["n"] == 1

def test_prestamo_y_devolucion_actualizan_ejemplar(cli):
    antes = next(l for l in cli.get("/api/libros?q=Ficciones").get_json())["disponibles"]
    r = cli.post("/api/prestamos", json={"dni": "35111222", "codigo_inventario": "L0002-2"})
    assert r.status_code == 201
    assert appmod.run("SELECT estado_disponibilidad e FROM ejemplares WHERE codigo_inventario='L0002-2'", one=True)["e"] == "Prestado"
    assert next(l for l in cli.get("/api/libros?q=Ficciones").get_json())["disponibles"] == antes - 1
    otro = cli.post("/api/prestamos", json={"dni": "27999888", "codigo_inventario": "L0002-2"})   # socio habilitado y sin vencidos
    assert otro.status_code == 409 and "no está disponible" in otro.get_json()["error"]          # rechazado por el ejemplar, no por el socio
    assert cli.post(f"/api/prestamos/{r.get_json()['id_prestamo']}/devolucion").status_code == 200
    assert appmod.run("SELECT estado_disponibilidad e FROM ejemplares WHERE codigo_inventario='L0002-2'", one=True)["e"] == "Disponible"

def test_prestamos_simultaneos_no_duplican_el_ejemplar(cli):
    dnis = ("40000001", "40000002")
    for d in dnis: assert cli.post("/api/socios", json={"dni": d, "nombre": "S", "apellido": d, "tipo_socio": "Particular"}).status_code == 201
    res = []
    def pedir(d):
        c = nuevo_cliente("encargada", "Test-Admin-1234")
        res.append(c.post("/api/prestamos", json={"dni": d, "codigo_inventario": "L0005-1"}).status_code)
    hilos = [threading.Thread(target=pedir, args=(d,)) for d in dnis]
    [h.start() for h in hilos]; [h.join() for h in hilos]
    assert sorted(res) == [201, 409]                                                # solo uno obtiene el ejemplar
    assert appmod.run("SELECT COUNT(*) n FROM prestamos WHERE id_ejemplar=(SELECT id_ejemplar FROM ejemplares WHERE codigo_inventario='L0005-1')", one=True)["n"] == 1

def test_autorizacion_csrf_y_validaciones(cli):
    col = nuevo_cliente("colaborador", "Test-Colab-1234")
    datos = {"dni": "12345678", "nombre": "x", "apellido": "y", "tipo_socio": "Particular"}
    assert col.post("/api/socios", json=datos).status_code == 403                   # rol sin permiso
    assert "telefono" not in col.get("/api/socios").get_json()[0]                   # sin datos de contacto para el Colaborador
    sin_cabecera = appmod.create_app().test_client()
    assert sin_cabecera.post("/api/logout").status_code == 403                      # falta la cabecera anti-CSRF
    assert nuevo_cliente().get("/api/socios").status_code == 401                    # sin sesión
    malo = {"titulo": "T", "autor": "A", "categoria": "C", "ubicacion_fisica": "U"}
    assert cli.post("/api/libros", json={**malo, "cantidad": "abc"}).status_code == 400
    assert cli.post("/api/libros", json={**malo, "cantidad": 10**9}).status_code == 400
    assert cli.post("/api/libros", json={**malo, "titulo": 5}).status_code == 400

def test_login_se_bloquea_tras_cinco_fallos():
    c = nuevo_cliente()
    for _ in range(5): assert c.post("/api/login", json={"username": "intruso", "password": "x"}).status_code == 401
    assert c.post("/api/login", json={"username": "intruso", "password": "x"}).status_code == 429
