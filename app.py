from flask import Flask
from flask_cors import CORS
from documentos import documentos_bp
import os

app = Flask(__name__)
CORS(app, origins=os.getenv('CORS_ORIGINS', '*'))

app.register_blueprint(documentos_bp, url_prefix='/api/documentos')

@app.route('/api/ping')
def ping():
    return {'status': 'ok'}

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.getenv('PORT', 5000)))
