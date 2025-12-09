#!/usr/bin/env python3
"""
Chatbot BIM RAG - Backend API
Flask REST API para el sistema de chatbot BIM con RAG
"""

import os
import sys
import logging
import asyncio
from pathlib import Path
from datetime import datetime
from typing import Dict, Any

# Agregar el directorio actual al path
sys.path.insert(0, str(Path(__file__).parent))

from flask import Flask, request, jsonify
from flask_cors import CORS
from flask_socketio import SocketIO, emit
from dotenv import load_dotenv

# Importar componentes del proyecto
from config.database import engine, Base, get_db_session
from app.services.rag_system import ChatbotRAGSystem
from app.repositories.informacion_gez_repository import InformacionGezRepository
from app.models.web_chat_session import TblWebChatSession
from app.models.web_chat_message import TblWebChatMessage
from app.models.informacion_gez import TblInformacionGez

# Cargar variables de entorno
load_dotenv()

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Crear tablas si no existen
try:
    Base.metadata.create_all(bind=engine)
    logger.info("✅ Database tables verified/created")
except Exception as e:
    logger.error(f"❌ Database connection error: {e}")
    sys.exit(1)

# Inicializar Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'chatbot-bim-secret-key-2024')

# Habilitar CORS para permitir requests desde frontend
CORS(app)

# Inicializar SocketIO
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

# Inicializar sistema RAG
try:
    rag_system = ChatbotRAGSystem()
    logger.info("✅ RAG System initialized")
except Exception as e:
    logger.error(f"❌ Error initializing RAG system: {e}")
    rag_system = None

# ============== API ENDPOINTS ==============

@app.route('/api/health', methods=['GET'])
def health_check():
    """Endpoint de salud del sistema"""
    try:
        # Verificar conexión a BD
        db_session = get_db_session()
        db_session.execute("SELECT 1")
        db_session.close()
        db_status = "OK"
    except Exception as e:
        db_status = f"Error: {str(e)}"
    
    # Verificar RAG system
    rag_status = "OK" if rag_system else "Not initialized"
    
    return jsonify({
        "status": "running",
        "timestamp": datetime.now().isoformat(),
        "database": db_status,
        "rag_system": rag_status,
        "version": "1.0.0"
    })

