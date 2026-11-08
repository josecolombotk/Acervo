from datetime import date
import logic

def test_vencimiento_es_salida_mas_15_dias():
    assert logic.calcular_vencimiento("2026-09-20") == date(2026, 10, 5)          # cruza de mes

def test_dias_de_atraso():
    assert logic.dias_atraso("2026-09-20", hoy="2026-10-04") == 14                  # caso del wireframe
    assert logic.dias_atraso("2026-10-10", hoy="2026-10-04") == 0                   # no vencido

def test_validar_socio():
    ok = {"dni": "30123456", "nombre": "Ana", "apellido": "Paz", "tipo_socio": "Particular"}
    assert logic.validar_socio(ok) == []
    assert logic.validar_socio({**ok, "dni": ""})                                   # campo obligatorio
    assert logic.validar_socio({**ok, "tipo_socio": "Afiliado CEC"})                # afiliado sin nº

def test_reglas_de_prestamo():
    assert logic.puede_prestar("Habilitado", False, "Disponible")[0]
    assert not logic.puede_prestar("Inhabilitado", False, "Disponible")[0]
    assert not logic.puede_prestar("Habilitado", True, "Disponible")[0]
    assert not logic.puede_prestar("Habilitado", False, "Prestado")[0]

def test_validar_socio_tipos_largos_y_estado():
    ok = {"dni": "30123456", "nombre": "Ana", "apellido": "Paz", "tipo_socio": "Particular"}
    assert logic.validar_socio({**ok, "nombre": 123})                              # nombre no textual
    assert logic.validar_socio({**ok, "nombre": "x" * 101})                        # supera 100 caracteres
    assert logic.validar_socio({**ok, "email": "ana@"})                            # email mal formado
    assert logic.validar_socio({**ok, "estado": "Borrado"})                        # estado fuera de catálogo
    assert logic.validar_socio({**ok, "estado": "Inhabilitado"}) == []             # estado válido

def test_validar_cantidad_y_libro_y_codigo():
    for malo in ("abc", -1, 10**9, True, 2.5):                                     # texto, negativo, enorme, booleano, decimal
        assert logic.validar_cantidad(malo)[1], malo
    assert logic.validar_cantidad(5) == (5, [])
    assert logic.validar_cantidad("10") == (10, [])
    libro = {"titulo": "Rayuela", "autor": "Julio Cortázar", "categoria": "Novela", "ubicacion_fisica": "A-03"}
    assert logic.validar_libro(libro) == []
    assert logic.validar_libro({**libro, "titulo": 5})                             # título no textual
    assert logic.validar_codigo("L0001-1") == []
    for malo in ("L1'; DROP TABLE libros;--", "<script>", "", "L" * 51):           # caracteres peligrosos, vacío, largo
        assert logic.validar_codigo(malo), malo
