# app/services/rag_system.py
import asyncio
import os
from typing import List, Optional, Dict, Any
import logging
from datetime import datetime

from langchain_core.prompts import PromptTemplate
from langchain_openai import ChatOpenAI
from langchain_core.documents import Document

from app.services.document_cache_manager import DocumentCacheManager
from app.repositories.informacion_gez_repository import InformacionGezRepository
from app.models.informacion_gez import TblInformacionGez
from config.database import get_db_session

logger = logging.getLogger(__name__)

class ChatbotRAGSystem:
    """Sistema RAG principal para el chatbot BIM"""
    
    def __init__(self, openai_api_key: str = None, vector_store_path: str = None):
        self.openai_api_key = openai_api_key or os.getenv('OPENAI_API_KEY')
        
        # Inicializar componentes
        self.document_manager = DocumentCacheManager(
            vector_store_path=vector_store_path,
            openai_api_key=self.openai_api_key
        )
        
        # LLM
        self.llm = ChatOpenAI(
            openai_api_key=self.openai_api_key,
            model="gpt-4",
            temperature=0.3,
            max_tokens=1000
        )
        
        # Template para respuestas
        self.prompt_template = PromptTemplate(
            input_variables=["context", "question"],
            template="""Eres ABI (Asistente BIM), el asistente BIM para orientación sobre la implementación de BIM en el Estado peruano.

Contexto relevante:
{context}

Pregunta del usuario: {question}

Instrucciones de personalidad:
- Me llamo ABI y soy el asistente BIM para orientación sobre la implementación de BIM en el Estado peruano
- Puedo ser gracioso y dar respuestas coloquiales
- Usar emojis al inicio o final de la respuesta, pero no en todos los párrafos
- Mantener respuestas breves y directas
- Siempre incluir el link https://mef.gob.pe/planbimperu para mayor información sobre el tema consultado
- NO terminar con punto (.) la última oración. Si tiene varios párrafos, usar punto seguido/aparte en todos excepto el último
- Al finalizar respuesta sobre trámites, preguntar: "¿Te puedo ayudar en otra consulta?"
- Responder basándose únicamente en el contexto proporcionado
- Si la información no está disponible en el contexto, indicar que no tengo esa información específica
- Si mencionas normativas o decretos, incluir números exactos cuando estén disponibles

Respuesta:"""
        )
        
        # Contador de mensajes no comprendidos por sesión
        self.failed_attempts = {}
    
    def get_welcome_message(self) -> Dict[str, Any]:
        """Obtiene el mensaje proactivo de bienvenida"""
        return {
            "answer": "Hola 👋, me llamo ABI y soy el asistente BIM para orientación sobre la implementación de BIM en el Estado peruano. ¿En qué te ayudo?",
            "sources": [],
            "confidence": "high",
            "message_type": "welcome"
        }
    
    async def answer_query(self, user_query: str, session_id: str = None) -> Dict[str, Any]:
        """
        Responde a una consulta del usuario usando RAG
        
        Args:
            user_query: Pregunta del usuario
            session_id: ID de sesión para contexto
            
        Returns:
            Diccionario con respuesta y metadatos
        """
        try:
            logger.info(f"📥 NEW USER QUERY - Query: '{user_query[:100]}...' | Session: {session_id}")

            # 1. PRIMERO: Buscar directamente en vector store (más preciso)
            logger.info("🔎 STEP 1: Searching in vector store for relevant chunks...")
            relevant_chunks = self.document_manager.search_similar_chunks(
                user_query, k=8  # Más chunks para mejor contexto
            )
            
            db_session = get_db_session()
            repo = InformacionGezRepository(db_session)
            
            # 2. Si hay chunks del vector store, extraer los documentos fuente
            relevant_records = []
            if relevant_chunks:
                logger.info(f"📚 STEP 2: Extracting source documents from {len(relevant_chunks)} chunks...")

                # Obtener IDs únicos de documentos fuente
                source_ids = list(set(
                    chunk.metadata.get('source_id')
                    for chunk in relevant_chunks
                    if chunk.metadata.get('source_id')
                ))

                logger.info(f"   Found {len(source_ids)} unique source document IDs: {source_ids}")

                # Obtener información de los documentos fuente
                for source_id in source_ids:
                    record = repo.find_by_id(source_id)
                    if record:
                        relevant_records.append(record)
                        logger.info(f"   ✅ Loaded source doc ID {source_id}: '{record.titulo}' (Type: {record.tipo}, Link: {record.link})")
            
            # 3. Si no hay chunks en vector store, buscar en BD como fallback
            if not relevant_chunks:
                logger.warning("⚠️ STEP 3: No vector store results found! Falling back to database search...")
                relevant_records = repo.search_by_content(user_query, limit=5)

                if not relevant_records:
                    logger.warning("   ⚠️ No content match in DB, using cached documents as last resort...")
                    relevant_records = repo.find_cached_documents()[:3]
                    logger.info(f"   Using {len(relevant_records)} cached documents as fallback")

                # Procesar documentos si es necesario
                await self._ensure_documents_processed(relevant_records, db_session)

                # Buscar chunks después del procesamiento
                for record in relevant_records:
                    if record.cache_status == 'cached' and record.vector_store_id:
                        logger.info(f"   Searching chunks from fallback doc ID {record.id}: '{record.titulo}'")
                        chunks = self.document_manager.search_similar_chunks(
                            user_query, k=3,
                            filter_metadata={"source_id": record.id}
                        )
                        relevant_chunks.extend(chunks)
            
            # 4. Verificar que tenemos contenido para responder
            if not relevant_chunks and not relevant_records:
                return self._handle_no_understanding(user_query, session_id)
            
            # 5. Preparar contexto para el LLM
            if relevant_chunks:
                # PRIORIZAR chunks del vector store (más relevantes)
                context = "\n\n".join([chunk.page_content for chunk in relevant_chunks[:8]])
                sources = self._extract_sources_from_chunks(relevant_chunks)
                logger.info(f"📝 STEP 4: Building context from {len(relevant_chunks)} VECTOR STORE chunks (best quality)")
                logger.info(f"   Context length: {len(context)} characters")
                logger.info(f"   Sources identified: {[s.get('titulo', 'Unknown') for s in sources]}")
            else:
                # Fallback: usar contenido básico de BD
                context = "\n\n".join([
                    f"Documento: {record.titulo}\n{record.contenido_procesado or 'Sin contenido procesado'}"
                    for record in relevant_records
                    if record.contenido_procesado
                ])
                sources = [{"titulo": r.titulo, "link": r.link, "tipo": r.tipo} for r in relevant_records]
                logger.warning(f"⚠️ STEP 4: Building context from {len(relevant_records)} DATABASE RECORDS (fallback mode)")
                logger.info(f"   Context length: {len(context)} characters")

            # 4. Generar respuesta con LLM
            logger.info("🤖 STEP 5: Generating response with OpenAI GPT-4...")
            logger.info(f"   Using model: gpt-4 | Temperature: 0.3 | Max tokens: 1000")
            logger.info(f"   Context preview: '{context[:200]}...'")

            prompt = self.prompt_template.format(
                context=context,
                question=user_query
            )

            response = await self._generate_response(prompt)

            logger.info(f"✅ RESPONSE GENERATED - Length: {len(response)} characters")
            logger.info(f"   Response preview: '{response[:150]}...'")
            logger.info(f"   📊 SUMMARY - Used {len(sources)} sources from {'VECTOR STORE' if relevant_chunks else 'DATABASE FALLBACK'}")
            
            # Resetear intentos fallidos ya que se comprendió el mensaje
            self._reset_failed_attempts(session_id)

            db_session.close()

            # Log final con resumen completo
            logger.info("=" * 80)
            logger.info("📊 FINAL ANSWER SUMMARY")
            logger.info(f"   Source type: {'VECTOR STORE (Cached Documents)' if relevant_chunks else 'DATABASE (Fallback)'}")
            logger.info(f"   Total chunks used: {len(relevant_chunks)}")
            logger.info(f"   Total source documents: {len(relevant_records)}")
            logger.info(f"   Document titles: {[r.titulo for r in relevant_records]}")
            logger.info(f"   Confidence level: {'HIGH' if relevant_chunks else 'MEDIUM'}")
            logger.info(f"   Response sent to user (first 200 chars): '{response[:200]}...'")
            logger.info("=" * 80)

            return {
                "answer": response,
                "sources": sources,
                "confidence": "high" if relevant_chunks else "medium",
                "processed_documents": len(relevant_records)
            }
            
        except Exception as e:
            logger.error(f"Error in answer_query: {e}")
            return {
                "answer": "🤖 Lo siento, ocurrió un error procesando tu consulta. Por favor intenta nuevamente.",
                "sources": [],
                "confidence": "error",
                "error": str(e)
            }
    
    async def _ensure_documents_processed(self, records: List[TblInformacionGez], db_session):
        """Asegura que los documentos estén procesados y cacheados"""
        tasks = []
        for record in records:
            if record.cache_status == 'not_cached':
                logger.info(f"Processing document {record.id}: {record.titulo}")
                task = self.document_manager.process_document(record, db_session)
                tasks.append(task)
        
        if tasks:
            # Procesar en paralelo con límite
            semaphore = asyncio.Semaphore(2)  # Máximo 2 documentos simultáneos
            
            async def process_with_semaphore(task):
                async with semaphore:
                    return await task
            
            results = await asyncio.gather(*[process_with_semaphore(task) for task in tasks], 
                                          return_exceptions=True)
            
            logger.info(f"Processed {len([r for r in results if r is True])} documents successfully")
    
    def _handle_no_understanding(self, user_query: str, session_id: str = None) -> Dict[str, Any]:
        """Maneja casos donde no se comprende el mensaje del usuario"""
        session_key = session_id or "default"
        
        # Incrementar contador de intentos fallidos para esta sesión
        if session_key not in self.failed_attempts:
            self.failed_attempts[session_key] = 0
        
        self.failed_attempts[session_key] += 1
        
        # Primer intento fallido
        if self.failed_attempts[session_key] == 1:
            return {
                "answer": "Disculpa, no te entendí. Vuelve a indicarme tu mensaje",
                "sources": [],
                "confidence": "low",
                "failed_attempts": 1
            }
        
        # Segundo intento fallido
        elif self.failed_attempts[session_key] >= 2:
            return {
                "answer": "Por ahora no puedo ayudarte con ese tema, pero puedes comunicarte a planbimperu@mef.gob.pe 📩 para que un compañero pueda ayudarte",
                "sources": [],
                "confidence": "low", 
                "failed_attempts": self.failed_attempts[session_key]
            }
    
    def _reset_failed_attempts(self, session_id: str = None):
        """Resetea el contador de intentos fallidos cuando se comprende un mensaje"""
        session_key = session_id or "default"
        if session_key in self.failed_attempts:
            self.failed_attempts[session_key] = 0
    
    async def _generate_response(self, prompt: str) -> str:
        """Genera respuesta usando el LLM"""
        try:
            response = await asyncio.to_thread(self.llm.invoke, prompt)
            return response.content.strip()
        except Exception as e:
            logger.error(f"Error generating response: {e}")
            return "🤖 Lo siento, no pude generar una respuesta en este momento."
    
    def _extract_sources_from_chunks(self, chunks: List[Document]) -> List[Dict[str, str]]:
        """Extrae información de fuentes desde chunks"""
        sources_seen = set()
        sources = []
        
        for chunk in chunks:
            metadata = chunk.metadata
            source_key = f"{metadata.get('titulo', '')}_{metadata.get('source_id', '')}"
            
            if source_key not in sources_seen:
                sources_seen.add(source_key)
                sources.append({
                    "titulo": metadata.get('titulo', 'Sin título'),
                    "tipo": metadata.get('source_type', 'Desconocido'),
                    "categoria": metadata.get('categoria', '')
                })
        
        return sources
    
    async def process_single_document_by_id(self, document_id: int) -> Dict[str, Any]:
        """
        Procesa un documento específico por su ID

        Args:
            document_id: ID del documento a procesar

        Returns:
            Diccionario con resultado del procesamiento
        """
        try:
            db_session = get_db_session()
            repo = InformacionGezRepository(db_session)

            # Obtener documento por ID
            document = repo.find_by_id(document_id)

            if not document:
                db_session.close()
                return {"success": False, "error": "Document not found"}

            if not document.activo:
                db_session.close()
                return {"success": False, "error": "Document is not active"}

            if document.tipo not in ['web', 'pdf']:
                db_session.close()
                return {"success": False, "error": "Document type must be 'web' or 'pdf'"}

            logger.info(f"Processing single document: ID={document_id}, title={document.titulo}")

            # Procesar el documento
            try:
                result = await self.document_manager.process_document(document, db_session)

                db_session.close()

                if result:
                    return {
                        "success": True,
                        "document": {
                            "id": document.id,
                            "titulo": document.titulo,
                            "tipo": document.tipo,
                            "cache_status": document.cache_status,
                            "chunks_count": document.chunks_count,
                            "last_processed": document.last_processed.isoformat() if document.last_processed else None
                        },
                        "message": "Document processed successfully"
                    }
                else:
                    return {
                        "success": False,
                        "error": "Processing failed, check logs for details"
                    }

            except Exception as e:
                db_session.close()
                logger.error(f"Error processing document {document_id}: {e}")
                return {
                    "success": False,
                    "error": str(e)
                }

        except Exception as e:
            logger.error(f"Error in process_single_document_by_id: {e}")
            return {"success": False, "error": str(e)}

    async def process_pending_documents(self, batch_size: int = 5) -> Dict[str, Any]:
        """
        Procesa documentos pendientes en lotes
        Útil para ejecutar como tarea programada
        """
        try:
            db_session = get_db_session()
            repo = InformacionGezRepository(db_session)

            # Obtener documentos pendientes
            pending_docs = repo.find_for_processing(batch_size)

            if not pending_docs:
                return {"processed_count": 0, "failed_count": 0, "message": "No hay documentos pendientes"}

            logger.info(f"Processing {len(pending_docs)} pending documents")

            # Procesar uno por uno para capturar errores individuales
            processed_details = []
            successful = 0
            failed = 0

            for doc in pending_docs:
                try:
                    result = await self.document_manager.process_document(doc, db_session)
                    if result:
                        successful += 1
                        status = "success"
                    else:
                        failed += 1
                        status = "failed"

                    processed_details.append({
                        "id": doc.id,
                        "title": doc.titulo,
                        "status": status,
                        "chunks_created": doc.chunks_count if result else 0
                    })

                except Exception as e:
                    failed += 1
                    logger.error(f"Error processing document {doc.id}: {e}")
                    processed_details.append({
                        "id": doc.id,
                        "title": doc.titulo,
                        "status": "error",
                        "error": str(e),
                        "chunks_created": 0
                    })

            db_session.close()

            processing_time = 0  # Placeholder - podrías agregar un timer si quieres

            return {
                "processed_count": successful,
                "failed_count": failed,
                "processing_time": processing_time,
                "documents_processed": processed_details,
                "success_rate": f"{(successful/len(pending_docs)*100):.1f}%" if pending_docs else "0%"
            }

        except Exception as e:
            logger.error(f"Error processing pending documents: {e}")
            return {"error": str(e), "processed_count": 0, "failed_count": 0}
    
    async def clear_all_processing(self, clear_vector_store: bool = True, clear_file_cache: bool = True, reset_type: str = "all") -> Dict[str, Any]:
        """
        Limpia todos los procesamientos: vector store, cache de archivos y resetea estados en BD
        
        Args:
            clear_vector_store: Si limpiar el vector store (ChromaDB)
            clear_file_cache: Si limpiar cache de archivos descargados
            reset_type: Tipo de reset - "all", "errors", "web", "pdf"
            
        Returns:
            Diccionario con resultados de la limpieza
        """
        try:
            db_session = get_db_session()
            repo = InformacionGezRepository(db_session)
            
            results = {
                "vector_store_cleared": False,
                "file_cache_cleared": {"success": False},
                "database_reset": 0,
                "errors": []
            }
            
            # 1. Limpiar vector store si se solicita
            if clear_vector_store:
                try:
                    vector_cleared = self.document_manager.clear_vector_store()
                    results["vector_store_cleared"] = vector_cleared
                    if vector_cleared:
                        logger.info("Vector store cleared successfully")
                except Exception as e:
                    error_msg = f"Error clearing vector store: {e}"
                    logger.error(error_msg)
                    results["errors"].append(error_msg)
            
            # 2. Limpiar cache de archivos si se solicita
            if clear_file_cache:
                try:
                    cache_result = self.document_manager.clear_file_cache()
                    results["file_cache_cleared"] = cache_result
                    if cache_result["success"]:
                        logger.info(f"File cache cleared: {cache_result['files_removed']} files, {cache_result['size_freed_mb']} MB freed")
                except Exception as e:
                    error_msg = f"Error clearing file cache: {e}"
                    logger.error(error_msg)
                    results["errors"].append(error_msg)
            
            # 3. Resetear estados en base de datos
            try:
                if reset_type == "all":
                    reset_count = repo.reset_all_processing_status()
                elif reset_type == "errors":
                    reset_count = repo.reset_error_documents()
                elif reset_type in ["web", "pdf"]:
                    reset_count = repo.reset_processing_status_by_type(reset_type)
                else:
                    raise ValueError(f"Invalid reset_type: {reset_type}. Must be 'all', 'errors', 'web', or 'pdf'")
                
                results["database_reset"] = reset_count
                logger.info(f"Database reset completed: {reset_count} documents reset ({reset_type})")
                
            except Exception as e:
                error_msg = f"Error resetting database: {e}"
                logger.error(error_msg)
                results["errors"].append(error_msg)
            
            db_session.close()
            
            # Determinar si fue exitoso en general
            results["success"] = len(results["errors"]) == 0
            results["message"] = "Processing cleared successfully" if results["success"] else "Processing cleared with some errors"
            
            return results
            
        except Exception as e:
            logger.error(f"Error in clear_all_processing: {e}")
            return {
                "success": False,
                "error": str(e),
                "vector_store_cleared": False,
                "file_cache_cleared": {"success": False},
                "database_reset": 0
            }
    
    def get_system_stats(self) -> Dict[str, Any]:
        """Obtiene estadísticas del sistema RAG"""
        try:
            db_session = get_db_session()
            repo = InformacionGezRepository(db_session)
            
            db_stats = repo.get_cache_stats()
            cache_stats = self.document_manager.downloader.get_cache_stats()
            
            db_session.close()
            
            return {
                "database": db_stats,
                "file_cache": cache_stats,
                "vector_store_path": self.document_manager.vector_store_path,
                "last_update": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error getting system stats: {e}")
            return {"error": str(e)}