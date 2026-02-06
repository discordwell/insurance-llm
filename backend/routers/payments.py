from fastapi import APIRouter, HTTPException, Request
import stripe
from config import STRIPE_SECRET_KEY, STRIPE_WEBHOOK_SECRET
from services.auth import (get_current_user, add_credits_to_user, use_credit,
                           check_premium_access, get_user_by_email)
from schemas.auth import CheckoutInput

router = APIRouter(prefix="/api", tags=["payments"])


@router.post("/create-checkout-session")
async def create_checkout_session(input: CheckoutInput, request: Request):
    """Create a Stripe checkout session for purchasing credits"""
    if not STRIPE_SECRET_KEY:
        raise HTTPException(status_code=500, detail="Stripe not configured")

    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Must be logged in to purchase")

    try:
        # Create checkout session
        checkout_session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            line_items=[
                {
                    "price_data": {
                        "currency": "usd",
                        "product_data": {
                            "name": "Full Report Unlock",
                            "description": "Unlock the complete detailed analysis report"
                        },
                        "unit_amount": 300,  # $3.00 in cents
                    },
                    "quantity": 1,
                }
            ],
            mode="payment",
            success_url=input.success_url + "?session_id={CHECKOUT_SESSION_ID}",
            cancel_url=input.cancel_url,
            metadata={
                "user_id": str(user.id),
                "document_hash": input.document_hash
            }
        )

        return {"checkout_url": checkout_session.url, "session_id": checkout_session.id}

    except Exception as e:
        print(f"Stripe error: {e}")
        raise HTTPException(status_code=500, detail="Failed to create checkout session")


@router.post("/stripe-webhook")
async def stripe_webhook(request: Request):
    """Handle Stripe webhook events"""
    if not STRIPE_SECRET_KEY or not STRIPE_WEBHOOK_SECRET:
        raise HTTPException(status_code=500, detail="Stripe not configured")

    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, STRIPE_WEBHOOK_SECRET
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail="Invalid payload")
    except stripe.error.SignatureVerificationError as e:
        raise HTTPException(status_code=400, detail="Invalid signature")

    # Handle checkout.session.completed
    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        metadata = session.get("metadata", {})

        user_id = metadata.get("user_id")
        document_hash = metadata.get("document_hash")

        if user_id and document_hash:
            # Add credit and unlock document
            add_credits_to_user(int(user_id), 1)
            use_credit(int(user_id), document_hash)
            print(f"Unlocked document {document_hash} for user {user_id}")

    return {"received": True}


@router.post("/unlock-report")
async def unlock_report(request: Request):
    """Use a credit to unlock a report (for users with existing credits)"""
    body = await request.json()
    document_hash = body.get("document_hash")

    if not document_hash:
        raise HTTPException(status_code=400, detail="document_hash required")

    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Must be logged in")

    # Check if already unlocked
    if check_premium_access(user.id, document_hash):
        return {"success": True, "message": "Already unlocked", "credits": user.credits}

    # Try to use a credit
    if use_credit(user.id, document_hash):
        # Refresh user to get updated credits
        refreshed_user = get_user_by_email(user.email)
        return {
            "success": True,
            "message": "Report unlocked",
            "credits": refreshed_user.credits if refreshed_user else user.credits - 1
        }
    else:
        raise HTTPException(status_code=402, detail="No credits available. Please purchase more.")


@router.get("/check-unlock/{document_hash}")
async def check_unlock(document_hash: str, request: Request):
    """Check if user has unlocked a specific document"""
    user = get_current_user(request)
    if not user:
        return {"unlocked": False, "authenticated": False}

    unlocked = check_premium_access(user.id, document_hash)
    return {"unlocked": unlocked, "authenticated": True, "credits": user.credits}
