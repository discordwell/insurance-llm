from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, JSON, Boolean, ForeignKey
from database import Base


class Upload(Base):
    __tablename__ = "uploads"

    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    document_type = Column(String(50), index=True)
    document_text = Column(Text)
    text_length = Column(Integer)
    state = Column(String(10), nullable=True)
    analysis_result = Column(JSON, nullable=True)
    overall_risk = Column(String(20), nullable=True)
    risk_score = Column(Integer, nullable=True)
    red_flag_count = Column(Integer, nullable=True)
    source = Column(String(50), default="web")
    user_agent = Column(String(500), nullable=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)


class Waitlist(Base):
    __tablename__ = "waitlist"

    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    email = Column(String(255), index=True)
    document_type = Column(String(100))
    document_text_preview = Column(Text, nullable=True)
    notified = Column(Boolean, default=False)
    notified_at = Column(DateTime, nullable=True)
