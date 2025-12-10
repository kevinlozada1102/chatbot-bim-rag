#!/usr/bin/env python3
"""
Script de diagnóstico para verificar estado del Vector Store
Compara documentos en BD vs chunks en ChromaDB
"""

import sys
import os
from pathlib import Path

# Agregar directorio raíz al path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

from config.database import get_db_session
from app.repositories.informacion_gez_repository import InformacionGezRepository
from app.services.document_cache_manager import DocumentCacheManager

def check_vector_store_sync():
    """Verifica sincronización entre BD y Vector Store"""

    print("=" * 80)
    print("🔍 DIAGNÓSTICO DE VECTOR STORE")
    print("=" * 80)

    # Obtener documentos de BD
    db_session = get_db_session()
    repo = InformacionGezRepository(db_session)

    all_docs = db_session.query(repo.model).all()

    print(f"\n📊 DOCUMENTOS EN BASE DE DATOS:")
    print(f"   Total documentos: {len(all_docs)}")

    cached_docs = [d for d in all_docs if d.cache_status == 'cached']
    processing_docs = [d for d in all_docs if d.cache_status == 'processing']
    error_docs = [d for d in all_docs if d.cache_status == 'error']
    not_cached_docs = [d for d in all_docs if d.cache_status == 'not_cached']

    print(f"   ✅ Cached: {len(cached_docs)}")
    print(f"   ⏳ Processing: {len(processing_docs)}")
    print(f"   ❌ Error: {len(error_docs)}")
    print(f"   ⭕ Not cached: {len(not_cached_docs)}")

    # Verificar Vector Store
    print(f"\n🗄️ VERIFICANDO CHROMADB VECTOR STORE:")

    doc_manager = DocumentCacheManager()
    vector_store_path = Path(doc_manager.vector_store_path)

    print(f"   Path: {vector_store_path}")
    print(f"   Existe: {'✅ SÍ' if vector_store_path.exists() else '❌ NO'}")

    if vector_store_path.exists():
        files = list(vector_store_path.rglob("*"))
        print(f"   Archivos en directorio: {len(files)}")

        # Intentar consultar el vector store
        try:
            test_results = doc_manager.search_similar_chunks("test query", k=1)
            print(f"   ✅ Vector store funcional")
            print(f"   Total chunks indexados: (hacer query completo para contar)")
        except Exception as e:
            print(f"   ❌ Error consultando vector store: {e}")

    # Listar documentos "cached" con detalle
    print(f"\n📄 DOCUMENTOS MARCADOS COMO 'CACHED':")
    for doc in cached_docs:
        print(f"\n   ID: {doc.id}")
        print(f"   Título: {doc.titulo}")
        print(f"   Tipo: {doc.tipo}")
        print(f"   Vector Store ID: {doc.vector_store_id}")
        print(f"   Chunks count: {doc.chunks_count}")
        print(f"   Last processed: {doc.last_processed}")
        print(f"   Link: {doc.link}")

        # Intentar buscar chunks de este documento
        try:
            chunks = doc_manager.search_similar_chunks(
                "test", k=1,
                filter_metadata={"source_id": doc.id}
            )
            print(f"   🔍 Chunks en vector store: {len(chunks)} encontrados")
        except Exception as e:
            print(f"   ❌ Error buscando chunks: {e}")

    # Listar documentos con error
    if error_docs:
        print(f"\n❌ DOCUMENTOS CON ERROR:")
        for doc in error_docs:
            print(f"   ID: {doc.id} - {doc.titulo} ({doc.tipo})")

    # Listar documentos en processing
    if processing_docs:
        print(f"\n⏳ DOCUMENTOS EN PROCESSING (posible problema):")
        for doc in processing_docs:
            print(f"   ID: {doc.id} - {doc.titulo} ({doc.tipo})")

    db_session.close()

    print("\n" + "=" * 80)
    print("✅ DIAGNÓSTICO COMPLETADO")
    print("=" * 80)

if __name__ == "__main__":
    check_vector_store_sync()
