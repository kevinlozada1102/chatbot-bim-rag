# config/database.py
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session, declarative_base
import os
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

# Base para modelos
Base = declarative_base()

# Obtener DATABASE_URL directamente o construirla desde componentes
DATABASE_URL = os.getenv('DATABASE_URL')

# Si no existe DATABASE_URL completa, construirla desde componentes individuales
if not DATABASE_URL:
    DB_HOST = os.getenv('DB_HOST')
    DB_PORT = os.getenv('DB_PORT')
    DB_USER = os.getenv('DB_USER')
    DB_PASSWORD = os.getenv('DB_PASSWORD')
    DB_NAME = os.getenv('DB_NAME')
    DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

# Crear engine
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    echo=False  # Sin debug por defecto
)

# Crear sessionmaker
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Función para obtener sesión de BD
def get_db_session() -> Session:
    """Genera una sesión de base de datos"""
    db = SessionLocal()
    return db