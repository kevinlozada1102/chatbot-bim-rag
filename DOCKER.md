# Despliegue con Docker - Chatbot BIM RAG

Esta guía explica cómo desplegar el proyecto usando Docker y Docker Compose.

## 📋 Requisitos Previos

- **Docker**: versión 20.10 o superior
- **Docker Compose**: versión 2.0 o superior
- **OpenAI API Key**: Necesaria para el sistema RAG

### Instalación de Docker

**macOS / Windows:**
- Descargar [Docker Desktop](https://www.docker.com/products/docker-desktop)

**Linux (Ubuntu/Debian):**
```bash
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker $USER
```

## 🚀 Inicio Rápido

### 1. Configurar Variables de Entorno

Copiar el archivo de ejemplo:
```bash
cp .env.example .env
```

Editar `.env` con tus credenciales:
```bash
# PostgreSQL
POSTGRES_DB=chatbot_bim_db
POSTGRES_USER=postgres
POSTGRES_PASSWORD=TU_CONTRASEÑA_SEGURA

# OpenAI (REQUERIDO)
OPENAI_API_KEY=sk-tu-api-key-aqui

# Flask
SECRET_KEY=tu-clave-secreta-segura
FLASK_ENV=production
```

### 2. Iniciar con Script Automático

```bash
./docker-init.sh
```

Este script:
- Verifica dependencias
- Crea directorios necesarios
- Construye las imágenes
- Inicia los servicios
- Verifica el estado de salud

### 3. O Iniciar Manualmente

```bash
# Construir imágenes
docker-compose build

# Iniciar servicios en background
docker-compose up -d

# Ver logs
docker-compose logs -f
```

## 🏗️ Arquitectura Docker

El proyecto utiliza 2 servicios principales:

### 1. **postgres** - Base de Datos
- **Imagen**: `postgres:15-alpine`
- **Puerto**: 5432
- **Volumen**: Datos persistentes en `postgres_data`
- **Health Check**: Verifica disponibilidad cada 10s

### 2. **app** - Aplicación Flask
- **Imagen**: Custom (construida desde Dockerfile)
- **Puerto**: 5001
- **Volúmenes**:
  - `./cache` → `/app/cache` (documentos y vectores)
  - `./logs` → `/app/logs` (logs de aplicación)
- **Health Check**: Verifica `/api/health` cada 30s

### Red
- **chatbot-network**: Red bridge privada para comunicación entre servicios

## 📦 Servicios y Puertos

| Servicio | Puerto | Descripción |
|----------|--------|-------------|
| app | 5001 | API REST y WebSockets |
| postgres | 5432 | Base de datos PostgreSQL |

## 🔧 Comandos Útiles

### Gestión de Servicios

```bash
# Iniciar servicios
docker-compose up -d

# Detener servicios
docker-compose down

# Detener y eliminar volúmenes (¡CUIDADO! Elimina datos)
docker-compose down -v

# Reiniciar servicios
docker-compose restart

# Reiniciar solo la app
docker-compose restart app

# Ver estado de servicios
docker-compose ps
```

### Logs y Debugging

```bash
# Ver logs de todos los servicios
docker-compose logs -f

# Ver logs solo de la app
docker-compose logs -f app

# Ver logs de PostgreSQL
docker-compose logs -f postgres

# Ver últimas 100 líneas
docker-compose logs --tail=100 app

# Ver logs desde hace 10 minutos
docker-compose logs --since 10m app
```

### Acceso a Contenedores

```bash
# Acceder al contenedor de la app
docker-compose exec app bash

# Acceder a PostgreSQL
docker-compose exec postgres psql -U postgres -d chatbot_bim_db

# Ver archivos en cache
docker-compose exec app ls -la /app/cache/files

# Ver proceso de Python
docker-compose exec app ps aux
```

### Construcción y Actualización

```bash
# Reconstruir imágenes
docker-compose build

# Reconstruir sin cache
docker-compose build --no-cache

# Actualizar y reiniciar
docker-compose up -d --build
```

## 🗄️ Gestión de Base de Datos

### Backup

```bash
# Backup de base de datos
docker-compose exec postgres pg_dump -U postgres chatbot_bim_db > backup_$(date +%Y%m%d_%H%M%S).sql

# Backup comprimido
docker-compose exec postgres pg_dump -U postgres chatbot_bim_db | gzip > backup_$(date +%Y%m%d_%H%M%S).sql.gz
```

### Restore

```bash
# Restaurar desde backup
cat backup.sql | docker-compose exec -T postgres psql -U postgres chatbot_bim_db

# Restaurar desde backup comprimido
gunzip -c backup.sql.gz | docker-compose exec -T postgres psql -U postgres chatbot_bim_db
```

### Conexión Directa

```bash
# Conectar a PostgreSQL
docker-compose exec postgres psql -U postgres -d chatbot_bim_db

# Listar tablas
\dt

# Ver datos de una tabla
SELECT * FROM informacion_gez LIMIT 10;

# Salir
\q
```

## 📊 Monitoreo

### Health Checks

```bash
# Verificar health de la API
curl http://localhost:5001/api/health

# Verificar estadísticas
curl http://localhost:5001/api/stats

# Verificar documentos
curl http://localhost:5001/api/documents/stats
```

### Estado de Servicios

```bash
# Ver estado de contenedores
docker-compose ps

# Ver uso de recursos
docker stats

# Ver solo recursos de este proyecto
docker stats chatbot-bim-app chatbot-bim-postgres
```

### Inspección de Volúmenes

```bash
# Listar volúmenes
docker volume ls | grep chatbot

# Inspeccionar volumen de PostgreSQL
docker volume inspect chatbot-bim-rag_postgres_data

# Ver uso de espacio
docker system df -v
```

## 🔒 Seguridad

### Variables Sensibles

**NUNCA** commitear el archivo `.env` con credenciales reales:
```bash
# Ya está en .gitignore
echo ".env" >> .gitignore
```

### Contraseñas Seguras

Generar contraseñas seguras:
```bash
# Para POSTGRES_PASSWORD
openssl rand -base64 32

# Para SECRET_KEY
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

### Limitar Acceso a PostgreSQL

Para producción, modificar `docker-compose.yml`:
```yaml
postgres:
  ports:
    # Comentar o eliminar para no exponer el puerto
    # - "5432:5432"
```

## 🐛 Troubleshooting

### Problema: Puerto 5001 ya en uso

```bash
# Ver qué está usando el puerto
lsof -i :5001

# Cambiar puerto en .env
APP_PORT=5002
```

### Problema: PostgreSQL no inicia

```bash
# Ver logs detallados
docker-compose logs postgres

# Verificar permisos de volumen
docker volume rm chatbot-bim-rag_postgres_data
docker-compose up -d
```

### Problema: App no se conecta a PostgreSQL

```bash
# Verificar que postgres esté healthy
docker-compose ps

# Verificar conexión desde app
docker-compose exec app ping postgres

# Verificar DATABASE_URL
docker-compose exec app env | grep DATABASE_URL
```

### Problema: Errores con ChromaDB/Vector Store

```bash
# Limpiar cache de vectores
rm -rf cache/vector_store/*

# Reiniciar app
docker-compose restart app
```

### Problema: Falta OPENAI_API_KEY

```bash
# Verificar variables de entorno
docker-compose config | grep OPENAI_API_KEY

# Asegurarse que .env tiene la key
cat .env | grep OPENAI_API_KEY

# Reiniciar después de modificar
docker-compose restart app
```

## 🚀 Despliegue en Producción

### Optimizaciones Recomendadas

1. **Variables de entorno:**
```bash
FLASK_ENV=production
FLASK_DEBUG=False
```

2. **Usar secrets para credenciales sensibles** (Docker Swarm/Kubernetes)

3. **Configurar reverse proxy (Nginx):**
```nginx
server {
    listen 80;
    server_name tu-dominio.com;

    location / {
        proxy_pass http://localhost:5001;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

4. **Configurar SSL/TLS** con Let's Encrypt

5. **Limitar recursos en docker-compose.yml:**
```yaml
app:
  deploy:
    resources:
      limits:
        cpus: '2'
        memory: 4G
      reservations:
        cpus: '1'
        memory: 2G
```

6. **Configurar logging:**
```yaml
app:
  logging:
    driver: "json-file"
    options:
      max-size: "10m"
      max-file: "3"
```

## 📈 Escalabilidad

### Múltiples Instancias

Para escalar horizontalmente:
```bash
docker-compose up -d --scale app=3
```

Requiere load balancer (Nginx/HAProxy) para distribuir tráfico.

### Volúmenes Externos

Para mejor performance en producción:
```yaml
volumes:
  postgres_data:
    driver: local
    driver_opts:
      type: none
      o: bind
      device: /mnt/data/postgres
```

## 🧹 Limpieza

### Eliminar Todo

```bash
# Detener y eliminar contenedores, redes
docker-compose down

# Eliminar también volúmenes (¡CUIDADO!)
docker-compose down -v

# Limpiar imágenes huérfanas
docker image prune -a

# Limpiar todo el sistema Docker
docker system prune -a --volumes
```

### Limpiar Cache Local

```bash
rm -rf cache/files/*
rm -rf cache/vector_store/*
rm -rf logs/*
```

## 📚 Referencias

- [Documentación Docker](https://docs.docker.com/)
- [Documentación Docker Compose](https://docs.docker.com/compose/)
- [API Endpoints](./ENDPOINTS_INFORMACION_GEZ.md)
- [README Principal](./README.md)

## 🆘 Soporte

Si encuentras problemas:

1. Revisar logs: `docker-compose logs -f`
2. Verificar health: `curl http://localhost:5001/api/health`
3. Verificar variables: `docker-compose config`
4. Revisar issues en GitHub
