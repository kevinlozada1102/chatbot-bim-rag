# Dockerfile para Chatbot BIM RAG
FROM python:3.9-slim

# Establecer el directorio de trabajo
WORKDIR /app

# Variables de entorno para Python
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Instalar dependencias del sistema
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Copiar archivos de dependencias
COPY requirements.txt .

# Instalar dependencias de Python
RUN pip install --upgrade pip && \
    pip install -r requirements.txt

# Copiar el código de la aplicación
COPY . .

# Crear directorio para cache
RUN mkdir -p /app/cache/files /app/cache/vector_store

# Exponer el puerto
EXPOSE 5001

# Comando para ejecutar la aplicación
CMD ["python", "app.py"]
