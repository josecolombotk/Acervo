"""Crea la base 'acervo' (o la indicada) con sus tablas y datos de prueba.  Uso:  python init_db.py"""
import os, re
from datetime import date, timedelta
import pymysql
from werkzeug.security import generate_password_hash

def init(dbname="acervo", datos=True):
    sql = open(os.path.join(os.path.dirname(__file__), "..", "database", "schema.sql"), encoding="utf8").read()
    sql = re.sub(r"\bacervo\b", dbname, sql)
    c = pymysql.connect(host=os.getenv("DB_HOST", "localhost"), port=int(os.getenv("DB_PORT", 3306)),
                        user=os.getenv("DB_USER", "root"), password=os.getenv("DB_PASS", ""), charset="utf8mb4")
    cur = c.cursor()
    cur.execute(f"DROP DATABASE IF EXISTS {dbname}")
    for st in [s.strip() for s in sql.split(";") if s.strip()]:
        st = "\n".join(l for l in st.splitlines() if not l.startswith("--")).strip()
        if st: cur.execute(st)
    if datos:
        d0 = date.today()
        cur.executemany("INSERT INTO usuarios(username,password_hash,nombre,rol) VALUES(%s,%s,%s,%s)", [
            ("encargada", generate_password_hash("acervo123"), "Daiana Funes", "Bibliotecaria"),
            ("colaborador", generate_password_hash("acervo123"), "Personal CEC", "Colaborador")])
        libros = [("Rayuela", "Julio Cortázar", "Novela", "A-03", 3), ("Ficciones", "Jorge Luis Borges", "Cuento", "A-03", 3),
                  ("Sobre héroes y tumbas", "Ernesto Sabato", "Novela", "A-04", 2), ("Martín Fierro", "José Hernández", "Poesía", "B-02", 4),
                  ("Historia de la Argentina", "Felix Luna", "Historia", "C-07", 2)]
        for i, (t, a, cat, u, n) in enumerate(libros, 1):
            cur.execute("INSERT INTO libros(titulo,autor,categoria,ubicacion_fisica) VALUES(%s,%s,%s,%s)", (t, a, cat, u))
            for k in range(1, n + 1):
                cur.execute("INSERT INTO ejemplares(id_libro,codigo_inventario) VALUES(%s,%s)", (i, f"L{i:04d}-{k}"))
        cur.executemany("INSERT INTO socios(dni,nombre,apellido,telefono,email,tipo_socio,nro_afiliado) VALUES(%s,%s,%s,%s,%s,%s,%s)", [
            ("30123456", "Lucía", "Fernández", "3492-555101", "lucia@mail.com", "Afiliado CEC", "A-001"),
            ("38222111", "Martín", "Gómez", "3492-555102", None, "Afiliado CEC", "A-002"),
            ("41555777", "Sofía", "Ramírez", "3492-555103", "sofia@mail.com", "Particular", None),
            ("27999888", "Carlos", "Pérez", "3492-555104", None, "Particular", None)])
        for sid, eid, dias in [(1, 1, 29), (2, 4, 24), (3, 7, 18), (4, 10, 5)]:  # 3 vencidos + 1 activo
            sal = d0 - timedelta(days=dias)
            cur.execute("INSERT INTO prestamos(id_socio,id_ejemplar,id_usuario,fecha_salida,fecha_vencimiento) VALUES(%s,%s,1,%s,%s)",
                        (sid, eid, sal, sal + timedelta(days=15)))
            cur.execute("UPDATE ejemplares SET estado_disponibilidad='Prestado' WHERE id_ejemplar=%s", (eid,))
    c.commit(); c.close()
    print(f"Base '{dbname}' lista.")

if __name__ == "__main__":
    init()
