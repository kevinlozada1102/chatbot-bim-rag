# Endpoints para Mantenimiento de `informacion_gez`

Base URL: `http://localhost:5001`

## CRUD Endpoints

### 1. **Listar Documentos**
```
GET /api/documents
```
**Descripción:** Obtiene lista de documentos con filtros opcionales

**Query Parameters:**
- `tipo` (opcional): Filtrar por tipo ['web', 'pdf', 'consulta_previa']
- `categoria` (opcional): Filtrar por categoría
- `cache_status` (opcional): Filtrar por estado de cache ['not_cached', 'processing', 'cached', 'error']
- `activo` (opcional): Filtrar por estado activo [true/false], default: true

**Response:**
```json
{
  "success": true,
  "total": 10,
  "documents": [
    {
      "id": 1,
      "tipo": "web",
      "categoria": "recursos",
      "titulo": "Guía de implementación BIM",
      "link": "https://example.com/guia",
      "tags": ["bim", "guia"],
      "prioridad": 5,
      "activo": true,
      "cache_status": "cached",
      "chunks_count": 25,
      "last_processed": "2024-01-15T10:30:00",
      "created_at": "2024-01-10T08:00:00",
      "updated_at": "2024-01-15T10:30:00"
    }
  ]
}
```

### 2. **Obtener Documento por ID**
```
GET /api/documents/{document_id}
```
**Descripción:** Obtiene un documento específico con todos sus detalles

**Response:**
```json
{
  "success": true,
  "document": {
    "id": 1,
    "tipo": "web",
    "categoria": "recursos",
    "titulo": "Guía de implementación BIM",
    "link": "https://example.com/guia",
    "contenido_procesado": "Texto completo procesado...",
    "tags": ["bim", "guia"],
    "prioridad": 5,
    "activo": true,
    "cache_status": "cached",
    "chunks_count": 25,
    "vector_store_id": "doc_1_vector_id",
    "last_processed": "2024-01-15T10:30:00",
    "created_at": "2024-01-10T08:00:00",
    "updated_at": "2024-01-15T10:30:00"
  }
}
```

### 3. **Crear Documento**
```
POST /api/documents
```
**Descripción:** Crea un nuevo documento en el sistema

**Request Body:**
```json
{
  "tipo": "web",                      // REQUERIDO: 'web', 'pdf', 'consulta_previa'
  "categoria": "recursos",            // OPCIONAL
  "titulo": "Nueva guía BIM",         // OPCIONAL
  "link": "https://example.com",      // OPCIONAL
  "contenido_procesado": "...",       // OPCIONAL
  "tags": ["bim", "tutorial"],        // OPCIONAL (JSON array)
  "prioridad": 3,                     // OPCIONAL (default: 3, rango: 1-5)
  "activo": true                      // OPCIONAL (default: true)
}
```

**Response (201 Created):**
```json
{
  "success": true,
  "message": "Document created successfully",
  "document": {
    "id": 15,
    "tipo": "web",
    "categoria": "recursos",
    "titulo": "Nueva guía BIM",
    "link": "https://example.com",
    "tags": ["bim", "tutorial"],
    "prioridad": 3,
    "activo": true,
    "cache_status": "not_cached",
    "created_at": "2024-01-20T14:30:00"
  }
}
```

### 4. **Actualizar Documento**
```
PUT /api/documents/{document_id}
```
**Descripción:** Actualiza un documento existente (actualización parcial)

**Request Body:** (Todos los campos son opcionales, solo enviar los que se quieren actualizar)
```json
{
  "tipo": "pdf",
  "categoria": "normativas",
  "titulo": "Título actualizado",
  "link": "https://nuevo-link.com",
  "contenido_procesado": "...",
  "tags": ["tag1", "tag2"],
  "prioridad": 4,
  "activo": false
}
```

**Response:**
```json
{
  "success": true,
  "message": "Document updated successfully",
  "document": {
    "id": 15,
    "tipo": "pdf",
    "categoria": "normativas",
    "titulo": "Título actualizado",
    "link": "https://nuevo-link.com",
    "tags": ["tag1", "tag2"],
    "prioridad": 4,
    "activo": false,
    "cache_status": "not_cached",
    "chunks_count": 0,
    "last_processed": null,
    "updated_at": "2024-01-20T15:00:00"
  }
}
```

### 5. **Eliminar Documento (Soft Delete)**
```
DELETE /api/documents/{document_id}
```
**Descripción:** Marca el documento como inactivo (no lo elimina de la BD)

**Response:**
```json
{
  "success": true,
  "message": "Document deleted successfully (marked as inactive)"
}
```

### 6. **Eliminar Documento Permanentemente (Hard Delete)**
```
DELETE /api/documents/{document_id}/hard-delete
```
**Descripción:** Elimina permanentemente el documento de la base de datos

**Response:**
```json
{
  "success": true,
  "message": "Document permanently deleted from database"
}
```

---

## Endpoints de Procesamiento

### 7. **Procesar Documentos Pendientes (Batch)**
```
POST /api/documents/process
```
**Descripción:** Procesa múltiples documentos pendientes en lote

**Request Body:**
```json
{
  "batch_size": 5    // OPCIONAL (default: 3)
}
```

**Response:**
```json
{
  "success": true,
  "result": {
    "processed_count": 4,
    "failed_count": 1,
    "processing_time": 0,
    "success_rate": "80.0%",
    "documents_processed": [
      {
        "id": 1,
        "title": "Documento 1",
        "status": "success",
        "chunks_created": 15
      },
      {
        "id": 2,
        "title": "Documento 2",
        "status": "error",
        "error": "Failed to download",
        "chunks_created": 0
      }
    ]
  },
  "timestamp": "2024-01-20T16:00:00"
}
```

