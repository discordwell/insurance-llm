from datetime import datetime
from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, JSON, Boolean, ForeignKey
from sqlalchemy.orm import declarative_base, sessionmaker, relationship
from config import DATABASE_URL

Base = declarative_base()
db_engine = None
SessionLocal = None


def init_db():
    global db_engine, SessionLocal
    if DATABASE_URL:
        db_url = DATABASE_URL.replace("postgres://", "postgresql://", 1)
        db_engine = create_engine(db_url)
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=db_engine)
        try:
            Base.metadata.create_all(bind=db_engine)
            print("Database initialized successfully")
        except Exception as e:
            print(f"Database table creation failed (will retry on first request): {e}")
        return True
    else:
        print("DATABASE_URL not set - running without database storage")
        return False


def get_db():
    if SessionLocal is None:
        return None
    db = SessionLocal()
    try:
        return db
    except:
        db.close()
        raise