@app.route('/api/stats', methods=['GET'])
def get_system_stats():
    """API para obtener estadísticas del sistema"""
    if not rag_system:
        return jsonify({"error": "RAG system not initialized"}), 500
    
    try:
        stats = rag_system.get_system_stats()
        return jsonify(stats)
    except Exception as e:
        logger.error(f"Error getting stats: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/welcome', methods=['GET'])
def get_welcome_message():
    """Obtener mensaje de bienvenida proactivo de ABI"""
    if not rag_system:
        return jsonify({"error": "RAG system not initialized"}), 500
    
    try:
        welcome_msg = rag_system.get_welcome_message()
        return jsonify({
            "success": True,
            "message": welcome_msg,
            "timestamp": datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Error getting welcome message: {e}")
        return jsonify({"error": f"Failed to get welcome message: {str(e)}"}), 500

@app.route('/api/chat', methods=['POST'])
def chat_query():
    """Endpoint principal para consultas del chatbot"""
    if not rag_system:
        return jsonify({"error": "RAG system not initialized"}), 500
    
    try:
        # Obtener datos del request
        data = request.get_json()
        if not data or 'message' not in data:
            return jsonify({"error": "Message is required"}), 400
        
        user_message = data.get('message', '').strip()
        session_id = data.get('session_id')
        
        if not user_message:
            return jsonify({"error": "Message cannot be empty"}), 400
        
        logger.info(f"Processing chat query: {user_message[:100]}...")
        
        # Crear event loop para async
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        # Procesar consulta con RAG
        result = loop.run_until_complete(
            rag_system.answer_query(user_message, session_id=session_id)
        )
        
        # Guardar en BD si se proporciona session_id
        if session_id:
            save_chat_message(user_message, result, session_id)
        
        return jsonify({
            "success": True,
            "response": result,
            "timestamp": datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Error processing chat query: {e}")
        return jsonify({"error": f"Failed to process query: {str(e)}"}), 500

@app.route('/api/session', methods=['POST'])
def create_chat_session():
    """Crear nueva sesión de chat"""
    try:
        data = request.get_json() or {}
        
        db_session = get_db_session()
        
        # Crear nueva sesión
        import uuid
        session_token = str(uuid.uuid4())
        
        new_session = TblWebChatSession(
            session_token=session_token,
            user_ip=request.remote_addr,
            user_agent=request.headers.get('User-Agent', ''),
            context_data=data.get('context', {})
        )
        
        db_session.add(new_session)
        db_session.commit()
        db_session.refresh(new_session)
        
        session_id = new_session.id
        db_session.close()
        
        return jsonify({
            "success": True,
            "session_id": session_id,
            "session_token": session_token,
            "timestamp": datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Error creating session: {e}")
        return jsonify({"error": f"Failed to create session: {str(e)}"}), 500

@app.route('/api/session/<int:session_id>/messages', methods=['GET'])
def get_session_messages(session_id):
    """Obtener mensajes de una sesión"""
    try:
        db_session = get_db_session()
        
        messages = db_session.query(TblWebChatMessage).filter(
            TblWebChatMessage.session_id == session_id
        ).order_by(TblWebChatMessage.timestamp).all()
        
        result = []
        for msg in messages:
            result.append({
                "id": msg.id,
                "type": msg.message_type,
                "content": msg.content,
                "timestamp": msg.timestamp.isoformat() if msg.timestamp else None,
                "metadata": msg.message_metadata
            })
        
        db_session.close()
        
        return jsonify({
            "success": True,
            "session_id": session_id,
            "messages": result
        })
        
    except Exception as e:
        logger.error(f"Error getting messages: {e}")
        return jsonify({"error": f"Failed to get messages: {str(e)}"}), 500

@app.route('/api/documents', methods=['GET'])
def get_documents():
    """Obtener lista de documentos en el sistema"""
    try:
        db_session = get_db_session()
        repo = InformacionGezRepository(db_session)

        # Parámetros de filtrado opcionales
        tipo = request.args.get('tipo')
        categoria = request.args.get('categoria')
        cache_status = request.args.get('cache_status')
        activo = request.args.get('activo', 'true').lower() == 'true'

        # Aplicar filtros según parámetros
        if tipo:
            documents = repo.find_by_tipo(tipo)
        elif categoria:
            documents = repo.find_by_categoria(categoria)
        elif cache_status:
            documents = repo.find_by_cache_status(cache_status)
        else:
            # Filtrar por activo o todos
            if activo:
                documents = repo.find_all_active()
            else:
                documents = db_session.query(TblInformacionGez).order_by(
                    TblInformacionGez.prioridad.desc(),
                    TblInformacionGez.created_at
                ).all()

        result = []
        for doc in documents:
            result.append({
                "id": doc.id,
                "tipo": doc.tipo,
                "categoria": doc.categoria,
                "titulo": doc.titulo,
                "link": doc.link,
                "tags": doc.tags,
                "prioridad": doc.prioridad,
                "activo": doc.activo,
                "cache_status": doc.cache_status,
                "chunks_count": doc.chunks_count,
                "last_processed": doc.last_processed.isoformat() if doc.last_processed else None,
                "created_at": doc.created_at.isoformat() if doc.created_at else None,
                "updated_at": doc.updated_at.isoformat() if doc.updated_at else None
            })

        db_session.close()

        return jsonify({
            "success": True,
            "total": len(result),
            "documents": result
        })

    except Exception as e:
        logger.error(f"Error getting documents: {e}")
        return jsonify({"error": f"Failed to get documents: {str(e)}"}), 500

@app.route('/api/documents/<int:document_id>', methods=['GET'])
def get_document_by_id(document_id):
    """Obtener un documento específico por ID"""
    try:
        db_session = get_db_session()
        repo = InformacionGezRepository(db_session)

        document = repo.find_by_id(document_id)

        if not document:
            db_session.close()
            return jsonify({"error": "Document not found"}), 404

        result = {
            "id": document.id,
            "tipo": document.tipo,
            "categoria": document.categoria,
            "titulo": document.titulo,
            "link": document.link,
            "contenido_procesado": document.contenido_procesado,
            "tags": document.tags,
            "prioridad": document.prioridad,
            "activo": document.activo,
            "cache_status": document.cache_status,
            "chunks_count": document.chunks_count,
            "vector_store_id": document.vector_store_id,
            "last_processed": document.last_processed.isoformat() if document.last_processed else None,
            "created_at": document.created_at.isoformat() if document.created_at else None,
            "updated_at": document.updated_at.isoformat() if document.updated_at else None
        }

        db_session.close()

        return jsonify({
            "success": True,
            "document": result
        })

    except Exception as e:
        logger.error(f"Error getting document: {e}")
        return jsonify({"error": f"Failed to get document: {str(e)}"}), 500

@app.route('/api/documents', methods=['POST'])
def create_document():
    """Crear un nuevo documento"""
    try:
        data = request.get_json()

        # Validar campos requeridos
        if not data or 'tipo' not in data:
            return jsonify({"error": "Field 'tipo' is required"}), 400

        # Validar tipo
        valid_tipos = ['web', 'pdf', 'consulta_previa']
        if data['tipo'] not in valid_tipos:
            return jsonify({"error": f"Invalid tipo. Must be one of: {', '.join(valid_tipos)}"}), 400

        db_session = get_db_session()

        # Crear nuevo documento
        new_document = TblInformacionGez(
            tipo=data['tipo'],
            categoria=data.get('categoria'),
            titulo=data.get('titulo'),
            link=data.get('link'),
            contenido_procesado=data.get('contenido_procesado'),
            tags=data.get('tags'),
            prioridad=data.get('prioridad', 3),
            activo=data.get('activo', True)
        )

        db_session.add(new_document)
        db_session.commit()
        db_session.refresh(new_document)

        result = {
            "id": new_document.id,
            "tipo": new_document.tipo,
            "categoria": new_document.categoria,
            "titulo": new_document.titulo,
            "link": new_document.link,
            "tags": new_document.tags,
            "prioridad": new_document.prioridad,
            "activo": new_document.activo,
            "cache_status": new_document.cache_status,
            "created_at": new_document.created_at.isoformat() if new_document.created_at else None
        }

        db_session.close()

        return jsonify({
            "success": True,
            "message": "Document created successfully",
            "document": result
        }), 201

    except Exception as e:
        logger.error(f"Error creating document: {e}")
        return jsonify({"error": f"Failed to create document: {str(e)}"}), 500

@app.route('/api/documents/<int:document_id>', methods=['PUT'])
def update_document(document_id):
    """Actualizar un documento existente"""
    try:
        data = request.get_json()

        if not data:
            return jsonify({"error": "No data provided"}), 400

        db_session = get_db_session()
        repo = InformacionGezRepository(db_session)

        document = repo.find_by_id(document_id)

        if not document:
            db_session.close()
            return jsonify({"error": "Document not found"}), 404

        # Actualizar campos si están presentes en el request
        if 'tipo' in data:
            valid_tipos = ['web', 'pdf', 'consulta_previa']
            if data['tipo'] not in valid_tipos:
                db_session.close()
                return jsonify({"error": f"Invalid tipo. Must be one of: {', '.join(valid_tipos)}"}), 400
            document.tipo = data['tipo']

        if 'categoria' in data:
            document.categoria = data['categoria']

        if 'titulo' in data:
            document.titulo = data['titulo']

        if 'link' in data:
            document.link = data['link']

        if 'contenido_procesado' in data:
            document.contenido_procesado = data['contenido_procesado']

        if 'tags' in data:
            document.tags = data['tags']

        if 'prioridad' in data:
            document.prioridad = data['prioridad']

        if 'activo' in data:
            document.activo = data['activo']

        db_session.commit()
        db_session.refresh(document)

        result = {
            "id": document.id,
            "tipo": document.tipo,
            "categoria": document.categoria,
            "titulo": document.titulo,
            "link": document.link,
            "tags": document.tags,
            "prioridad": document.prioridad,
            "activo": document.activo,
            "cache_status": document.cache_status,
            "chunks_count": document.chunks_count,
            "last_processed": document.last_processed.isoformat() if document.last_processed else None,
            "updated_at": document.updated_at.isoformat() if document.updated_at else None
        }

        db_session.close()

        return jsonify({
            "success": True,
            "message": "Document updated successfully",
            "document": result
        })

    except Exception as e:
        logger.error(f"Error updating document: {e}")
        return jsonify({"error": f"Failed to update document: {str(e)}"}), 500

@app.route('/api/documents/<int:document_id>', methods=['DELETE'])
def delete_document(document_id):
    """Eliminar un documento (soft delete - marca como inactivo)"""
    try:
        db_session = get_db_session()
        repo = InformacionGezRepository(db_session)

        document = repo.find_by_id(document_id)

        if not document:
            db_session.close()
            return jsonify({"error": "Document not found"}), 404

        # Soft delete - marcar como inactivo
        document.activo = False
        db_session.commit()

        db_session.close()

        return jsonify({
            "success": True,
            "message": "Document deleted successfully (marked as inactive)"
        })

    except Exception as e:
        logger.error(f"Error deleting document: {e}")
        return jsonify({"error": f"Failed to delete document: {str(e)}"}), 500

@app.route('/api/documents/<int:document_id>/hard-delete', methods=['DELETE'])
def hard_delete_document(document_id):
    """Eliminar permanentemente un documento de la base de datos"""
    try:
        db_session = get_db_session()
        repo = InformacionGezRepository(db_session)

        document = repo.find_by_id(document_id)

        if not document:
            db_session.close()
            return jsonify({"error": "Document not found"}), 404

        # Hard delete - eliminar permanentemente
        db_session.delete(document)
        db_session.commit()

        db_session.close()

        return jsonify({
            "success": True,
            "message": "Document permanently deleted from database"
        })

    except Exception as e:
        logger.error(f"Error hard deleting document: {e}")
        return jsonify({"error": f"Failed to hard delete document: {str(e)}"}), 500

@app.route('/api/documents/process', methods=['POST'])
def process_documents():
    """Procesar documentos pendientes en lote"""
    if not rag_system:
        return jsonify({"error": "RAG system not initialized"}), 500

    try:
        data = request.get_json() or {}
        batch_size = data.get('batch_size', 3)

        # Crear event loop para async
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        # Procesar documentos
        result = loop.run_until_complete(
            rag_system.process_pending_documents(batch_size)
        )

        return jsonify({
            "success": True,
            "result": result,
            "timestamp": datetime.now().isoformat()
        })

    except Exception as e:
        logger.error(f"Error processing documents: {e}")
        return jsonify({"error": f"Failed to process documents: {str(e)}"}), 500

@app.route('/api/documents/<int:document_id>/process', methods=['POST'])
def process_single_document(document_id):
    """Procesar un documento específico individualmente"""
    if not rag_system:
        return jsonify({"error": "RAG system not initialized"}), 500

    try:
        db_session = get_db_session()
        repo = InformacionGezRepository(db_session)

        document = repo.find_by_id(document_id)

        if not document:
            db_session.close()
            return jsonify({"error": "Document not found"}), 404

        if not document.activo:
            db_session.close()
            return jsonify({"error": "Document is not active"}), 400

        if document.tipo not in ['web', 'pdf']:
            db_session.close()
            return jsonify({"error": "Document type must be 'web' or 'pdf' to be processed"}), 400

        db_session.close()

        # Crear event loop para async
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        # Procesar el documento específico
        result = loop.run_until_complete(
            rag_system.process_single_document_by_id(document_id)
        )

        return jsonify({
            "success": True,
            "document_id": document_id,
            "result": result,
            "timestamp": datetime.now().isoformat()
        })

    except Exception as e:
        logger.error(f"Error processing single document: {e}")
        return jsonify({"error": f"Failed to process document: {str(e)}"}), 500

@app.route('/api/documents/stats', methods=['GET'])
def get_documents_stats():
    """Obtener estadísticas de documentos (cache y procesamiento)"""
    try:
        db_session = get_db_session()
        repo = InformacionGezRepository(db_session)

        stats = repo.get_cache_stats()

        db_session.close()

        return jsonify({
            "success": True,
            "stats": stats,
            "timestamp": datetime.now().isoformat()
        })

    except Exception as e:
        logger.error(f"Error getting documents stats: {e}")
        return jsonify({"error": f"Failed to get documents stats: {str(e)}"}), 500

@app.route('/api/documents/clear', methods=['POST'])
def clear_documents_processing():
    """Limpiar procesamientos de documentos (vector store, cache y estados en BD)"""
    if not rag_system:
        return jsonify({"error": "RAG system not initialized"}), 500
    
    try:
        data = request.get_json() or {}
        
        # Parámetros de limpieza
        clear_vector_store = data.get('clear_vector_store', True)
        clear_file_cache = data.get('clear_file_cache', True) 
        reset_type = data.get('reset_type', 'all')  # 'all', 'errors', 'web', 'pdf'
        
        # Validar reset_type
        valid_reset_types = ['all', 'errors', 'web', 'pdf']
        if reset_type not in valid_reset_types:
            return jsonify({
                "error": f"Invalid reset_type. Must be one of: {', '.join(valid_reset_types)}"
            }), 400
        
        # Crear event loop para async
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        # Ejecutar limpieza
        result = loop.run_until_complete(
            rag_system.clear_all_processing(
                clear_vector_store=clear_vector_store,
                clear_file_cache=clear_file_cache, 
                reset_type=reset_type
            )
        )
        
        return jsonify({
            "success": result.get("success", False),
            "result": result,
            "timestamp": datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Error clearing documents processing: {e}")
        return jsonify({"error": f"Failed to clear processing: {str(e)}"}), 500

# ============== HELPER FUNCTIONS ==============

def save_chat_message(user_message: str, bot_response: Dict[str, Any], session_id: str):
    """Guardar mensaje en base de datos"""
    try:
        logger.info(f"💾 SAVING message to DB - Session: {session_id}, User msg: '{user_message[:50]}...', Bot response: '{bot_response.get('answer', '')[:50]}...'")
        db_session = get_db_session()
        
        # Mensaje del usuario
        user_msg = TblWebChatMessage(
            session_id=int(session_id),
            message_type='user',
            content=user_message,
            message_metadata={}
        )
        db_session.add(user_msg)
        
        # Respuesta del bot
        bot_msg = TblWebChatMessage(
            session_id=int(session_id),
            message_type='assistant',
            content=bot_response.get('answer', ''),
            message_metadata={
                'confidence': bot_response.get('confidence'),
                'sources': bot_response.get('sources', []),
                'processed_documents': bot_response.get('processed_documents', 0)
            }
        )
        db_session.add(bot_msg)
        
        # Actualizar contador de mensajes en sesión
        session = db_session.query(TblWebChatSession).filter(
            TblWebChatSession.id == int(session_id)
        ).first()
        if session:
            session.message_count += 2
        
        db_session.commit()
        db_session.close()
        
    except Exception as e:
        logger.error(f"Error saving chat message: {e}")

# ============== ERROR HANDLERS ==============

@app.errorhandler(404)
def not_found(error):
    return jsonify({"error": "Endpoint not found"}), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({"error": "Internal server error"}), 500

# ============== SOCKETIO EVENTS ==============

@socketio.on('connect')
def handle_connect():
    """Handle client connection"""
    logger.info(f"Client connected: {request.sid}")
    emit('status', {'message': 'Conectado al servidor ABI', 'status': 'connected'})

@socketio.on('disconnect')
def handle_disconnect():
    """Handle client disconnection"""
    logger.info(f"Client disconnected: {request.sid}")

@socketio.on('start_session')
def handle_start_session(data):
    """Handle session start request"""
    try:
        logger.info(f"Starting session for client: {request.sid}")
        
        # Create new session in database
        db_session = get_db_session()
        
        import uuid
        session_token = str(uuid.uuid4())
        
        new_session = TblWebChatSession(
            session_token=session_token,
            user_ip=request.remote_addr,
            user_agent=data.get('user_agent', ''),
            context_data=data
        )
        
        db_session.add(new_session)
        db_session.commit()
        db_session.refresh(new_session)
        
        session_id = new_session.id
        db_session.close()
        
        # Send session info to client
        emit('session_started', {
            'session_token': session_token,
            'session_id': session_id,
            'timestamp': datetime.now().isoformat()
        })
        
        # Enviar mensaje proactivo de bienvenida de ABI
        if rag_system:
            welcome_msg = rag_system.get_welcome_message()
            emit('message', {
                'type': 'assistant',
                'content': welcome_msg['answer'],
                'sources': welcome_msg['sources'],
                'confidence': welcome_msg['confidence'],
                'message_type': 'welcome',
                'timestamp': datetime.now().isoformat()
            })
        
        logger.info(f"Session created: {session_id} for client: {request.sid}")
        
    except Exception as e:
        logger.error(f"Error starting session: {e}")
        emit('error', {'message': f'Error creating session: {str(e)}'})

@socketio.on('send_message')
def handle_user_message(data):
    """Handle user message and generate bot response"""
    try:
        logger.info(f"📥 RECEIVED send_message event with data: {data}")
        
        user_message = data.get('message', '').strip()
        session_token = data.get('session_token')
        
        logger.info(f"📝 Processing message: '{user_message}' from token: {session_token[:8] if session_token else 'None'}...")
        
        if not user_message:
            emit('error', {'message': 'Message cannot be empty'})
            return
        
        if not rag_system:
            emit('error', {'message': 'RAG system not initialized'})
            return
        
        logger.info(f"Processing message from {request.sid}: {user_message[:100]}...")
        
        # Show typing indicator
        emit('typing_indicator', {'typing': True})
        
        # Find session ID from token
        session_id = None
        if session_token:
            db_session = get_db_session()
            session = db_session.query(TblWebChatSession).filter(
                TblWebChatSession.session_token == session_token
            ).first()
            if session:
                session_id = session.id
            db_session.close()
        
        # Create event loop for async RAG call
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        # Process with RAG system
        result = loop.run_until_complete(
            rag_system.answer_query(user_message, session_id=str(session_id) if session_id else None)
        )
        
        # Save messages to database
        if session_id:
            save_chat_message(user_message, result, str(session_id))
        
        # Send bot response
        emit('typing_indicator', {'typing': False})
        emit('message', {
            'type': 'assistant',
            'content': result.get('answer', ''),
            'sources': result.get('sources', []),
            'confidence': result.get('confidence', 'medium'),
            'timestamp': datetime.now().isoformat()
        })
        
        logger.info(f"Response sent to {request.sid}")
        
    except Exception as e:
        logger.error(f"Error processing message: {e}")
        emit('typing_indicator', {'typing': False})
        emit('error', {'message': f'Error processing message: {str(e)}'})

@socketio.on('end_session')
def handle_end_session(data):
    """Handle session end request"""
    try:
        session_token = data.get('session_token')
        
        if session_token:
            db_session = get_db_session()
            session = db_session.query(TblWebChatSession).filter(
                TblWebChatSession.session_token == session_token
            ).first()
            
            if session:
                session.is_active = False
                session.ended_at = datetime.now()
                db_session.commit()
                logger.info(f"Session ended: {session.id}")
            
            db_session.close()
        
        emit('session_ended', {'message': 'Session ended successfully'})
        
    except Exception as e:
        logger.error(f"Error ending session: {e}")
        emit('error', {'message': f'Error ending session: {str(e)}'})

# ============== MAIN ==============

if __name__ == '__main__':
    # Leer puerto de variable de entorno o usar 5001 por defecto
    port = int(os.getenv('APP_PORT', 5001))

    print("🚀 Iniciando Chatbot BIM RAG - Backend API...")
    print(f"📡 API Base URL: http://localhost:{port}")
    print(f"🩺 Health check: http://localhost:{port}/api/health")
    print(f"📊 Stats API: http://localhost:{port}/api/stats")
    print(f"💬 Chat API: POST http://localhost:{port}/api/chat")
    print("=" * 60)

    # Verificar configuración crítica
    if not os.getenv('OPENAI_API_KEY'):
        print("❌ ADVERTENCIA: OPENAI_API_KEY no configurada")

    if not os.getenv('DATABASE_URL'):
        print("❌ ADVERTENCIA: DATABASE_URL no configurada")

    # Iniciar servidor SocketIO
    try:
        socketio.run(
            app,
            debug=os.getenv('FLASK_DEBUG', 'True').lower() == 'true',
            host='0.0.0.0',
            port=port,
            allow_unsafe_werkzeug=True  # Permitir Werkzeug en desarrollo
        )
    except KeyboardInterrupt:
        print("\n👋 Servidor API detenido por el usuario")
    except Exception as e:
        print(f"❌ Error iniciando servidor: {e}")