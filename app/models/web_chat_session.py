# app/models/web_chat_session.py
from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, JSON, func
from config.database import Base

class TblWebChatSession(Base):
    __tablename__ = 'web_chat_sessions'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    session_token = Column(String(255), unique=True, nullable=False)
    user_ip = Column(String(45), nullable=True)
    user_agent = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True)
    started_at = Column(DateTime, server_default=func.now())
    last_activity = Column(DateTime, server_default=func.now(), onupdate=func.now())
    ended_at = Column(DateTime, nullable=True)
    message_count = Column(Integer, default=0)
    context_data = Column(JSON, nullable=True)
    
    def __repr__(self):
        return f"<TblWebChatSession(id={self.id}, token='{self.session_token[:8]}...', active={self.is_active})>"