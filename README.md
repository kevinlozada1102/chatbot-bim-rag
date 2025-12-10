# Chatbot BIM RAG - API Documentation

## Descripción

Sistema de chatbot con arquitectura RAG (Retrieval-Augmented Generation) especializado en información BIM. Proporciona una API REST y comunicación en tiempo real mediante WebSockets.

### Personalidad de ABI

**ABI (Asistente BIM)** es el asistente especializado en orientación sobre la implementación de BIM en el Estado peruano, con las siguientes características:

- 🤖 **Nombre**: ABI (Asistente BIM)
- 🇵🇪 **Especialización**: Implementación BIM en el Estado peruano
- 😄 **Personalidad**: Gracioso y coloquial, pero profesional
- 💬 **Estilo**: Respuestas breves y directas
- 🌍 **Referencia**: Siempre incluye el link específico del documento fuente para más información
- 📩 **Contacto alternativo**: planbimperu@mef.gob.pe

**Comportamientos especiales:**
- Mensaje proactivo al iniciar chat: "Hola 👋, me llamo ABI y soy el asistente BIM para orientación sobre la implementación de BIM en el Estado peruano. ¿En qué te ayudo?"
- Manejo de incomprensión: 1er intento → "Disculpa, no te entendí...", 2do intento → Redirige a email
- No termina oraciones finales con punto (.)
- Finaliza trámites con: "¿Te puedo ayudar en otra consulta?"

## Tecnologías

- **Backend**: Flask 3.1.2 + Flask-SocketIO 5.3.6
- **Base de Datos**: PostgreSQL con SQLAlchemy 2.0.36
- **IA**: OpenAI GPT + LangChain 0.2.16
- **Vector Store**: ChromaDB con Sentence Transformers
- **Procesamiento**: BeautifulSoup4, pypdf, html2text

## Configuración

### Opción 1: Docker (Recomendado)

La forma más rápida de desplegar el proyecto:

```bash
# 1. Copiar y configurar variables de entorno
cp .env.example .env
# Editar .env con tu OPENAI_API_KEY

# 2. Iniciar con script automático
./docker-init.sh

# O manualmente
docker-compose up -d
```

**Servidor**: http://localhost:5001

📚 **Documentación completa de Docker**: Ver [DOCKER.md](./DOCKER.md)

### Opción 2: Instalación Local

#### Variables de Entorno
```bash
# OpenAI
OPENAI_API_KEY=sk-...

# Base de Datos
DATABASE_URL=postgresql://user:password@localhost:5432/dbname

# Flask
SECRET_KEY=chatbot-bim-secret-key-2024
FLASK_DEBUG=True
```

#### Instalación
```bash
# Crear entorno virtual
python3 -m venv venv
source venv/bin/activate  # En Windows: venv\Scripts\activate

# Instalar dependencias
pip install -r requirements.txt

# Ejecutar aplicación
python app.py
```

**Servidor**: http://localhost:5001

---

## API REST Endpoints

### 1. Health Check
**GET** `/api/health`

Verifica el estado del sistema y sus componentes.

**Response:**
```json
{
  "status": "running",
  "timestamp": "2024-12-02T15:22:07.123456",
  "database": "OK",
  "rag_system": "OK",
  "version": "1.0.0"
}
```

**Códigos de Estado:**
- `200` - Sistema funcionando correctamente
- `500` - Error interno del servidor

---

### 2. System Stats
**GET** `/api/stats`

Obtiene estadísticas del sistema RAG y documentos procesados.

**Response:**
```json
{
  "documents_processed": 150,
  "total_chunks": 2500,
  "vector_store_size": "45.2MB",
  "cache_hit_rate": 0.78,
  "average_response_time": 1.2
}
```

**Códigos de Estado:**
- `200` - Estadísticas obtenidas exitosamente
- `500` - RAG system no inicializado o error interno

---

### 3. Welcome Message
**GET** `/api/welcome`

Obtiene el mensaje proactivo de bienvenida de ABI.

