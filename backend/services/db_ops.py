from database import get_db
from models import Upload, Waitlist


def save_upload(doc_type: str, text: str, state: str = None, analysis: dict = None, user_agent: str = None, user_id: int = None):
    """Save an upload to the database"""
    db = get_db()
    if db is None:
        return None  # No database configured

    try:
        upload = Upload(
            document_type=doc_type,
            document_text=text,
            text_length=len(text),
            state=state,
            analysis_result=analysis,
            overall_risk=analysis.get("overall_risk") if analysis else None,
            risk_score=analysis.get("risk_score") if analysis else None,
            red_flag_count=len(analysis.get("red_flags", [])) if analysis else None,
            user_agent=user_agent,
            user_id=user_id
        )
        db.add(upload)
        db.commit()
        db.refresh(upload)
        return upload.id
    except Exception as e:
        print(f"Error saving upload: {e}")
        db.rollback()
        return None
    finally:
        db.close()


def save_waitlist(email: str, doc_type: str, text_preview: str = None):
    """Save a waitlist signup"""
    db = get_db()
    if db is None:
        return None

    try:
        entry = Waitlist(
            email=email,
            document_type=doc_type,
            document_text_preview=text_preview[:500] if text_preview else None
        )
        db.add(entry)
        db.commit()
        db.refresh(entry)
        return entry.id
    except Exception as e:
        print(f"Error saving waitlist: {e}")
        db.rollback()
        return None
    finally:
        db.close()
