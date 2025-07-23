from flask import Flask
from routes.documentos import documentos_bp

app = Flask(__name__)
app.register_blueprint(documentos_bp)

if __name__ == '__main__':
    # Usar host 0.0.0.0 para que sea accesible en Railway
    app.run(debug=True, host='0.0.0.0', port=5000)