**Response:**
```json
{
  "success": true,
  "message": {
    "answer": "Hola 👋, me llamo ABI y soy el asistente BIM para orientación sobre la implementación de BIM en el Estado peruano. ¿En qué te ayudo?",
    "sources": [],
    "confidence": "high",
    "message_type": "welcome"
  },
  "timestamp": "2024-12-02T15:22:07.123456"
}
```

**Códigos de Estado:**
- `200` - Mensaje obtenido exitosamente
- `500` - RAG system no inicializado o error interno

---

### 4. Chat Query
**POST** `/api/chat`

Endpoint principal para realizar consultas al chatbot.

**Request Body:**
```json
{
  "message": "¿Qué es un modelo BIM?",
  "session_id": 123
}
```

**Parámetros:**
- `message` *(string, requerido)*: Pregunta o consulta del usuario
- `session_id` *(integer, opcional)*: ID de sesión para persistir conversación

**Response:**
```json
{
  "success": true,
  "response": {
    "answer": "Un modelo BIM (Building Information Modeling) es...",
    "confidence": "high",
    "sources": [
      {
        "document_id": 45,
        "title": "Introducción a BIM",
        "chunk_id": "chunk_123",
        "relevance_score": 0.89
      }
    ],
    "processed_documents": 15
  },
  "timestamp": "2024-12-02T15:22:07.123456"
}
```

**Códigos de Estado:**
- `200` - Consulta procesada exitosamente
- `400` - Mensaje vacío o inválido
- `500` - RAG system no inicializado o error interno

---

### 5. Create Chat Session
**POST** `/api/session`

Crea una nueva sesión de chat para persistir conversaciones.

**Request Body:**
```json
{
  "context": {
    "user_preferences": {},
    "initial_topic": "BIM modeling"
  }
}
```

**Parámetros:**
- `context` *(object, opcional)*: Contexto inicial de la sesión

**Response:**
```json
{
  "success": true,
  "session_id": 123,
  "session_token": "550e8400-e29b-41d4-a716-446655440000",
  "timestamp": "2024-12-02T15:22:07.123456"
}
```

**Códigos de Estado:**
- `200` - Sesión creada exitosamente
- `500` - Error creando sesión en base de datos

---

### 6. Get Session Messages
**GET** `/api/session/{session_id}/messages`

Obtiene el historial de mensajes de una sesión específica.

**Parámetros de URL:**
- `session_id` *(integer, requerido)*: ID de la sesión

**Response:**
```json
{
  "success": true,
  "session_id": 123,
  "messages": [
    {
      "id": 1,
      "type": "user",
      "content": "¿Qué es un modelo BIM?",
      "timestamp": "2024-12-02T15:20:00.000000",
      "metadata": {}
    },
    {
      "id": 2,
      "type": "assistant",
      "content": "Un modelo BIM es...",
      "timestamp": "2024-12-02T15:20:05.000000",
      "metadata": {
        "confidence": "high",
        "sources": [...],
        "processed_documents": 15
      }
    }
  ]
}
```

**Códigos de Estado:**
- `200` - Mensajes obtenidos exitosamente
- `500` - Error accediendo a la base de datos

---

### 7. Get Documents
**GET** `/api/documents`

Lista todos los documentos disponibles en el sistema.

**Response:**
```json
{
  "success": true,
  "total": 150,
  "documents": [
    {
      "id": 1,
      "tipo": "PDF",
      "categoria": "Normativas",
      "titulo": "Manual BIM Nivel 2",
      "link": "https://example.com/manual.pdf",
      "cache_status": "processed",
      "chunks_count": 45,
      "last_processed": "2024-12-02T10:00:00.000000",
      "created_at": "2024-12-01T08:00:00.000000"
    }
  ]
}
```

**Códigos de Estado:**
- `200` - Documentos obtenidos exitosamente
- `500` - Error accediendo al repositorio

---

### 8. Process Documents
**POST** `/api/documents/process`

Inicia el procesamiento de documentos pendientes. Ahora maneja errores individualmente y procesa todos los documentos aunque algunos fallen.

**Request Body:**
```json
{
  "batch_size": 3
}
```

**Parámetros:**
- `batch_size` *(integer, opcional)*: Número de documentos a procesar (default: 3)

