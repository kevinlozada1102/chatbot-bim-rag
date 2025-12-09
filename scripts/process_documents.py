#!/usr/bin/env python3
"""
Script principal para procesar documentos RAG
Uso: python scripts/process_documents.py [--batch-size N] [--stats] [--search "query"]
"""

import sys
import os
import asyncio
import argparse
import logging
from pathlib import Path

# Agregar el directorio raíz al path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Verificar que tenemos OpenAI API Key
if not os.getenv('OPENAI_API_KEY'):
    print("❌ Error: OPENAI_API_KEY no configurada en .env")
    sys.exit(1)

try:
    from config.database import get_db_session
    from app.repositories.informacion_gez_repository import InformacionGezRepository
    from app.services.rag_system import ChatbotRAGSystem
except ImportError as e:
    print(f"❌ Error importando módulos: {e}")
    print("Asegúrate de que estás en el directorio correcto y que las dependencias están instaladas")
    sys.exit(1)

async def process_documents(batch_size: int = 3):
    """Procesa documentos pendientes"""
    try:
        print("🚀 Iniciando procesamiento de documentos BIM...")
        
        # Inicializar sistema RAG
        rag_system = ChatbotRAGSystem()
        
        # Procesar documentos pendientes
        result = await rag_system.process_pending_documents(batch_size)
        
        print(f"✅ Procesamiento completado:")
        print(f"   - Documentos procesados: {result.get('processed', 0)}")
        print(f"   - Total encontrados: {result.get('total', 0)}")
        print(f"   - Tasa de éxito: {result.get('success_rate', 'N/A')}")
        
        if 'error' in result:
            print(f"❌ Error: {result['error']}")
        elif result.get('processed', 0) > 0:
            print("\n🎉 ¡Sistema RAG actualizado! Ahora ABI puede acceder al contenido completo de los PDFs.")
            print("Prueba preguntando: '¿Cuáles son los pasos para la adopción progresiva de BIM?'")
        else:
            print("\n📋 No había documentos pendientes para procesar.")

    except Exception as e:
        print(f"❌ Error en procesamiento: {str(e)}")
        import traceback
        traceback.print_exc()

def get_stats():
    """Obtiene estadísticas del sistema"""
    try:
        print("📊 Obteniendo estadísticas del sistema...")
        
        # Inicializar sistema RAG
        rag_system = ChatbotRAGSystem()
        
        # Obtener estadísticas
        stats = rag_system.get_system_stats()
        
        print("✅ Estadísticas del sistema:")
        print(f"📚 Base de datos:")
        db_stats = stats.get('database', {})
        print(f"   - Total documentos: {db_stats.get('total_documents', 'N/A')}")
        print(f"   - Cacheados: {db_stats.get('cached', 'N/A')}")
        print(f"   - Procesando: {db_stats.get('processing', 'N/A')}")
        print(f"   - Con errores: {db_stats.get('errors', 'N/A')}")
        print(f"   - Sin procesar: {db_stats.get('not_cached', 'N/A')}")
        
        print(f"💾 Cache de archivos:")
        cache_stats = stats.get('file_cache', {})
        print(f"   - Archivos en cache: {cache_stats.get('total_files', 'N/A')}")
        print(f"   - Tamaño total: {cache_stats.get('total_size_mb', 'N/A')} MB")
        print(f"   - Directorio: {cache_stats.get('cache_dir', 'N/A')}")
        
        print(f"🗄️ Vector Store: {stats.get('vector_store_path', 'N/A')}")
        print(f"🕒 Última actualización: {stats.get('last_update', 'N/A')}")

    except Exception as e:
        print(f"❌ Error obteniendo estadísticas: {str(e)}")

async def test_query(query: str):
    """Prueba una consulta con el sistema RAG"""
    try:
        print(f"🔍 Probando consulta: '{query}'")
        
        # Inicializar sistema RAG
        rag_system = ChatbotRAGSystem()
        
        # Hacer consulta
        result = await rag_system.answer_query(query)
        
        print(f"\n🤖 Respuesta de ABI:")
        print(result.get('answer', 'No se pudo generar respuesta'))
        
        print(f"\n📊 Metadatos:")
        print(f"   - Confianza: {result.get('confidence', 'N/A')}")
        print(f"   - Documentos procesados: {result.get('processed_documents', 'N/A')}")
        print(f"   - Fuentes utilizadas: {len(result.get('sources', []))}")
        
        if result.get('sources'):
            print(f"\n📚 Fuentes:")
            for i, source in enumerate(result.get('sources', []), 1):
                print(f"   {i}. {source.get('titulo', 'Sin título')} ({source.get('tipo', 'N/A')})")

    except Exception as e:
        print(f"❌ Error en consulta: {str(e)}")

def show_documents():
    """Muestra los documentos disponibles en la BD"""
    try:
        print("📋 Documentos disponibles en la base de datos:")
        
        db_session = get_db_session()
        repo = InformacionGezRepository(db_session)
        
        docs = repo.find_all_active()
        
        if not docs:
            print("   No hay documentos activos en la BD")
            return
        
        for doc in docs:
            status_icon = {"not_cached": "⏳", "cached": "✅", "processing": "🔄", "error": "❌"}.get(doc.cache_status, "❓")
            print(f"\n{status_icon} ID: {doc.id} | Tipo: {doc.tipo}")
            print(f"   Título: {doc.titulo}")
            print(f"   Cache: {doc.cache_status} | Chunks: {doc.chunks_count}")
            print(f"   Link: {doc.link[:80]}{'...' if len(doc.link) > 80 else ''}")
        
        db_session.close()

    except Exception as e:
        print(f"❌ Error listando documentos: {str(e)}")

def main():
    parser = argparse.ArgumentParser(description='Administrador del sistema RAG para BIM')
    parser.add_argument('--process', action='store_true', help='Procesar documentos pendientes')
    parser.add_argument('--batch-size', type=int, default=3, help='Número de documentos por lote (default: 3)')
    parser.add_argument('--stats', action='store_true', help='Mostrar estadísticas del sistema')
    parser.add_argument('--query', type=str, help='Probar una consulta')
    parser.add_argument('--list', action='store_true', help='Listar documentos en la BD')
    
    args = parser.parse_args()
    
    if not any([args.process, args.stats, args.query, args.list]):
        print("🤖 Administrador del Sistema RAG - Chatbot BIM")
        print("\nOpciones disponibles:")
        print("  --process          Procesar documentos pendientes")
        print("  --stats            Mostrar estadísticas del sistema") 
        print("  --query 'texto'    Probar una consulta")
        print("  --list             Listar documentos en la BD")
        print("\nEjemplos:")
        print("  python scripts/process_documents.py --process")
        print("  python scripts/process_documents.py --query 'pasos adopción BIM'")
        return
    
    # Ejecutar comandos
    if args.list:
        show_documents()
    
    if args.stats:
        get_stats()
    
    if args.process:
        asyncio.run(process_documents(args.batch_size))
    
    if args.query:
        asyncio.run(test_query(args.query))

if __name__ == '__main__':
    main()