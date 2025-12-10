#!/usr/bin/env python3
"""
Script para verificar un documento específico en la BD
"""

import sys
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

from config.database import get_db_session
from app.repositories.informacion_gez_repository import InformacionGezRepository

def check_document(doc_id):
    """Verifica un documento específico"""

    db_session = get_db_session()
    repo = InformacionGezRepository(db_session)

    doc = repo.find_by_id(doc_id)

    if not doc:
        print(f"❌ Documento ID {doc_id} no encontrado")
        return

    print("=" * 80)
    print(f"📄 DOCUMENTO ID: {doc_id}")
    print("=" * 80)
    print(f"Título: {doc.titulo}")
    print(f"Tipo: {doc.tipo}")
    print(f"Categoría: {doc.categoria}")
    print(f"Link: {doc.link}")
    print(f"Tags: {doc.tags}")
    print(f"Prioridad: {doc.prioridad}")
    print(f"Activo: {doc.activo}")
    print(f"\nEstado de Cache:")
    print(f"  Cache status: {doc.cache_status}")
    print(f"  Chunks count: {doc.chunks_count}")
    print(f"  Vector store ID: {doc.vector_store_id}")
    print(f"  Last processed: {doc.last_processed}")
    print(f"\nContenido procesado:")
    if doc.contenido_procesado:
        preview = doc.contenido_procesado[:500]
        print(f"  Longitud: {len(doc.contenido_procesado)} caracteres")
        print(f"  Preview: {preview}...")
    else:
        print("  (Sin contenido procesado)")

    print("\n" + "=" * 80)

    # Verificar si el link es PDF directo
    if doc.link:
        is_pdf_direct = doc.link.lower().endswith('.pdf')
        print(f"\n🔍 ANÁLISIS DE URL:")
        print(f"  Es PDF directo: {'✅ SÍ' if is_pdf_direct else '❌ NO (página web con PDF)'}")
        print(f"  URL: {doc.link}")

        if not is_pdf_direct and doc.tipo == 'pdf':
            print(f"\n⚠️ PROBLEMA DETECTADO:")
            print(f"  - Tipo configurado: 'pdf'")
            print(f"  - URL real: página web (no PDF directo)")
            print(f"  - Sistema procesará como web scraping")
            print(f"  - SOLUCIÓN: Cambiar tipo a 'web' o usar URL directa del PDF")

    db_session.close()

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python scripts/check_document.py <document_id>")
        sys.exit(1)

    doc_id = int(sys.argv[1])
    check_document(doc_id)
