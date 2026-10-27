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
