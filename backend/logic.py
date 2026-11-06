"""Reglas de negocio y validaciones puras (sin base de datos): fáciles de probar con pruebas unitarias."""
import re
from datetime import date, datetime, timedelta

PLAZO_DIAS = 15
MAX_EJEMPLARES = 200
TIPOS_SOCIO = ("Afiliado CEC", "Particular")
ESTADOS_SOCIO = ("Habilitado", "Inhabilitado")
MAXLEN = {"dni": 15, "nombre": 100, "apellido": 100, "telefono": 30, "email": 100, "nro_afiliado": 30, "isbn": 20,
          "titulo": 255, "autor": 150, "editorial": 100, "categoria": 100, "ubicacion_fisica": 50, "codigo_inventario": 50}
EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
CODIGO = re.compile(r"^[A-Za-z0-9._-]+$")

def _d(x):
    if isinstance(x, datetime): return x.date()
    if isinstance(x, date): return x
    return datetime.strptime(str(x)[:10], "%Y-%m-%d").date()

def calcular_vencimiento(fecha_salida, dias=PLAZO_DIAS):
    return _d(fecha_salida) + timedelta(days=dias)

def dias_atraso(vencimiento, hoy=None):
    hoy = _d(hoy) if hoy else date.today()
    return max((hoy - _d(vencimiento)).days, 0)

def _largos(d, campos):
    """Cada campo, si viene, debe ser texto y respetar el largo máximo de la columna."""
    e = []
    for c in campos:
        v = d.get(c)
        if v is None: continue
        if not isinstance(v, str): e.append(f"El campo {c} debe ser texto")
        elif len(v.strip()) > MAXLEN[c]: e.append(f"El campo {c} no puede superar {MAXLEN[c]} caracteres")
    return e

def validar_socio(d):
    e = _largos(d, ("dni", "nombre", "apellido", "telefono", "email", "nro_afiliado"))
    for c in ("dni", "nombre", "apellido", "tipo_socio"):
        if not str(d.get(c) or "").strip(): e.append(f"El campo {c} es obligatorio")
    dni = str(d.get("dni") or "").strip()
    if dni and not (dni.isdigit() and 7 <= len(dni) <= 9):
        e.append("El DNI debe tener entre 7 y 9 dígitos numéricos")
    t = d.get("tipo_socio")
    if t and t not in TIPOS_SOCIO: e.append("Tipo de socio inválido")
    if t == "Afiliado CEC" and not str(d.get("nro_afiliado") or "").strip():
        e.append("El afiliado CEC requiere número de afiliado")
    mail = d.get("email")
    if isinstance(mail, str) and mail.strip() and not EMAIL.match(mail.strip()): e.append("El email no tiene un formato válido")
    if d.get("estado") is not None and d.get("estado") not in ESTADOS_SOCIO: e.append("Estado de socio inválido")
    return e

def validar_libro(d, parcial=False):
    e = []
    for c in ("titulo", "autor", "categoria", "ubicacion_fisica"):
        if (not parcial or c in d) and not str(d.get(c) or "").strip(): e.append(f"El campo {c} es obligatorio")
    return e + _largos(d, ("titulo", "autor", "categoria", "ubicacion_fisica", "editorial", "isbn"))

def validar_cantidad(v):
    """Devuelve (cantidad, errores). Admite entero o texto numérico, entre 0 y MAX_EJEMPLARES."""
    if v in (None, ""): return 0, []
    if isinstance(v, bool) or not (isinstance(v, int) or (isinstance(v, str) and v.strip().isdigit())):
        return 0, ["La cantidad de ejemplares debe ser un número entero"]
    n = int(v)
    if not 0 <= n <= MAX_EJEMPLARES: return 0, [f"La cantidad de ejemplares debe estar entre 0 y {MAX_EJEMPLARES}"]
    return n, []

def validar_codigo(c):
    if not isinstance(c, str) or not c.strip(): return ["El código de inventario es obligatorio"]
    c = c.strip()
    if len(c) > MAXLEN["codigo_inventario"] or not CODIGO.match(c):
        return ["El código de inventario solo admite letras, números, punto, guion y guion bajo (máx. 50)"]
    return []

def puede_prestar(estado_socio, tiene_vencidos, estado_ejemplar):
    if estado_socio != "Habilitado": return False, "El socio está inhabilitado"
    if tiene_vencidos: return False, "El socio tiene préstamos vencidos sin devolver"
    if estado_ejemplar != "Disponible": return False, f"El ejemplar no está disponible (estado: {estado_ejemplar})"
    return True, "OK"

def texto_aviso(nombre, telefono, titulo, vencimiento, dias):
    return (f"Estimado/a {nombre}: le recordamos que el ejemplar «{titulo}» venció el "
            f"{_d(vencimiento).strftime('%d/%m/%Y')} ({dias} días de atraso). Por favor, regularice la "
            f"devolución a la brevedad. Biblioteca Sarmiento - CEC Rafaela. Contacto: {telefono or 's/d'}")
