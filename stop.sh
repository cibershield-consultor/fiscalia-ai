#!/bin/bash
echo "⏹  Parando Fiscalía IA..."
if command -v docker compose &> /dev/null; then
    docker compose down
else
    docker-compose down
fi
echo "✅ Detenido. Los datos se conservan en los volúmenes de Docker."
