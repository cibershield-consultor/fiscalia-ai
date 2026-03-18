#!/bin/bash
# ============================================================
# Fiscalía IA — Script de instalación y arranque
# macOS / Linux
# ============================================================

set -e  # Parar si hay error

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No color

echo ""
echo "⚖️  ================================================"
echo "⚖️   Fiscalía IA — Instalación automática"
echo "⚖️  ================================================"
echo ""

# ── 1. Comprobar Docker ────────────────────────────────────
echo "🔍 Comprobando Docker..."
if ! command -v docker &> /dev/null; then
    echo -e "${RED}❌ Docker no está instalado.${NC}"
    echo ""
    echo "Instálalo desde: https://www.docker.com/get-started"
    echo "  - macOS: descarga Docker Desktop"
    echo "  - Ubuntu/Debian: sudo apt install docker.io docker-compose-plugin"
    exit 1
fi

if ! command -v docker compose &> /dev/null && ! command -v docker-compose &> /dev/null; then
    echo -e "${RED}❌ Docker Compose no está disponible.${NC}"
    echo "Actualiza Docker Desktop o instala docker-compose-plugin."
    exit 1
fi

echo -e "${GREEN}✅ Docker disponible: $(docker --version)${NC}"

# ── 2. Crear .env si no existe ─────────────────────────────
if [ ! -f "backend/.env" ]; then
    echo ""
    echo -e "${YELLOW}⚙️  Configurando variables de entorno...${NC}"
    cp backend/.env.example backend/.env

    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "🔑 IMPORTANTE: Necesitas una API key de OpenAI"
    echo "   Obtén la tuya en: https://platform.openai.com/api-keys"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    read -p "Pega tu OpenAI API Key (empieza por sk-...): " API_KEY

    if [ -z "$API_KEY" ]; then
        echo -e "${YELLOW}⚠️  No introdujiste una API key. Puedes editar backend/.env manualmente después.${NC}"
    else
        # Compatible con macOS (sed -i '') y Linux (sed -i)
        if [[ "$OSTYPE" == "darwin"* ]]; then
            sed -i '' "s|OPENAI_API_KEY=.*|OPENAI_API_KEY=$API_KEY|" backend/.env
        else
            sed -i "s|OPENAI_API_KEY=.*|OPENAI_API_KEY=$API_KEY|" backend/.env
        fi
        echo -e "${GREEN}✅ API key guardada en backend/.env${NC}"
    fi

    # Generate a random SECRET_KEY
    SECRET=$(python3 -c "import secrets; print(secrets.token_hex(32))" 2>/dev/null || openssl rand -hex 32)
    if [[ "$OSTYPE" == "darwin"* ]]; then
        sed -i '' "s|SECRET_KEY=.*|SECRET_KEY=$SECRET|" backend/.env
    else
        sed -i "s|SECRET_KEY=.*|SECRET_KEY=$SECRET|" backend/.env
    fi
else
    echo -e "${GREEN}✅ backend/.env ya existe${NC}"
fi

# ── 3. Arrancar con Docker Compose ────────────────────────
echo ""
echo "🐳 Construyendo e iniciando contenedores..."
echo "   (La primera vez puede tardar 1-2 minutos mientras descarga Python)"
echo ""

# Usar docker compose (v2) o docker-compose (v1)
if command -v docker compose &> /dev/null; then
    docker compose up --build -d
else
    docker-compose up --build -d
fi

# ── 4. Esperar a que el backend esté listo ─────────────────
echo ""
echo "⏳ Esperando a que el servidor arranque..."
for i in {1..20}; do
    if curl -sf http://localhost:8000/ > /dev/null 2>&1; then
        echo -e "${GREEN}✅ Backend listo!${NC}"
        break
    fi
    sleep 2
    echo -n "."
done
echo ""

# ── 5. Resultado ───────────────────────────────────────────
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo -e "${GREEN}🎉 ¡Fiscalía IA está en marcha!${NC}"
echo ""
echo "  🌐 Aplicación web:   http://localhost:3000"
echo "  📚 API (Swagger):    http://localhost:8000/docs"
echo "  🔌 Backend directo:  http://localhost:8000"
echo ""
echo "Para parar:     docker compose down"
echo "Para ver logs:  docker compose logs -f"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Abrir el navegador automáticamente
sleep 1
if [[ "$OSTYPE" == "darwin"* ]]; then
    open http://localhost:3000
elif command -v xdg-open &> /dev/null; then
    xdg-open http://localhost:3000 2>/dev/null &
fi
