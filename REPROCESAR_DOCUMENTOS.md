# Cómo Reprocesar Documentos para Actualizar Metadatos

## Problema Identificado

Los chunks existentes en el vector store fueron creados **antes** de agregar el campo `link` a los metadatos. Por lo tanto:

- ❌ Los chunks NO tienen el campo `link` en sus metadatos
- ❌ El LLM está inventando links basándose en el contexto
- ✅ **Solución**: Reprocesar todos los documentos

## Paso 1: Limpiar Vector Store y Estado Actual

Ejecuta el siguiente comando para limpiar todo:

```bash
curl -X POST http://localhost:5001/api/documents/clear \
  -H "Content-Type: application/json" \
  -d '{
    "clear_vector_store": true,
    "clear_file_cache": true,
    "reset_type": "all"
  }'
```

Esto hará:
- Limpiar el vector store (ChromaDB)
- Limpiar cache de archivos descargados
- Resetear todos los documentos a estado `not_cached`

## Paso 2: Reprocesar Todos los Documentos

Una vez limpiado, procesa todos los documentos nuevamente:

```bash
curl -X POST http://localhost:5001/api/documents/process \
  -H "Content-Type: application/json" \
  -d '{
    "batch_size": 5
  }'
```

Parámetros:
- `batch_size`: Número de documentos a procesar por lote (recomendado: 3-5)

## Paso 3: Verificar Estadísticas

Verifica que todo se procesó correctamente:

```bash
curl http://localhost:5001/api/stats
```

Deberías ver:
- `cached`: Número de documentos procesados
- `not_cached`: Debe ser 0
- Total de chunks creados

## Alternativa: Procesar Documento por Documento

Si prefieres procesar solo ciertos documentos, puedes hacerlo uno por uno:

```bash
curl -X POST http://localhost:5001/api/documents/{ID}/process
```

Reemplaza `{ID}` con el ID del documento.

## Verificar que Ahora Funcionan los Links

Después del reprocesamiento:

1. Los chunks tendrán el campo `link` en sus metadatos
2. El método `_extract_sources_from_chunks` extraerá el link correcto
3. El LLM usará EXACTAMENTE el link de las fuentes (no inventará)
4. Las respuestas incluirán el link específico del documento de `informacion_gez`

## Notas Importantes

⚠️ **IMPORTANTE**: Después de reprocesar, los chunks tendrán los siguientes metadatos:

```python
{
    "source_id": 123,
    "source_type": "pdf",  # o "web"
    "titulo": "Título del documento",
    "categoria": "Categoría",
    "vector_store_id": "doc_123_abc123",
    "link": "https://ejemplo.com/documento.pdf"  # ← AHORA INCLUIDO
}
```

⚠️ **Tiempo de procesamiento**: Depende del número de documentos y su tamaño. Puede tomar varios minutos.

⚠️ **Costo OpenAI**: El reprocesamiento genera embeddings nuevamente, lo que consume créditos de OpenAI API.
