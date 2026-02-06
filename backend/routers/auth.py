from fastapi import APIRouter, HTTPException, Request, Response
from services.auth import (create_user, get_user_by_email, verify_password,
                           create_session, delete_session, get_current_user)
from schemas.auth import SignupInput, LoginInput, AuthResponse
from database import get_db
from models import Upload

router = APIRouter(prefix="/api", tags=["auth"])


@router.post("/auth/signup", response_model=AuthResponse)
async def signup(input: SignupInput, response: Response):
    """Create a new user account"""
    # Validate email format
    if not input.email or '@' not in input.email:
        raise HTTPException(status_code=400, detail="Invalid email address")

    # Validate password
    if not input.password or len(input.password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters")

    # Check if user already exists
    existing = get_user_by_email(input.email)
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    # Create user
    user = create_user(input.email, input.password)
    if not user:
        raise HTTPException(status_code=500, detail="Failed to create account")

    # Create session
    token = create_session(user.id)
    if not token:
        raise HTTPException(status_code=500, detail="Failed to create session")

    # Set cookie
    response.set_cookie(
        key="auth_token",
        value=token,
        httponly=True,
        max_age=30 * 24 * 60 * 60,  # 30 days
        samesite="lax"
    )

    return AuthResponse(
        success=True,
        message="Account created successfully",
        user={"email": user.email, "credits": user.credits},
        token=token
    )


@router.post("/auth/login", response_model=AuthResponse)
async def login(input: LoginInput, response: Response):
    """Log in to existing account"""
    # Get user
    user = get_user_by_email(input.email)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid email or password")

    # Verify password
    if not verify_password(input.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    # Create session
    token = create_session(user.id)
    if not token:
        raise HTTPException(status_code=500, detail="Failed to create session")

    # Set cookie
    response.set_cookie(
        key="auth_token",
        value=token,
        httponly=True,
        max_age=30 * 24 * 60 * 60,  # 30 days
        samesite="lax"
    )

    return AuthResponse(
        success=True,
        message="Logged in successfully",
        user={"email": user.email, "credits": user.credits},
        token=token
    )


@router.post("/auth/logout")
async def logout(request: Request, response: Response):
    """Log out (delete session)"""
    token = request.cookies.get("auth_token")
    if token:
        delete_session(token)

    response.delete_cookie("auth_token")
    return {"success": True, "message": "Logged out"}


@router.get("/auth/me")
async def get_me(request: Request):
    """Get current user info"""
    user = get_current_user(request)
    if not user:
        return {"authenticated": False, "user": None}

    return {
        "authenticated": True,
        "user": {
            "email": user.email,
            "credits": user.credits,
            "created_at": user.created_at.isoformat() if user.created_at else None
        }
    }


@router.get("/user/history")
async def get_user_history(request: Request):
    """Get user's document analysis history"""
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")

    db = get_db()
    if db is None:
        return {"uploads": []}

    try:
        uploads = db.query(Upload).filter(
            Upload.user_id == user.id
        ).order_by(Upload.created_at.desc()).limit(50).all()

        return {
            "uploads": [
                {
                    "id": u.id,
                    "created_at": u.created_at.isoformat() if u.created_at else None,
                    "document_type": u.document_type,
                    "overall_risk": u.overall_risk,
                    "risk_score": u.risk_score
                }
                for u in uploads
            ]
        }
    except Exception as e:
        print(f"Error fetching history: {e}")
        return {"uploads": []}
    finally:
        db.close()
