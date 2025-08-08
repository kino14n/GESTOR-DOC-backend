from flask import Flask
from flask_cors import CORS

# Se importa el Blueprint que contiene todas las rutas de tu API
from routes.documentos import documentos_bp

app = Flask(__name__)

# --- CONFIGURACIÓN DE CORS ---
# Permite que tu frontend en GitHub Pages se comunique con este backend.
origins = [
    "https://kino14n.github.io",
    "http://127.0.0.1:5500",
    "http://localhost:5500"
]
CORS(app, resources={r"/api/*": {"origins": origins}})


# --- REGISTRO DE RUTAS (BLUEPRINT) ---
# Activa todas las rutas que has definido en el archivo 'routes/documentos.py'.
app.register_blueprint(documentos_bp)


# --- PUNTO DE ENTRADA ---
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)