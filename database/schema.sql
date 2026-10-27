-- Acervo - Esquema de base de datos (MySQL / MariaDB de XAMPP). Basado en el DER de la Etapa 2.
CREATE DATABASE IF NOT EXISTS acervo CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE acervo;
CREATE TABLE IF NOT EXISTS usuarios (
  id_usuario INT AUTO_INCREMENT PRIMARY KEY,
  username VARCHAR(50) NOT NULL UNIQUE,
  password_hash VARCHAR(255) NOT NULL,
  nombre VARCHAR(100) NOT NULL,
  rol VARCHAR(20) NOT NULL DEFAULT 'Colaborador'
);
CREATE TABLE IF NOT EXISTS socios (
  id_socio INT AUTO_INCREMENT PRIMARY KEY,
  dni VARCHAR(15) NOT NULL UNIQUE,
  nombre VARCHAR(100) NOT NULL,
  apellido VARCHAR(100) NOT NULL,
  telefono VARCHAR(30),
  email VARCHAR(100),
  tipo_socio VARCHAR(20) NOT NULL,
  nro_afiliado VARCHAR(30) NULL UNIQUE,
  estado VARCHAR(20) NOT NULL DEFAULT 'Habilitado'
);
CREATE TABLE IF NOT EXISTS libros (
  id_libro INT AUTO_INCREMENT PRIMARY KEY,
  isbn VARCHAR(20) NULL,
  titulo VARCHAR(255) NOT NULL,
  autor VARCHAR(150) NOT NULL,
  editorial VARCHAR(100),
  categoria VARCHAR(100),
  ubicacion_fisica VARCHAR(50),
  activo BOOLEAN NOT NULL DEFAULT TRUE
);
CREATE TABLE IF NOT EXISTS ejemplares (
  id_ejemplar INT AUTO_INCREMENT PRIMARY KEY,
  id_libro INT NOT NULL,
  codigo_inventario VARCHAR(50) NOT NULL UNIQUE,
  estado_disponibilidad VARCHAR(20) NOT NULL DEFAULT 'Disponible',
  FOREIGN KEY (id_libro) REFERENCES libros(id_libro)
);
CREATE TABLE IF NOT EXISTS prestamos (
  id_prestamo INT AUTO_INCREMENT PRIMARY KEY,
  id_socio INT NOT NULL,
  id_ejemplar INT NOT NULL,
  id_usuario INT NOT NULL,
  fecha_salida DATE NOT NULL,
  fecha_vencimiento DATE NOT NULL,
  fecha_devolucion DATE NULL,
  estado VARCHAR(20) NOT NULL DEFAULT 'Activo',
  FOREIGN KEY (id_socio) REFERENCES socios(id_socio),
  FOREIGN KEY (id_ejemplar) REFERENCES ejemplares(id_ejemplar),
  FOREIGN KEY (id_usuario) REFERENCES usuarios(id_usuario)
);
CREATE TABLE IF NOT EXISTS avisos_vencimiento (
  id_aviso INT AUTO_INCREMENT PRIMARY KEY,
  id_prestamo INT NOT NULL UNIQUE,
  fecha_emision DATETIME NOT NULL,
  medio_notificacion VARCHAR(50),
  FOREIGN KEY (id_prestamo) REFERENCES prestamos(id_prestamo)
);
