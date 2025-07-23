from flask import Flask
from flask_cors import CORS
from routes.documentos import documentos_bp

app = Flask(__name__)
CORS(app)  # Aquí habilitas CORS para todas las rutas

app.register_blueprint(documentos_bp)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
