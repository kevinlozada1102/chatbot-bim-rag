# app/repositories/informacion_gez_repository.py
from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, desc, func
from app.models.informacion_gez import TblInformacionGez

class InformacionGezRepository:
    def __init__(self, db_session: Session):
        self.db_session = db_session
    
    def save(self, info_gez: TblInformacionGez) -> TblInformacionGez:
        """Guarda un nuevo registro de información"""
        self.db_session.add(info_gez)
        self.db_session.commit()
        self.db_session.refresh(info_gez)
        return info_gez
    
    def find_by_id(self, id: int) -> Optional[TblInformacionGez]:
        """Busca por ID"""
        return self.db_session.query(TblInformacionGez).filter(TblInformacionGez.id == id).first()
    
    def find_all_active(self) -> List[TblInformacionGez]:
        """Obtiene todos los registros activos"""
        return self.db_session.query(TblInformacionGez).filter(
            TblInformacionGez.activo == True
        ).order_by(desc(TblInformacionGez.prioridad), TblInformacionGez.created_at).all()
    
    def search_by_content(self, query: str, limit: int = 10) -> List[TblInformacionGez]:
        """Búsqueda de contenido por texto (simple)"""
        return self.db_session.query(TblInformacionGez).filter(
            and_(
                TblInformacionGez.activo == True,
                or_(
                    TblInformacionGez.titulo.ilike(f'%{query}%'),
                    TblInformacionGez.contenido_procesado.ilike(f'%{query}%')
                )
            )
        ).order_by(desc(TblInformacionGez.prioridad)).limit(limit).all()
    
    def find_by_categoria(self, categoria: str) -> List[TblInformacionGez]:
        """Busca por categoría"""
        return self.db_session.query(TblInformacionGez).filter(
            and_(
                TblInformacionGez.activo == True,
                TblInformacionGez.categoria == categoria
            )
        ).order_by(desc(TblInformacionGez.prioridad)).all()
    
    def find_by_tipo(self, tipo: str) -> List[TblInformacionGez]:
        """Busca por tipo (web, pdf, consulta_previa)"""
        return self.db_session.query(TblInformacionGez).filter(
            and_(
                TblInformacionGez.activo == True,
                TblInformacionGez.tipo == tipo
            )
        ).order_by(desc(TblInformacionGez.prioridad)).all()
    
    # Métodos para sistema RAG
    
    def find_not_cached(self, limit: int = 50) -> List[TblInformacionGez]:
        """Encuentra documentos que no han sido procesados para cache"""
        return self.db_session.query(TblInformacionGez).filter(
            and_(
                TblInformacionGez.activo == True,
                TblInformacionGez.cache_status == 'not_cached'
            )
        ).order_by(desc(TblInformacionGez.prioridad)).limit(limit).all()
    
    def find_cached_documents(self) -> List[TblInformacionGez]:
        """Encuentra documentos ya procesados y cacheados"""
        return self.db_session.query(TblInformacionGez).filter(
            and_(
                TblInformacionGez.activo == True,
                TblInformacionGez.cache_status == 'cached'
            )
        ).order_by(desc(TblInformacionGez.prioridad)).all()
    
    def find_by_cache_status(self, status: str) -> List[TblInformacionGez]:
        """Busca por estado de cache"""
        return self.db_session.query(TblInformacionGez).filter(
            and_(
                TblInformacionGez.activo == True,
                TblInformacionGez.cache_status == status
            )
        ).all()
    
    def find_for_processing(self, batch_size: int = 5) -> List[TblInformacionGez]:
        """Encuentra documentos listos para procesamiento RAG"""
        return self.db_session.query(TblInformacionGez).filter(
            and_(
                TblInformacionGez.activo == True,
                or_(
                    TblInformacionGez.cache_status == 'not_cached',
                    TblInformacionGez.cache_status == 'error'
                ),
                TblInformacionGez.tipo.in_(['pdf', 'web'])
            )
        ).order_by(desc(TblInformacionGez.prioridad)).limit(batch_size).all()
    
    def update_contenido(self, id: int, contenido: str) -> bool:
        """Actualiza el contenido procesado"""
        record = self.find_by_id(id)
        if record:
            record.contenido_procesado = contenido
            self.db_session.commit()
            return True
        return False
    
    def get_cache_stats(self) -> dict:
        """Obtiene estadísticas del cache"""
        total = self.db_session.query(TblInformacionGez).filter(
            TblInformacionGez.activo == True
        ).count()
        
        cached = self.db_session.query(TblInformacionGez).filter(
            and_(
                TblInformacionGez.activo == True,
                TblInformacionGez.cache_status == 'cached'
            )
        ).count()
        
        processing = self.db_session.query(TblInformacionGez).filter(
            and_(
                TblInformacionGez.activo == True,
                TblInformacionGez.cache_status == 'processing'
            )
        ).count()
        
        errors = self.db_session.query(TblInformacionGez).filter(
            and_(
                TblInformacionGez.activo == True,
                TblInformacionGez.cache_status == 'error'
            )
        ).count()
        
        return {
            'total_documents': total,
            'cached': cached,
            'processing': processing,
            'errors': errors,
            'not_cached': total - cached - processing - errors
        }
    
    def reset_all_processing_status(self) -> int:
        """Resetea el estado de procesamiento de todos los documentos activos"""
        try:
            updated = self.db_session.query(TblInformacionGez).filter(
                TblInformacionGez.activo == True
            ).update({
                TblInformacionGez.cache_status: 'not_cached',
                TblInformacionGez.last_processed: None,
                TblInformacionGez.chunks_count: 0,
                TblInformacionGez.vector_store_id: None
            })
            
            self.db_session.commit()
            return updated
            
        except Exception as e:
            self.db_session.rollback()
            raise e
    
    def reset_processing_status_by_type(self, doc_type: str) -> int:
        """Resetea el estado de procesamiento de documentos por tipo"""
        try:
            updated = self.db_session.query(TblInformacionGez).filter(
                and_(
                    TblInformacionGez.activo == True,
                    TblInformacionGez.tipo == doc_type
                )
            ).update({
                TblInformacionGez.cache_status: 'not_cached',
                TblInformacionGez.last_processed: None,
                TblInformacionGez.chunks_count: 0,
                TblInformacionGez.vector_store_id: None
            })
            
            self.db_session.commit()
            return updated
            
        except Exception as e:
            self.db_session.rollback()
            raise e
    
    def reset_error_documents(self) -> int:
        """Resetea solo los documentos con estado 'error' para reintento"""
        try:
            updated = self.db_session.query(TblInformacionGez).filter(
                and_(
                    TblInformacionGez.activo == True,
                    TblInformacionGez.cache_status == 'error'
                )
            ).update({
                TblInformacionGez.cache_status: 'not_cached',
                TblInformacionGez.last_processed: None,
                TblInformacionGez.chunks_count: 0,
                TblInformacionGez.vector_store_id: None
            })
            
            self.db_session.commit()
            return updated
            
        except Exception as e:
            self.db_session.rollback()
            raise e
