#!/bin/bash

# Script de inicialización para Docker
# Chatbot BIM RAG

set -e

echo "🚀 Iniciando Chatbot BIM RAG con Docker..."

# Colores para output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Verificar si existe archivo .env
if [ ! -f .env ]; then
    echo -e "${YELLOW}⚠️  Archivo .env no encontrado${NC}"
    echo "Copiando .env.example a .env..."
    cp .env.example .env
    echo -e "${RED}⚠️  IMPORTANTE: Edita el archivo .env con tus credenciales antes de continuar${NC}"
    echo "Especialmente:"
    echo "  - OPENAI_API_KEY"
    echo "  - POSTGRES_PASSWORD"
    echo "  - SECRET_KEY"
    echo ""
    read -p "¿Deseas continuar de todos modos? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Crear directorios necesarios
echo "📁 Creando directorios necesarios..."
mkdir -p cache/files cache/vector_store logs

# Verificar si Docker está instalado
if ! command -v docker &> /dev/null; then
    echo -e "${RED}❌ Docker no está instalado${NC}"
    echo "Por favor instala Docker desde: https://docs.docker.com/get-docker/"
    exit 1
fi

# Verificar si Docker Compose está instalado
if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
    echo -e "${RED}❌ Docker Compose no está instalado${NC}"
    echo "Por favor instala Docker Compose desde: https://docs.docker.com/compose/install/"
    exit 1
fi

# Detener contenedores existentes si los hay
echo "🛑 Deteniendo contenedores existentes..."
docker-compose down 2>/dev/null || true

# Construir imágenes
echo "🔨 Construyendo imágenes Docker..."
docker-compose build

# Iniciar servicios
echo "🚀 Iniciando servicios..."
docker-compose up -d

# Esperar a que los servicios estén listos
echo "⏳ Esperando a que los servicios estén listos..."
sleep 10

# Verificar estado de los servicios
echo "🔍 Verificando estado de los servicios..."
docker-compose ps

# Verificar health de la aplicación
echo "🏥 Verificando salud de la aplicación..."
max_attempts=30
attempt=0

while [ $attempt -lt $max_attempts ]; do
    if curl -f http://localhost:5001/api/health &> /dev/null; then
        echo -e "${GREEN}✅ Aplicación lista y funcionando!${NC}"
        break
    fi
    attempt=$((attempt + 1))
    echo "Intento $attempt/$max_attempts - Esperando..."
    sleep 2
done

if [ $attempt -eq $max_attempts ]; then
    echo -e "${RED}❌ La aplicación no respondió después de $max_attempts intentos${NC}"
    echo "Revisando logs:"
    docker-compose logs app
    exit 1
fi

# Mostrar información
echo ""
echo -e "${GREEN}✅ ¡Chatbot BIM RAG está ejecutándose!${NC}"
echo ""
echo "📋 Información de servicios:"
echo "  🌐 API: http://localhost:5001"
echo "  🏥 Health Check: http://localhost:5001/api/health"
echo "  📊 Stats: http://localhost:5001/api/stats"
echo "  🗄️  PostgreSQL: localhost:5432"
echo ""
echo "📝 Comandos útiles:"
echo "  Ver logs: docker-compose logs -f"
echo "  Ver logs de app: docker-compose logs -f app"
echo "  Detener: docker-compose down"
echo "  Reiniciar: docker-compose restart"
echo "  Ver estado: docker-compose ps"
echo ""
echo "📚 Documentación de API: ENDPOINTS_INFORMACION_GEZ.md"
