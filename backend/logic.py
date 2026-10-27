from datetime import date, datetime, timedelta

PLAZO_DIAS = 15

def _d(x):
    if isinstance(x, datetime): return x.date()
    if isinstance(x, date): return x
    return datetime.strptime(str(x)[:10], "%Y-%m-%d").date()

def calcular_vencimiento(fecha_salida, dias=PLAZO_DIAS):
    return _d(fecha_salida) + timedelta(days=dias)

def dias_atraso(vencimiento, hoy=None):
    hoy = _d(hoy) if hoy else date.today()
    return max((hoy - _d(vencimiento)).days, 0)

def validar_socio(d):
    e = []
    for c in ("dni", "nombre", "apellido", "tipo_socio"):
        if not str(d.get(c) or "").strip(): e.append(f"El campo {c} es obligatorio")
    dni = str(d.get("dni") or "").strip()
    if dni and not (dni.isdigit() and 7 <= len(dni) <= 9):
        e.append("El DNI debe tener entre 7 y 9 dígitos numéricos")
    t = d.get("tipo_socio")
    if t and t not in ("Afiliado CEC", "Particular"): e.append("Tipo de socio inválido")
    if t == "Afiliado CEC" and not str(d.get("nro_afiliado") or "").strip():
        e.append("El afiliado CEC requiere número de afiliado")
    return e

def puede_prestar(estado_socio, tiene_vencidos, estado_ejemplar):
    if estado_socio != "Habilitado": return False, "El socio está inhabilitado"
    if tiene_vencidos: return False, "El socio tiene préstamos vencidos sin devolver"
    if estado_ejemplar != "Disponible": return False, f"El ejemplar no está disponible (estado: {estado_ejemplar})"
    return True, "OK"

def texto_aviso(nombre, telefono, titulo, vencimiento, dias):
    return (f"Estimado/a {nombre}: le recordamos que el ejemplar «{titulo}» venció el "
            f"{_d(vencimiento).strftime('%d/%m/%Y')} ({dias} días de atraso). Por favor, regularice la "
            f"devolución a la brevedad. Biblioteca Sarmiento - CEC Rafaela. Contacto: {telefono or 's/d'}")