**Response:**
```json
{
  "success": true,
  "result": {
    "processed_count": 2,
    "failed_count": 1,
    "processing_time": 45.2,
    "documents_processed": [
      {
        "id": 10,
        "title": "Guía BIM Avanzada",
        "chunks_created": 23,
        "status": "success"
      },
      {
        "id": 11,
        "title": "Manual Error",
        "chunks_created": 0,
        "status": "error",
        "error": "Failed to download PDF"
      }
    ],
    "success_rate": "66.7%"
  },
  "timestamp": "2024-12-02T15:22:07.123456"
}
```

**Códigos de Estado:**
- `200` - Procesamiento iniciado exitosamente
- `500` - RAG system no inicializado o error procesando

---

### 9. Clear Documents Processing
**POST** `/api/documents/clear`

Limpia los procesamientos de documentos: elimina vector store, cache de archivos y resetea estados en la base de datos.

**Request Body:**
```json
{
  "clear_vector_store": true,
  "clear_file_cache": true,
  "reset_type": "all"
}
```

**Parámetros:**
- `clear_vector_store` *(boolean, opcional)*: Limpiar vector store (ChromaDB) (default: true)
- `clear_file_cache` *(boolean, opcional)*: Limpiar cache de archivos descargados (default: true)
- `reset_type` *(string, opcional)*: Tipo de reset en BD - "all", "errors", "web", "pdf" (default: "all")

**Response:**
```json
{
  "success": true,
  "result": {
    "success": true,
    "message": "Processing cleared successfully",
    "vector_store_cleared": true,
    "file_cache_cleared": {
      "success": true,
      "files_removed": 15,
      "size_freed_mb": 127.5
    },
    "database_reset": 45,
    "errors": []
  },
  "timestamp": "2024-12-02T15:22:07.123456"
}
```

**Códigos de Estado:**
- `200` - Limpieza ejecutada (revisar `success` en response para resultado)
- `400` - Parámetro `reset_type` inválido
- `500` - RAG system no inicializado o error procesando

---

## WebSocket Events (Socket.IO)

**Conexión**: `ws://localhost:5001`

### Client → Server Events

#### `connect`
Se ejecuta automáticamente al conectarse.

**Server Response:**
```json
{
  "message": "Conectado al servidor ABI",
  "status": "connected"
}
```

#### `start_session`
Inicia una nueva sesión de chat.

**Client Data:**
```json
{
  "user_agent": "Mozilla/5.0...",
  "additional_context": {}
}
```

**Server Response:**
```json
{
  "session_token": "550e8400-e29b-41d4-a716-446655440000",
  "session_id": 123,
  "timestamp": "2024-12-02T15:22:07.123456"
}
```

#### `send_message`
Envía un mensaje al chatbot.

**Client Data:**
```json
{
  "message": "¿Qué es LOD en BIM?",
  "session_token": "550e8400-e29b-41d4-a716-446655440000"
}
```

**Server Responses:**
1. **Typing Indicator:**
```json
{
  "typing": true
}
```

2. **Bot Message:**
```json
{
  "type": "assistant",
  "content": "LOD (Level of Development) en BIM se refiere...",
  "sources": [...],
  "confidence": "high",
  "timestamp": "2024-12-02T15:22:07.123456"
}
```

3. **Typing Stop:**
```json
{
  "typing": false
}
```

#### `end_session`
Finaliza la sesión actual.

**Client Data:**
```json
{
  "session_token": "550e8400-e29b-41d4-a716-446655440000"
}
```

**Server Response:**
```json
{
  "message": "Session ended successfully"
}
```

### Server → Client Events

#### `status`
Estado de conexión del servidor.

#### `session_started`
Confirmación de nueva sesión creada.

#### `message`
Respuesta del chatbot a un mensaje.

#### `typing_indicator`
Indica si el bot está procesando un mensaje.

#### `session_ended`
Confirmación de sesión finalizada.

#### `error`
Notificación de errores.

```json
{
  "message": "Error processing message: ..."
}
```

#### `disconnect`
Se ejecuta automáticamente al desconectarse.

