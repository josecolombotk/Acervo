# Acervo – Sistema de Gestión de Biblioteca

Biblioteca Sarmiento – CEC Rafaela · IFTS N.° 29 · Flask + MySQL (XAMPP) · React + Vite

## Requisitos

- Python 3.10 o superior.
- XAMPP (MySQL/MariaDB).
- Node.js 18 o superior.
- Git.

## Instalación y puesta en marcha

### 1. Base de datos

Abrir XAMPP Control Panel e iniciar MySQL.

Configuración local predeterminada:

- Host: `127.0.0.1`
- Puerto: `3306`
- Usuario: `root`
- Contraseña: vacía.

### 2. Backend

Desde una terminal:

```bash
cd backend
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

En Linux/Mac, activar el entorno con:

```bash
source venv/bin/activate
```

Configurar las variables de entorno necesarias para la conexión a MySQL y la clave secreta de Flask.

```text
DB_HOST=127.0.0.1
DB_PORT=3306
DB_USER=root
DB_PASS=
DB_NAME=acervo
SECRET_KEY=clave-local-de-desarrollo
```

Inicializar la base de datos:

```bash
python init_db.py
```

Iniciar el servidor:

```bash
python app.py
```

API disponible en `http://localhost:5000`.

También se puede importar manualmente `database/schema.sql` desde phpMyAdmin:

http://localhost/phpmyadmin

### 3. Frontend

En otra terminal:

```bash
cd frontend
npm install
npm run dev
```

Abrir:

http://localhost:5173

## Seguridad

- Las claves y credenciales deben configurarse mediante variables de entorno.
- No subir contraseñas, claves secretas ni archivos de registro al repositorio.
- En producción se debe utilizar una clave secreta segura.
- No utilizar el usuario root de MySQL en producción.
- La aplicación incorpora controles de acceso, validaciones, limitación de intentos de inicio de sesión y cabeceras HTTP de seguridad.
- El registro de auditoría se almacena en `backend/audit.log`.

## Pruebas

Ejecutar desde la carpeta raíz del proyecto:

```bash
pytest tests/test_unit.py -v
pytest tests/test_integration.py -v
```

Las pruebas unitarias no requieren MySQL.

Las pruebas de integración requieren MySQL iniciado y utilizan la base de datos `acervo_test`.

## Endpoints principales

- `POST /api/login`
- `GET /api/dashboard`
- `GET|POST /api/libros`
- `PUT|DELETE /api/libros/<id>`
- `GET|POST /api/socios`
- `PUT|DELETE /api/socios/<id>`
- `GET|POST /api/prestamos`
- `POST /api/prestamos/<id>/devolucion`
- `GET /api/vencidos`
- `POST /api/prestamos/<id>/aviso`

Las bajas (DELETE) son lógicas, según las reglas de negocio de la Etapa 2.
