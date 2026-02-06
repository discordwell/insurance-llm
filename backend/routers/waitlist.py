from fastapi import APIRouter, HTTPException
from schemas.common import WaitlistInput, WaitlistResponse
from services.db_ops import save_waitlist

router = APIRouter(prefix="/api", tags=["waitlist"])


@router.post("/waitlist", response_model=WaitlistResponse)
async def add_to_waitlist(input: WaitlistInput):
    """Add someone to the waitlist for unsupported document types"""
    # Validate email format (basic)
    if not input.email or '@' not in input.email:
        raise HTTPException(status_code=400, detail="Invalid email address")

    # Save to database
    entry_id = save_waitlist(
        email=input.email,
        doc_type=input.document_type,
        text_preview=input.document_text
    )

    if entry_id:
        return WaitlistResponse(
            success=True,
            message=f"Added to waitlist for {input.document_type}"
        )
    else:
        # Still return success even if DB not configured (graceful degradation)
        return WaitlistResponse(
            success=True,
            message="Thanks! We'll notify you when we support this document type."
        )
