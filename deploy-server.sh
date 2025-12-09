#!/bin/bash

# Script de Despliegue para Servidor Ubuntu (DigitalOcean)
# Chatbot BIM RAG

set -e

echo "🚀 Iniciando despliegue de Chatbot BIM RAG en servidor Ubuntu..."

# Colores para output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Variables de configuración
PROJECT_NAME="chatbot-bim-rag"
PROJECT_DIR="/opt/${PROJECT_NAME}"
GITHUB_REPO="https://github.com/kevinlozada1102/chatbot-bim-rag.git"

# Función para mostrar mensajes
print_message() {
    echo -e "${BLUE}==>${NC} $1"
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

# Verificar si se ejecuta como root
if [ "$EUID" -ne 0 ]; then
    print_error "Este script debe ejecutarse como root (usa sudo)"
    exit 1
fi

print_message "Sistema: $(lsb_release -d | cut -f2)"
print_message "Usuario: $(whoami)"
echo ""

# 1. Actualizar sistema
print_message "Actualizando sistema..."
apt update && apt upgrade -y
print_success "Sistema actualizado"

# 2. Instalar dependencias básicas
print_message "Instalando dependencias básicas..."
apt install -y \
    git \
    curl \
    wget \
    ca-certificates \
    gnupg \
    lsb-release \
    software-properties-common
print_success "Dependencias básicas instaladas"

# 3. Instalar Docker
if ! command -v docker &> /dev/null; then
    print_message "Instalando Docker..."

    # Agregar repositorio de Docker
    install -m 0755 -d /etc/apt/keyrings
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
    chmod a+r /etc/apt/keyrings/docker.gpg

    echo \
      "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
      $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
      tee /etc/apt/sources.list.d/docker.list > /dev/null

    apt update
    apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

    # Iniciar Docker
    systemctl start docker
    systemctl enable docker

    print_success "Docker instalado correctamente"
else
    print_success "Docker ya está instalado: $(docker --version)"
fi

# 4. Verificar Docker Compose
if ! docker compose version &> /dev/null; then
    print_error "Docker Compose no está disponible"
    exit 1
else
    print_success "Docker Compose disponible: $(docker compose version)"
fi

# 5. Configurar firewall (UFW)
print_message "Configurando firewall..."
if command -v ufw &> /dev/null; then
    ufw --force enable
    ufw allow 22/tcp      # SSH
    ufw allow 80/tcp      # HTTP
    ufw allow 443/tcp     # HTTPS
    ufw allow 5001/tcp    # API (temporal, mejor usar Nginx)
    print_success "Firewall configurado"
else
    print_warning "UFW no está instalado, omitiendo configuración de firewall"
fi

# 6. Clonar o actualizar repositorio
if [ -d "$PROJECT_DIR" ]; then
    print_message "Proyecto existe, actualizando..."
    cd "$PROJECT_DIR"

    # Detener servicios si están corriendo
    if [ -f "docker-compose.yml" ]; then
        print_message "Deteniendo servicios..."
        docker compose down || true
    fi

    # Actualizar código
    git fetch origin
    git reset --hard origin/main
    git pull origin main

    print_success "Proyecto actualizado"
else
    print_message "Clonando proyecto desde GitHub..."
    mkdir -p $(dirname "$PROJECT_DIR")
    git clone "$GITHUB_REPO" "$PROJECT_DIR"
    cd "$PROJECT_DIR"
    print_success "Proyecto clonado"
fi

# 7. Configurar variables de entorno
print_message "Configurando variables de entorno..."
if [ ! -f ".env" ]; then
    cp .env.example .env
    print_warning "Archivo .env creado desde .env.example"
    print_warning "IMPORTANTE: Debes editar .env con tus credenciales:"
    print_warning "  - OPENAI_API_KEY"
    print_warning "  - POSTGRES_PASSWORD"
    print_warning "  - SECRET_KEY"
    echo ""
    print_message "Para editar: nano $PROJECT_DIR/.env"
    echo ""
    read -p "¿Deseas editar .env ahora? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        nano .env
    else
        print_warning "Recuerda editar .env antes de iniciar los servicios"
        print_warning "Comando: nano $PROJECT_DIR/.env"
    fi
else
    print_success "Archivo .env ya existe"
fi

# 8. Crear directorios necesarios
print_message "Creando directorios..."
mkdir -p cache/files cache/vector_store logs
chown -R 1000:1000 cache logs  # Usuario del contenedor
print_success "Directorios creados"

# 9. Construir e iniciar servicios
print_message "Construyendo imágenes Docker..."
docker compose build --no-cache

print_message "Iniciando servicios..."
docker compose up -d

# 10. Esperar a que los servicios estén listos
print_message "Esperando a que los servicios estén listos..."
sleep 15

# 11. Verificar estado de los servicios
print_message "Verificando estado de los servicios..."
docker compose ps

# 12. Verificar health de la aplicación
max_attempts=30
attempt=0

while [ $attempt -lt $max_attempts ]; do
    if curl -f http://localhost:5001/api/health &> /dev/null; then
        print_success "Aplicación lista y funcionando!"
        break
    fi
    attempt=$((attempt + 1))
    echo "Intento $attempt/$max_attempts - Esperando..."
    sleep 2
done

if [ $attempt -eq $max_attempts ]; then
    print_error "La aplicación no respondió después de $max_attempts intentos"
    print_message "Revisando logs:"
    docker compose logs --tail=50 app
    exit 1
fi

# 13. Mostrar información del servidor
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
print_success "🎉 ¡Despliegue completado exitosamente!"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "📋 Información del servidor:"
echo "  🌐 IP Pública: $(curl -s ifconfig.me)"
echo "  📁 Directorio: $PROJECT_DIR"
echo ""
echo "🔗 URLs de acceso:"
echo "  API: http://$(curl -s ifconfig.me):5001"
echo "  Health: http://$(curl -s ifconfig.me):5001/api/health"
echo "  Stats: http://$(curl -s ifconfig.me):5001/api/stats"
echo "  Docs: http://$(curl -s ifconfig.me):5001/api/documents"
echo ""
echo "📝 Comandos útiles:"
echo "  Ver logs: cd $PROJECT_DIR && docker compose logs -f"
echo "  Detener: cd $PROJECT_DIR && docker compose down"
echo "  Reiniciar: cd $PROJECT_DIR && docker compose restart"
echo "  Estado: cd $PROJECT_DIR && docker compose ps"
echo "  Editar .env: nano $PROJECT_DIR/.env"
echo ""
echo "🔧 Próximos pasos recomendados:"
echo "  1. Configurar Nginx como reverse proxy"
echo "  2. Instalar certificado SSL con Let's Encrypt"
echo "  3. Configurar dominio personalizado"
echo "  4. Configurar backups automáticos"
echo ""
echo "📚 Documentación: $PROJECT_DIR/DOCKER.md"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# 14. Probar la API
print_message "Probando API..."
echo ""
curl -s http://localhost:5001/api/health | python3 -m json.tool || echo "API no responde con JSON válido"
echo ""

print_success "¡Despliegue completado!"
