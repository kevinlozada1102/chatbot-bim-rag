# app/models/informacion_gez.py
from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, JSON, func
from config.database import Base

class TblInformacionGez(Base):
    __tablename__ = 'informacion_gez'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    tipo = Column(String(20), nullable=False)  # 'web', 'pdf', 'consulta_previa'
    categoria = Column(String(50), nullable=True)  # 'pagina_principal', 'recursos', 'faq'
    titulo = Column(String(255), nullable=True)
    link = Column(Text, nullable=True)  # URL o path del archivo
    contenido_procesado = Column(Text, nullable=True)  # Contenido procesado/chunkeado
    tags = Column(JSON, nullable=True)  # Tags para búsqueda
    prioridad = Column(Integer, default=3)  # 1-5, mayor = más prioritario
    activo = Column(Boolean, default=True)
    # Campos para sistema de cache RAG
    cache_status = Column(String(20), default='not_cached')  # 'not_cached', 'processing', 'cached', 'error'
    last_processed = Column(DateTime, nullable=True)
    chunks_count = Column(Integer, default=0)
    vector_store_id = Column(String(255), nullable=True)  # ID en el vector store
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    
    def __repr__(self):
        return f"<TblInformacionGez(id={self.id}, tipo='{self.tipo}', titulo='{self.titulo}', cache_status='{self.cache_status}')>"