---

## Códigos de Error Comunes

| Código | Descripción |
|--------|-------------|
| `400` | Bad Request - Datos inválidos o faltantes |
| `404` | Not Found - Endpoint no encontrado |
| `500` | Internal Server Error - Error interno del sistema |

### Manejo de Errores

Todos los endpoints devuelven errores en el siguiente formato:

```json
{
  "error": "Descripción del error"
}
```

---

## Estructura de Base de Datos

### Tablas Principales

#### `tbl_web_chat_session`
- Almacena sesiones de chat
- Incluye tokens únicos y metadata de contexto

#### `tbl_web_chat_message`
- Mensajes individuales por sesión
- Diferencia entre mensajes de usuario y asistente

#### `informacion_gez`
- Documentos y recursos BIM
- Estados de procesamiento y cache

---

## Ejemplos de Uso

### Curl Examples

```bash
# Health Check
curl -X GET http://localhost:5001/api/health

# Mensaje de bienvenida de ABI
curl -X GET http://localhost:5001/api/welcome

# Crear sesión
curl -X POST http://localhost:5001/api/session \
  -H "Content-Type: application/json" \
  -d '{"context": {}}'

# Enviar mensaje
curl -X POST http://localhost:5001/api/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "¿Qué es un modelo BIM?",
    "session_id": 123
  }'

# Listar documentos
curl -X GET http://localhost:5001/api/documents

# Procesar documentos
curl -X POST http://localhost:5001/api/documents/process \
  -H "Content-Type: application/json" \
  -d '{"batch_size": 5}'

# Limpiar procesamientos (todo)
curl -X POST http://localhost:5001/api/documents/clear \
  -H "Content-Type: application/json" \
  -d '{
    "clear_vector_store": true,
    "clear_file_cache": true,
    "reset_type": "all"
  }'

# Limpiar solo documentos con errores
curl -X POST http://localhost:5001/api/documents/clear \
  -H "Content-Type: application/json" \
  -d '{
    "clear_vector_store": false,
    "clear_file_cache": false,
    "reset_type": "errors"
  }'
```

### JavaScript WebSocket Example

```javascript
import io from 'socket.io-client';

const socket = io('http://localhost:5001');

// Conectar
socket.on('connect', () => {
  console.log('Conectado al servidor');
  
  // Iniciar sesión
  socket.emit('start_session', {
    user_agent: navigator.userAgent
  });
});

// Sesión iniciada
socket.on('session_started', (data) => {
  console.log('Sesión creada:', data.session_id);
  
  // Enviar mensaje
  socket.emit('send_message', {
    message: '¿Qué es BIM?',
    session_token: data.session_token
  });
});

// Recibir respuesta
socket.on('message', (data) => {
  console.log('Respuesta del bot:', data.content);
});

// Indicador de escritura
socket.on('typing_indicator', (data) => {
  console.log('Bot escribiendo:', data.typing);
});

// Errores
socket.on('error', (error) => {
  console.error('Error:', error.message);
});
```

---

## Logs y Monitoreo

El sistema genera logs detallados para:
- Conexiones WebSocket
- Procesamiento de mensajes
- Operaciones de base de datos
- Errores y excepciones

**Formato de logs:**
```
2024-12-02 15:22:07 - app - INFO - Processing chat query: ¿Qué es un modelo BIM?...
```

---

## Desarrollo y Testing

### Estructura del Proyecto
```
chatbot-bim-rag/
├── app.py                 # Aplicación principal
├── requirements.txt       # Dependencias
├── config/
│   └── database.py       # Configuración BD
├── app/
│   ├── models/           # Modelos SQLAlchemy
│   ├── repositories/     # Acceso a datos
│   └── services/         # Lógica de negocio
└── scripts/
    └── process_documents.py
```

### Comandos Útiles

```bash
# Iniciar servidor de desarrollo
python app.py

# Procesar documentos manualmente
python scripts/process_documents.py

# Verificar dependencias
pip freeze > requirements.txt
```

---

*Documentación generada automáticamente para Chatbot BIM RAG v1.0.0*