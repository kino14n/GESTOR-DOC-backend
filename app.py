from flask import Flask
from routes.documentos import documentos_bp

app = Flask(__name__)
app.register_blueprint(documentos_bp)

if __name__ == '__main__':
    app.run(debug=True)
