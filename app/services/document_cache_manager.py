# app/services/document_cache_manager.py
import os
import uuid
import asyncio
from pathlib import Path
from datetime import datetime
from typing import List, Optional, Dict, Any
import logging

from langchain_community.document_loaders import PyPDFLoader, WebBaseLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document
from langchain_community.vectorstores import Chroma
from langchain_openai import OpenAIEmbeddings
import requests
import html2text
from bs4 import BeautifulSoup
import chromadb
from chromadb.config import Settings

from app.services.document_downloader import SmartDownloader
from app.models.informacion_gez import TblInformacionGez

logger = logging.getLogger(__name__)

class DocumentCacheManager:
    """Gestor de cache con chunking y vectorización"""
    
    def __init__(self, vector_store_path: str = None, openai_api_key: str = None):
        self.vector_store_path = vector_store_path or os.getenv('VECTOR_STORE_PATH', './cache/vector_store')
        self.downloader = SmartDownloader()
        
        # Configurar embeddings
        self.embeddings = OpenAIEmbeddings(
            openai_api_key=openai_api_key or os.getenv('OPENAI_API_KEY')
        )
        
        # Configurar text splitter (base)
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200,
            length_function=len,
            separators=["\n\n", "\n", " ", ""]
        )
        
        # Text splitter para documentos grandes (chunks más grandes)
        self.large_text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=2000,  # Chunks más grandes
            chunk_overlap=300,
            length_function=len,
            separators=["\n\n", "\n", " ", ""]
        )
        
        # Vector store (se inicializa cuando se necesita)
        self._vector_store = None
    
    @property
    def vector_store(self):
        """Lazy loading del vector store"""
        if self._vector_store is None:
            Path(self.vector_store_path).mkdir(parents=True, exist_ok=True)

            # Configurar cliente ChromaDB con settings explícitos
            chroma_client = chromadb.PersistentClient(
                path=self.vector_store_path,
                settings=Settings(
                    anonymized_telemetry=False,
                    allow_reset=True
                )
            )

            self._vector_store = Chroma(
                client=chroma_client,
                embedding_function=self.embeddings
            )
        return self._vector_store
    
    async def process_document(self, record: TblInformacionGez, db_session) -> bool:
        """
        Procesa un documento: descarga, chunking y vectorización
        
        Args:
            record: Registro de informacion_gez
            db_session: Sesión de BD para updates
            
        Returns:
            True si el procesamiento fue exitoso
        """
        try:
            # Marcar como procesando
            record.cache_status = 'processing'
            db_session.commit()
            
            logger.info(f"Processing document {record.id}: {record.titulo}")
            
            # Detectar tipo real basado en URL
            is_pdf_url = record.link and record.link.lower().endswith('.pdf')
            
            # Procesar según tipo real
            if record.tipo == 'pdf' and is_pdf_url:
                chunks = await self._process_pdf_document(record)
            elif record.tipo == 'pdf' and not is_pdf_url:
                # PDF listado como PDF pero URL no es PDF directo, tratar como web
                logger.info(f"Document {record.id} marked as PDF but URL is web page, processing as web")
                chunks = await self._process_web_document(record)
            elif record.tipo == 'web':
                chunks = await self._process_web_document(record)
            elif record.tipo == 'consulta_previa':
                # Para consultas previas, usar el contenido procesado existente
                chunks = await self._process_text_content(record)
            else:
                logger.warning(f"Unsupported document type: {record.tipo}")
                record.cache_status = 'error'
                db_session.commit()
                return False
            
            if not chunks:
                logger.error(f"No chunks generated for document {record.id}")
                record.cache_status = 'error'
                db_session.commit()
                return False
            
            # Generar ID único para el vector store
            vector_store_id = f"doc_{record.id}_{uuid.uuid4().hex[:8]}"
            
            # Agregar metadatos a cada chunk (filtrar valores None)
            for chunk in chunks:
                metadata = {
                    "source_id": record.id,
                    "source_type": record.tipo or "unknown",
                    "titulo": record.titulo or "Sin título",
                    "categoria": record.categoria or "general",
                    "vector_store_id": vector_store_id
                }
                
                # Solo agregar tags si no es None
                if record.tags:
                    metadata["tags"] = str(record.tags)
                
                chunk.metadata.update(metadata)
            
            # Agregar al vector store en lotes para evitar límite de tokens
            batch_size = 50  # Lotes de 50 chunks
            for i in range(0, len(chunks), batch_size):
                batch = chunks[i:i+batch_size]
                try:
                    self.vector_store.add_documents(batch)
                    logger.info(f"Processed batch {i//batch_size + 1}/{(len(chunks)-1)//batch_size + 1} ({len(batch)} chunks)")
                    
                    # Pequeño delay entre lotes para no sobrecargar OpenAI
                    if len(chunks) > batch_size:
                        await asyncio.sleep(1)
                        
                except Exception as e:
                    if "max_tokens_per_request" in str(e):
                        # Si aún es muy grande, reducir lote a la mitad
                        smaller_batch_size = max(1, batch_size // 2)
                        logger.warning(f"Batch too large, trying smaller batch size: {smaller_batch_size}")
                        
                        for j in range(i, min(i + batch_size, len(chunks)), smaller_batch_size):
                            smaller_batch = chunks[j:j+smaller_batch_size]
                            try:
                                self.vector_store.add_documents(smaller_batch)
                                await asyncio.sleep(0.5)
                            except Exception as e2:
                                logger.error(f"Failed to process chunk batch {j}: {e2}")
                                # Si falla individualmente, procesar uno por uno
                                for chunk in smaller_batch:
                                    try:
                                        self.vector_store.add_documents([chunk])
                                    except Exception as e3:
                                        logger.error(f"Failed to process individual chunk: {e3}")
                    else:
                        logger.error(f"Error processing batch {i//batch_size + 1}: {e}")
                        raise e
            
            # Actualizar registro en BD
            record.cache_status = 'cached'
            record.last_processed = datetime.now()
            record.chunks_count = len(chunks)
            record.vector_store_id = vector_store_id
            db_session.commit()
            
            logger.info(f"Successfully processed document {record.id} with {len(chunks)} chunks")
            return True
            
        except Exception as e:
            logger.error(f"Error processing document {record.id}: {e}")
            record.cache_status = 'error'
            db_session.commit()
            return False
    
    async def _process_pdf_document(self, record: TblInformacionGez) -> List[Document]:
        """Procesa documento PDF"""
        try:
            # Descargar PDF
            pdf_path = await self.downloader.get_or_download_file(record.link, record.id)
            if not pdf_path:
                raise Exception("Failed to download PDF")
            
            # Cargar PDF con PyPDF
            loader = PyPDFLoader(pdf_path)
            documents = loader.load()
            
            if not documents:
                raise Exception("No content extracted from PDF")
            
            # Chunking
            chunks = self.text_splitter.split_documents(documents)
            logger.info(f"Generated {len(chunks)} chunks from PDF {record.titulo}")
            
            return chunks
            
        except Exception as e:
            logger.error(f"Error processing PDF {record.id}: {e}")
            return []
    
    async def _process_web_document(self, record: TblInformacionGez) -> List[Document]:
        """Procesa documento web"""
        try:
            # Hacer scraping de la página
            content = await self._scrape_web_content(record.link)
            if not content:
                raise Exception("Failed to scrape web content")
            
            # Crear documento
            document = Document(
                page_content=content,
                metadata={
                    "source": record.link,
                    "title": record.titulo
                }
            )
            
            # Chunking - usar splitter apropiado según tamaño del documento
            if len(content) > 100000:  # Si el documento es muy grande (>100KB)
                logger.info(f"Large document detected ({len(content)} chars), using large chunk splitter")
                chunks = self.large_text_splitter.split_documents([document])
            else:
                chunks = self.text_splitter.split_documents([document])
            logger.info(f"Generated {len(chunks)} chunks from web page {record.titulo}")
            
            # Si hay demasiados chunks, filtrar solo contenido relevante a BIM
            if len(chunks) > 1000:  # Si más de 1000 chunks
                logger.warning(f"Document has {len(chunks)} chunks, filtering for BIM-related content")
                filtered_chunks = self._filter_bim_relevant_chunks(chunks)
                logger.info(f"Filtered down to {len(filtered_chunks)} relevant chunks")
                chunks = filtered_chunks
            
            return chunks
            
        except Exception as e:
            logger.error(f"Error processing web document {record.id}: {e}")
            return []
    
    async def _scrape_web_content(self, url: str) -> Optional[str]:
        """Extrae contenido limpio de página web con técnicas anti-bot"""
        try:
            logger.info(f"🌐 Starting web scraping for URL: {url}")

            # Headers completos para simular navegador real
            headers = {
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.9,es;q=0.8',
                'Accept-Encoding': 'gzip, deflate, br',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
                'Sec-Fetch-Dest': 'document',
                'Sec-Fetch-Mode': 'navigate',
                'Sec-Fetch-Site': 'none',
                'Sec-Fetch-User': '?1',
                'Cache-Control': 'max-age=0',
                'DNT': '1',
                'Referer': 'https://www.google.com/'
            }

            # Pequeño delay para no parecer bot
            import random
            await asyncio.sleep(random.uniform(1.0, 3.0))

            # Usar session con cookies y redirects
            session = requests.Session()
            session.headers.update(headers)

            response = session.get(url, timeout=30, allow_redirects=True)
            response.raise_for_status()

            logger.info(f"   HTTP Status: {response.status_code}")
            logger.info(f"   Content-Type: {response.headers.get('Content-Type', 'Unknown')}")
            logger.info(f"   Content-Length: {len(response.content)} bytes")

            # Parsear HTML
            soup = BeautifulSoup(response.content, 'html.parser')

            # Buscar enlaces a PDF embebidos
            pdf_links = []
            for link in soup.find_all(['a', 'iframe', 'embed', 'object']):
                href = link.get('href') or link.get('src') or link.get('data')
                if href and '.pdf' in href.lower():
                    pdf_links.append(href)

            if pdf_links:
                logger.warning(f"⚠️ FOUND {len(pdf_links)} EMBEDDED PDF LINKS in page:")
                for pdf_link in pdf_links:
                    logger.warning(f"   - {pdf_link}")
                logger.warning(f"   Consider using the direct PDF URL instead of the web page")

            # Remover scripts y estilos
            for script in soup(["script", "style"]):
                script.decompose()

            # Convertir a texto limpio
            h = html2text.HTML2Text()
            h.ignore_links = True
            h.ignore_images = True
            text = h.handle(str(soup))

            # Limpiar texto
            lines = text.split('\n')
            cleaned_lines = []
            for line in lines:
                line = line.strip()
                if line and not line.startswith('#'):  # Evitar headers de markdown vacíos
                    cleaned_lines.append(line)

            cleaned_text = '\n'.join(cleaned_lines)
            logger.info(f"   ✅ Scraped {len(cleaned_text)} characters from web page")
            logger.info(f"   Preview: '{cleaned_text[:200]}...'")

            if len(cleaned_text) < 100:
                logger.error(f"   ❌ WARNING: Very short content extracted ({len(cleaned_text)} chars). Page might be protected or have embedded PDF.")

            return cleaned_text
            
        except Exception as e:
            logger.error(f"Error scraping {url}: {e}")
            # Si falla, intentar con técnica alternativa para sitios protegidos
            if 'mef.gob.pe' in url or 'incapsula' in str(e).lower():
                logger.info(f"Intentando bypass para sitio protegido: {url}")
                return await self._scrape_protected_site(url)
            return None
    
    async def _scrape_protected_site(self, url: str) -> Optional[str]:
        """Técnica especial para sitios con Incapsula/Cloudflare"""
        try:
            import subprocess
            import tempfile
            
            # Usar curl con headers específicos
            curl_headers = [
                '-H', 'User-Agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                '-H', 'Accept: text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                '-H', 'Accept-Language: en-US,en;q=0.5',
                '-H', 'Accept-Encoding: gzip, deflate',
                '-H', 'Connection: keep-alive',
                '-H', 'Upgrade-Insecure-Requests: 1',
                '--compressed',
                '--location',  # Seguir redirects
                '--max-redirs', '10',
                '--connect-timeout', '30',
                '--max-time', '60',
                '--cookie-jar', '/tmp/cookies.txt',  # Mantener cookies
                '--cookie', '/tmp/cookies.txt'
            ]
            
            # Ejecutar curl
            result = subprocess.run(
                ['curl', '-s'] + curl_headers + [url],
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if result.returncode == 0 and result.stdout:
                content = result.stdout
                
                # Si aún contiene Incapsula, extraer lo que podamos
                if 'incapsula' in content.lower() or 'blocked' in content.lower():
                    logger.warning(f"Sitio aún bloqueado: {url}")
                    # Buscar cualquier contenido útil en el HTML
                    from bs4 import BeautifulSoup
                    soup = BeautifulSoup(content, 'html.parser')
                    
                    # Extraer cualquier texto visible
                    for script in soup(["script", "style", "iframe"]):
                        script.decompose()
                    
                    text = soup.get_text(separator=' ', strip=True)
                    return text[:500] if len(text) > 50 else None  # Solo si hay contenido mínimo
                
                # Procesar contenido normal
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(content, 'html.parser')
                
                for script in soup(["script", "style"]):
                    script.decompose()
                
                import html2text
                h = html2text.HTML2Text()
                h.ignore_links = True
                h.ignore_images = True
                text = h.handle(str(soup))
                
                lines = [line.strip() for line in text.split('\n') if line.strip()]
                return '\n'.join(lines)
            
            return None
            
        except Exception as e:
            logger.error(f"Error en bypass para sitio protegido {url}: {e}")
            return None
    
    def _filter_bim_relevant_chunks(self, chunks: List[Document]) -> List[Document]:
        """Filtra chunks para mantener solo contenido relevante a BIM"""
        bim_keywords = [
            'bim', 'building information modeling', 'modelado', 'construcción',
            'arquitectura', 'ingeniería', 'infraestructura', 'proyecto',
            'diseño', 'planificación', 'gestión', 'coordinación',
            'colaboración', 'multidisciplinar', 'interoperabilidad',
            'revit', 'autocad', 'tekla', 'bentley', 'archicad',
            'ifc', 'cad', '3d', 'modelo', 'digital',
            'estándar', 'normativa', 'protocolo', 'metodología',
            'ciclo de vida', 'mantenimiento', 'operación',
            'perú', 'estado', 'público', 'gobierno', 'mef',
            'productividad', 'competitividad', 'innovación',
            'tecnología', 'digitalización', 'transformación'
        ]
        
        relevant_chunks = []
        
        for chunk in chunks:
            content = chunk.page_content.lower()
            
            # Contar cuántas keywords BIM contiene
            keyword_count = sum(1 for keyword in bim_keywords if keyword in content)
            
            # Si tiene al menos 2 keywords BIM o es un chunk corto, mantenerlo
            if keyword_count >= 2 or len(content) < 200:
                relevant_chunks.append(chunk)
            
            # Limitar a máximo 500 chunks incluso después del filtrado
            if len(relevant_chunks) >= 500:
                break
        
        return relevant_chunks
    
    def search_similar_chunks(self, query: str, k: int = 8, filter_metadata: dict = None) -> List[Document]:
        """
        Busca chunks similares usando el vector store

        Args:
            query: Consulta de búsqueda
            k: Número de resultados
            filter_metadata: Filtros adicionales

        Returns:
            Lista de documentos similares
        """
        try:
            logger.info(f"🔍 VECTOR STORE SEARCH - Query: '{query[:80]}...' | Requesting k={k} chunks | Filters: {filter_metadata}")

            if filter_metadata:
                results = self.vector_store.similarity_search(
                    query, k=k, filter=filter_metadata
                )
            else:
                results = self.vector_store.similarity_search(query, k=k)

            logger.info(f"✅ VECTOR STORE RESULTS - Found {len(results)} chunks")

            # Log detallado de cada chunk encontrado
            for i, chunk in enumerate(results, 1):
                source_id = chunk.metadata.get('source_id', 'Unknown')
                titulo = chunk.metadata.get('titulo', 'Sin título')
                tipo = chunk.metadata.get('source_type', 'Unknown')
                preview = chunk.page_content[:100].replace('\n', ' ')

                logger.info(f"  📄 Chunk {i}/{len(results)} - Doc ID: {source_id} | Type: {tipo} | Title: '{titulo}' | Preview: '{preview}...'")

            return results

        except Exception as e:
            logger.error(f"❌ ERROR in similarity search: {e}")
            return []
    
    async def _process_text_content(self, record: TblInformacionGez) -> List[Document]:
        """Procesa contenido de texto directo (para consultas previas)"""
        try:
            if not record.contenido_procesado:
                raise Exception("No content available for processing")
            
            # Crear documento desde contenido existente
            document = Document(
                page_content=record.contenido_procesado,
                metadata={
                    "source": "database_content",
                    "title": record.titulo
                }
            )
            
            # Chunking
            chunks = self.text_splitter.split_documents([document])
            logger.info(f"Generated {len(chunks)} chunks from text content {record.titulo}")
            
            return chunks
            
        except Exception as e:
            logger.error(f"Error processing text content {record.id}: {e}")
            return []
    
    def clear_vector_store(self) -> bool:
        """
        Limpia completamente el vector store eliminando todos los documentos
        y recreando el directorio
        
        Returns:
            True si la limpieza fue exitosa
        """
        try:
            import shutil
            
            # Cerrar vector store actual si existe
            if self._vector_store is not None:
                self._vector_store = None
            
            # Eliminar directorio completo del vector store
            if Path(self.vector_store_path).exists():
                shutil.rmtree(self.vector_store_path)
                logger.info(f"Removed vector store directory: {self.vector_store_path}")
            
            # Recrear directorio vacío
            Path(self.vector_store_path).mkdir(parents=True, exist_ok=True)
            logger.info(f"Recreated empty vector store directory: {self.vector_store_path}")
            
            return True
            
        except Exception as e:
            logger.error(f"Error clearing vector store: {e}")
            return False
    
    def clear_file_cache(self) -> Dict[str, Any]:
        """
        Limpia el cache de archivos descargados
        
        Returns:
            Estadísticas de la limpieza
        """
        try:
            files_removed = 0
            total_size_mb = 0
            
            if self.downloader.cache_dir.exists():
                for file_path in self.downloader.cache_dir.glob("*"):
                    if file_path.is_file():
                        file_size = file_path.stat().st_size
                        total_size_mb += file_size / (1024 * 1024)
                        file_path.unlink()
                        files_removed += 1
                        
                logger.info(f"Removed {files_removed} files from cache ({total_size_mb:.2f} MB)")
            
            return {
                "files_removed": files_removed,
                "size_freed_mb": round(total_size_mb, 2),
                "success": True
            }
            
        except Exception as e:
            logger.error(f"Error clearing file cache: {e}")
            return {
                "files_removed": 0,
                "size_freed_mb": 0,
                "success": False,
                "error": str(e)
            }
