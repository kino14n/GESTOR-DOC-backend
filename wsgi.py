# backend/wsgi.py
from .app import create_app  # ← import relativo
app = create_app()