### 8. **Procesar Documento Individual**
```
POST /api/documents/{document_id}/process
```
**Descripción:** Procesa un documento específico inmediatamente

**Response:**
```json
{
  "success": true,
  "document_id": 15,
  "result": {
    "success": true,
    "document": {
      "id": 15,
      "titulo": "Guía BIM",
      "tipo": "web",
      "cache_status": "cached",
      "chunks_count": 20,
      "last_processed": "2024-01-20T16:05:00"
    },
    "message": "Document processed successfully"
  },
  "timestamp": "2024-01-20T16:05:00"
}
```

### 9. **Obtener Estadísticas de Documentos**
```
GET /api/documents/stats
```
**Descripción:** Obtiene estadísticas de cache y procesamiento

**Response:**
```json
{
  "success": true,
  "stats": {
    "total_documents": 50,
    "cached": 35,
    "processing": 2,
    "errors": 3,
    "not_cached": 10
  },
  "timestamp": "2024-01-20T16:10:00"
}
```

### 10. **Limpiar Procesamiento de Documentos**
```
POST /api/documents/clear
```
**Descripción:** Limpia vector store, cache y resetea estados de procesamiento

**Request Body:**
```json
{
  "clear_vector_store": true,     // OPCIONAL (default: true)
  "clear_file_cache": true,       // OPCIONAL (default: true)
  "reset_type": "all"             // OPCIONAL: 'all', 'errors', 'web', 'pdf' (default: 'all')
}
```

**Response:**
```json
{
  "success": true,
  "result": {
    "success": true,
    "vector_store_cleared": true,
    "file_cache_cleared": true,
    "database_records_reset": 45,
    "reset_type": "all"
  },
  "timestamp": "2024-01-20T16:15:00"
}
```

---

## Resumen de Endpoints

| Método | Endpoint | Descripción |
|--------|----------|-------------|
| GET | `/api/documents` | Listar documentos con filtros |
| GET | `/api/documents/{id}` | Obtener documento por ID |
| POST | `/api/documents` | Crear nuevo documento |
| PUT | `/api/documents/{id}` | Actualizar documento |
| DELETE | `/api/documents/{id}` | Soft delete (marcar inactivo) |
| DELETE | `/api/documents/{id}/hard-delete` | Hard delete (eliminar permanente) |
| POST | `/api/documents/process` | Procesar documentos en lote |
| POST | `/api/documents/{id}/process` | Procesar documento individual |
| GET | `/api/documents/stats` | Obtener estadísticas |
| POST | `/api/documents/clear` | Limpiar procesamiento |

---

## Notas Importantes

### Validaciones
- **Campo `tipo`**: Solo acepta 'web', 'pdf', 'consulta_previa'
- **Campo `prioridad`**: Rango 1-5 (1 = baja, 5 = alta)
- **Campo `cache_status`**: Valores posibles: 'not_cached', 'processing', 'cached', 'error'

### Flujo de Trabajo Recomendado

1. **Crear documento nuevo**: `POST /api/documents`
2. **Listar documentos**: `GET /api/documents?activo=true`
3. **Ver estadísticas**: `GET /api/documents/stats`
4. **Procesar documento**: `POST /api/documents/{id}/process`
5. **Verificar procesamiento**: `GET /api/documents/{id}` (revisar `cache_status` y `chunks_count`)
6. **Actualizar si es necesario**: `PUT /api/documents/{id}`
7. **Eliminar (soft)**: `DELETE /api/documents/{id}`

### Tipos de Documento

- **web**: Páginas web que se descargan y procesan
- **pdf**: Archivos PDF que se descargan y procesan
- **consulta_previa**: Consultas previas (solo almacenamiento, no se procesan)

### Estados de Cache

- **not_cached**: Documento no procesado aún
- **processing**: En proceso de descarga/vectorización
- **cached**: Procesado exitosamente y disponible en vector store
- **error**: Error durante el procesamiento

### Procesamiento

Solo se procesan documentos con:
- `activo = true`
- `tipo IN ('web', 'pdf')`
- `cache_status IN ('not_cached', 'error')`

### Consideraciones de Seguridad

- Los endpoints de **procesamiento** y **limpieza** requieren que el sistema RAG esté inicializado
- El **hard delete** es irreversible, usar con precaución
- Se recomienda usar **soft delete** para mantener histórico

---

## Códigos de Error Comunes

- **400 Bad Request**: Datos inválidos o faltantes
- **404 Not Found**: Documento no encontrado
- **500 Internal Server Error**: Error del servidor (revisar logs)

## Ejemplo de Uso con cURL

```bash
# Crear documento
curl -X POST http://localhost:5001/api/documents \
  -H "Content-Type: application/json" \
  -d '{
    "tipo": "web",
    "titulo": "Nueva guía BIM",
    "link": "https://mef.gob.pe/planbimperu",
    "categoria": "recursos",
    "prioridad": 4
  }'

# Listar documentos activos tipo web
curl "http://localhost:5001/api/documents?tipo=web&activo=true"

# Obtener documento específico
curl http://localhost:5001/api/documents/1

# Actualizar documento
curl -X PUT http://localhost:5001/api/documents/1 \
  -H "Content-Type: application/json" \
  -d '{
    "titulo": "Título actualizado",
    "prioridad": 5
  }'

# Procesar documento
curl -X POST http://localhost:5001/api/documents/1/process

# Ver estadísticas
curl http://localhost:5001/api/documents/stats

# Eliminar documento (soft delete)
curl -X DELETE http://localhost:5001/api/documents/1
```
