import secrets
import hashlib
from typing import Optional
from datetime import datetime, timedelta

import bcrypt
from fastapi import Request

from database import get_db
from models import User, AuthSession, PremiumUnlock


def hash_password(password: str) -> str:
    """Hash a password using bcrypt"""
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')


def verify_password(password: str, password_hash: str) -> bool:
    """Verify a password against its hash"""
    return bcrypt.checkpw(password.encode('utf-8'), password_hash.encode('utf-8'))


def generate_session_token() -> str:
    """Generate a secure random session token"""
    return secrets.token_urlsafe(32)


def hash_document(text: str) -> str:
    """Create a hash of document text for tracking premium unlocks"""
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def create_user(email: str, password: str) -> Optional[User]:
    """Create a new user"""
    db = get_db()
    if db is None:
        return None

    try:
        user = User(
            email=email.lower().strip(),
            password_hash=hash_password(password)
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return user
    except Exception as e:
        print(f"Error creating user: {e}")
        db.rollback()
        return None
    finally:
        db.close()


def get_user_by_email(email: str) -> Optional[User]:
    """Get a user by email"""
    db = get_db()
    if db is None:
        return None

    try:
        user = db.query(User).filter(User.email == email.lower().strip()).first()
        return user
    except Exception as e:
        print(f"Error getting user: {e}")
        return None
    finally:
        db.close()


def create_session(user_id: int) -> Optional[str]:
    """Create a new auth session and return the token"""
    db = get_db()
    if db is None:
        return None

    try:
        token = generate_session_token()
        session = AuthSession(
            user_id=user_id,
            token=token,
            expires_at=datetime.utcnow() + timedelta(days=30)
        )
        db.add(session)
        db.commit()
        return token
    except Exception as e:
        print(f"Error creating session: {e}")
        db.rollback()
        return None
    finally:
        db.close()


def get_user_from_token(token: str) -> Optional[User]:
    """Get user from session token"""
    if not token:
        return None

    db = get_db()
    if db is None:
        return None

    try:
        session = db.query(AuthSession).filter(
            AuthSession.token == token,
            AuthSession.expires_at > datetime.utcnow()
        ).first()
        if session:
            return db.query(User).filter(User.id == session.user_id).first()
        return None
    except Exception as e:
        print(f"Error getting user from token: {e}")
        return None
    finally:
        db.close()


def delete_session(token: str) -> bool:
    """Delete a session (logout)"""
    db = get_db()
    if db is None:
        return False

    try:
        db.query(AuthSession).filter(AuthSession.token == token).delete()
        db.commit()
        return True
    except Exception as e:
        print(f"Error deleting session: {e}")
        db.rollback()
        return False
    finally:
        db.close()


def add_credits_to_user(user_id: int, credits: int) -> bool:
    """Add credits to a user account"""
    db = get_db()
    if db is None:
        return False

    try:
        user = db.query(User).filter(User.id == user_id).first()
        if user:
            user.credits += credits
            db.commit()
            return True
        return False
    except Exception as e:
        print(f"Error adding credits: {e}")
        db.rollback()
        return False
    finally:
        db.close()


def use_credit(user_id: int, document_hash: str) -> bool:
    """Use a credit to unlock a document. Returns True if successful."""
    db = get_db()
    if db is None:
        return False

    try:
        user = db.query(User).filter(User.id == user_id).first()
        if not user or user.credits < 1:
            return False

        # Check if already unlocked
        existing = db.query(PremiumUnlock).filter(
            PremiumUnlock.user_id == user_id,
            PremiumUnlock.document_hash == document_hash
        ).first()
        if existing:
            return True  # Already unlocked, no credit needed

        # Deduct credit and record unlock
        user.credits -= 1
        unlock = PremiumUnlock(user_id=user_id, document_hash=document_hash)
        db.add(unlock)
        db.commit()
        return True
    except Exception as e:
        print(f"Error using credit: {e}")
        db.rollback()
        return False
    finally:
        db.close()


def check_premium_access(user_id: int, document_hash: str) -> bool:
    """Check if user has premium access to a document"""
    db = get_db()
    if db is None:
        return False

    try:
        unlock = db.query(PremiumUnlock).filter(
            PremiumUnlock.user_id == user_id,
            PremiumUnlock.document_hash == document_hash
        ).first()
        return unlock is not None
    except Exception as e:
        print(f"Error checking premium access: {e}")
        return False
    finally:
        db.close()


def get_current_user(request: Request) -> Optional[User]:
    """Extract current user from auth header or cookie"""
    # Try Authorization header first
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header[7:]
        return get_user_from_token(token)

    # Try cookie
    token = request.cookies.get("auth_token")
    if token:
        return get_user_from_token(token)

    return None
