# app/models/web_chat_message.py
from sqlalchemy import Column, Integer, String, Text, DateTime, JSON, ForeignKey, func
from config.database import Base

class TblWebChatMessage(Base):
    __tablename__ = 'web_chat_messages'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(Integer, ForeignKey('web_chat_sessions.id'), nullable=False)
    message_type = Column(String(20), nullable=False)  # 'user', 'assistant'
    content = Column(Text, nullable=False)
    timestamp = Column(DateTime, server_default=func.now())
    message_metadata = Column(JSON, nullable=True)
    response_time_ms = Column(Integer, nullable=True)
    tokens_used = Column(Integer, nullable=True)
    informacion_gez_ids = Column(JSON, nullable=True)  # Cambiado a JSON para compatibilidad
    
    def __repr__(self):
        return f"<TblWebChatMessage(id={self.id}, type='{self.message_type}', session_id={self.session_id})>"