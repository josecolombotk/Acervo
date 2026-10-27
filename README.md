
# Acervo – Sistema de Gestión de Biblioteca 
Biblioteca Sarmiento – CEC Rafaela · IFTS N.° 29 · Flask + MySQL (XAMPP)

## Requisitos
Python 3.10+, XAMPP (MySQL/MariaDB), Git. Node.js 18+ (frontend).

## Instalación y puesta en marcha
1. Abrir **XAMPP Control Panel** e iniciar **MySQL** (usuario `root`, sin contraseña por defecto, puerto 3306).
2. En una terminal:
   ```
   cd backend
   python -m venv venv
   venv\Scripts\activate          (Linux/Mac: source venv/bin/activate)
   pip install -r requirements.txt
   python init_db.py              # crea la base 'acervo', tablas y datos de prueba
   python app.py                  # API en http://localhost:5000
   ```
   Alternativa manual: importar `database/schema.sql` desde phpMyAdmin (http://localhost/phpmyadmin).
   Otra configuración de MySQL: variables de entorno `DB_HOST`, `DB_PORT`, `DB_USER`, `DB_PASS`, `DB_NAME`.

3. Frontend (otra terminal, con el backend corriendo):
   ```
   cd frontend
   npm install
   npm run dev                    # abrir http://localhost:5173
   ```

## Credenciales de prueba
| Usuario | Contraseña | Rol |
|---|---|---|
| encargada | acervo123 | Bibliotecaria |
| colaborador | acervo123 | Colaborador |

## Pruebas (ejecutar desde la carpeta raíz del proyecto)
```
pytest tests/test_unit.py -v           # unitarias (no necesitan MySQL)
pytest tests/test_integration.py -v    # integración (necesitan MySQL iniciado; usan la base 'acervo_test')
```

## Endpoints principales
`POST /api/login` · `GET /api/dashboard` · `GET|POST /api/libros` · `PUT|DELETE /api/libros/<id>` ·
`GET|POST /api/socios` · `PUT|DELETE /api/socios/<id>` · `GET|POST /api/prestamos` ·
`POST /api/prestamos/<id>/devolucion` · `GET /api/vencidos` · `POST /api/prestamos/<id>/aviso`.
Las bajas (DELETE) son **lógicas** (regla de negocio de la Etapa 2).
