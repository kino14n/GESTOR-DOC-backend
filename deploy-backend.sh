#!/bin/bash

# Ir a la carpeta del backend (ajusta la ruta)
cd /ruta/a/tu/backend

# Agregar todos los cambios
git add .

# Commit con mensaje con fecha y hora
git commit -m "Deploy backend: $(date '+%Y-%m-%d %H:%M:%S')"

# Subir a main
git push origin main

echo "🚀 Cambios subidos y deploy iniciado en Railway"
