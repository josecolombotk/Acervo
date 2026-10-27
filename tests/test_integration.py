import os, pytest
os.environ["DB_NAME"] = "acervo_test"
import init_db, app as appmod

@pytest.fixture(scope="module")
def cli():
    init_db.init("acervo_test")
    c = appmod.create_app().test_client()
    assert c.post("/api/login", json={"username": "encargada", "password": "acervo123"}).status_code == 200
    return c

def test_crear_socio_impacta_en_bd_y_se_recupera(cli):
    nuevo = {"dni": "35111222", "nombre": "Julia", "apellido": "Ríos", "tipo_socio": "Particular"}
    assert cli.post("/api/socios", json=nuevo).status_code == 201
    assert cli.post("/api/socios", json=nuevo).status_code == 409                   # DNI duplicado
    assert any(s["dni"] == "35111222" for s in cli.get("/api/socios?q=35111222").get_json())
    assert appmod.run("SELECT COUNT(*) n FROM socios WHERE dni='35111222'", one=True)["n"] == 1

def test_prestamo_y_devolucion_actualizan_ejemplar(cli):
    antes = next(l for l in cli.get("/api/libros?q=Ficciones").get_json())["disponibles"]
    r = cli.post("/api/prestamos", json={"dni": "35111222", "codigo_inventario": "L0002-1"})
    assert r.status_code == 201
    ej = appmod.run("SELECT estado_disponibilidad e FROM ejemplares WHERE codigo_inventario='L0002-1'", one=True)
    assert ej["e"] == "Prestado"
    assert next(l for l in cli.get("/api/libros?q=Ficciones").get_json())["disponibles"] == antes - 1
    assert cli.post("/api/prestamos", json={"dni": "38222111", "codigo_inventario": "L0002-1"}).status_code == 409
    assert cli.post(f"/api/prestamos/{r.get_json()['id_prestamo']}/devolucion").status_code == 200
    assert appmod.run("SELECT estado_disponibilidad e FROM ejemplares WHERE codigo_inventario='L0002-1'", one=True)["e"] == "Disponible"
