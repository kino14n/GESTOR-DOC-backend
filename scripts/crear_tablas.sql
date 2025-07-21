CREATE TABLE IF NOT EXISTS documentos (
    id INT AUTO_INCREMENT PRIMARY KEY,
    nombre VARCHAR(255),
    archivo VARCHAR(255),
    fecha DATE,
    codigos TEXT
);