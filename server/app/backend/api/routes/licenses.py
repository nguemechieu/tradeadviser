"""
License Management API Routes - Purchase, activate, verify, and manage licenses.

Endpoints:
- POST /api/licenses/purchase - Purchase a license
- POST /api/licenses/activate - Activate a license key
- GET /api/licenses/verify - Verify license status
- GET /api/licenses/list - List user's licenses
- POST /api/licenses/renew - Renew expiring license
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query,  BackgroundTasks
from pydantic import BaseModel
from sqlalchemy.orm import Session

from server.app.backend.dependencies import get_db, get_current_user
from server.app.backend.schemas import UserSchema
from server.app.backend.services.license_service import (
    get_license_service,
    LicenseType,
    LICENSE_FEATURES,
    LICENSE_PRICING,
)
from server.app.backend.services.payment_service import (
    get_payment_service,
    PaymentMethod,
    CryptoCurrency,
)
from server.app.backend.services.email_service import get_email_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v3/licenses", tags=["licenses"])


# Request/Response Models

class PurchaseLicenseRequest(BaseModel):
    """Purchase license request."""
    license_type: str  # trial, basic, pro, enterprise
    payment_method: str  # card, paypal, crypto
    card_token: Optional[str] = None  # Required for card payments
    crypto_currency: Optional[str] = None  # Required for crypto payments


class ActivateLicenseRequest(BaseModel):
    """Activate license request."""
    license_key: str
    hardware_id: Optional[str] = None


class VerifyLicenseRequest(BaseModel):
    """Verify license request."""
    license_key: str


# License Purchase & Payment Routes

@router.post("/purchase")
async def purchase_license(
    request: PurchaseLicenseRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: UserSchema = Depends(get_current_user),
):
    """
    Purchase a license.
    
    Supports card (Visa/Mastercard), PayPal, and cryptocurrency payments.
    
    Returns:
        - For card/PayPal: Immediate response with license or payment redirect
        - For crypto: Wallet address to send funds to
    """
    try:
        # Validate license type
        try:
            license_type = LicenseType(request.license_type)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid license type")
        
        # Get pricing
        amount_usd = LICENSE_PRICING.get(license_type)
        if amount_usd is None and license_type != LicenseType.TRIAL:
            raise HTTPException(status_code=400, detail="Enterprise pricing requires contact")
        
        payment_service = get_payment_service()
        license_service = get_license_service(db)
        email_service = get_email_service()
        
        payment_method = PaymentMethod(request.payment_method)
        
        # Process payment based on method
        if payment_method == PaymentMethod.CARD:
            if not request.card_token:
                raise HTTPException(status_code=400, detail="Card token required")
            
            payment_result = payment_service.create_card_payment(
                user_id=current_user.id,
                email=current_user.email,
                amount_usd=amount_usd or 0,
                license_type=request.license_type,
                card_token=request.card_token,
            )
            
            if payment_result["status"] != "completed":
                raise HTTPException(status_code=400, detail="Payment failed")
            
            # Create license after successful payment
            license_data = license_service.create_license(
                user_id=current_user.id,
                email=current_user.email,
                license_type=license_type,
            )
            
            # Send license email in background
            background_tasks.add_task(
                email_service.send_license_email,
                recipient_email=current_user.email,
                license_key=license_data["license_key"],
                license_type=license_data["type"],
                expires_at=license_data["expires_at"],
                features=license_data["features"],
            )
            
            background_tasks.add_task(
                email_service.send_payment_confirmation,
                recipient_email=current_user.email,
                payment_id=payment_result.get("payment_id", ""),
                amount_usd=amount_usd or 0,
                license_type=request.license_type,
                payment_method="card",
            )
            
            logger.info(f"License purchased: {license_data['license_key']} for user {current_user.id}")
            
            return {
                "success": True,
                "message": "License purchased successfully",
                "payment_id": payment_result.get("payment_id"),
                "license_key": license_data["license_key"],
                "expires_at": license_data["expires_at"],
                "features": license_data["features"],
            }
        
        elif payment_method == PaymentMethod.PAYPAL:
            payment_result = payment_service.create_paypal_payment(
                user_id=current_user.id,
                email=current_user.email,
                amount_usd=amount_usd or 0,
                license_type=request.license_type,
            )
            
            if payment_result["status"] == "failed":
                raise HTTPException(status_code=400, detail="Payment request failed")
            
            return {
                "success": True,
                "message": "Redirect to PayPal to complete payment",
                "payment_id": payment_result.get("payment_id"),
                "redirect_url": payment_result.get("redirect_url"),
            }
        
        elif payment_method == PaymentMethod.CRYPTO:
            if not request.crypto_currency:
                raise HTTPException(status_code=400, detail="Crypto currency required")
            
            try:
                crypto = CryptoCurrency(request.crypto_currency.lower())
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid crypto currency")
            
            payment_result = payment_service.create_crypto_payment(
                user_id=current_user.id,
                email=current_user.email,
                amount_usd=amount_usd or 0,
                license_type=request.license_type,
                currency=crypto,
            )
            
            if payment_result["status"] == "failed":
                raise HTTPException(status_code=400, detail="Payment request failed")
            
            return {
                "success": True,
                "message": f"Send {request.crypto_currency.upper()} to complete payment",
                "payment_id": payment_result.get("payment_id"),
                "currency": request.crypto_currency,
                "amount_crypto": payment_result.get("amount_crypto"),
                "amount_usd": amount_usd,
                "wallet_address": payment_result.get("wallet_address"),
                "expires_at": payment_result.get("expires_at"),
            }
    
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"License purchase error: {exc}")
        raise HTTPException(status_code=500, detail="Purchase failed")


# License Activation & Verification Routes

@router.post("/activate")
async def activate_license(
    request: ActivateLicenseRequest,
    db: Session = Depends(get_db),
    current_user: UserSchema = Depends(get_current_user),
):
    """
    Activate a license key on this device.
    
    The license key is sent to the user's email after purchase.
    """
    try:
        license_service = get_license_service(db)
        
        # Get hardware ID from request or generate one
        hardware_id = request.hardware_id or "default_device"
        
        result = license_service.activate_license(
            license_key=request.license_key,
            hardware_id=hardware_id,
        )
        
        if not result["activated"]:
            raise HTTPException(status_code=400, detail=result["message"])
        
        return {
            "success": True,
            "message": result["message"],
            "features": result["features"],
        }
    
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"License activation error: {exc}")
        raise HTTPException(status_code=500, detail="Activation failed")


@router.get("/verify")
async def verify_license(
    license_key: str = Query(..., min_length=20),
    db: Session = Depends(get_db),
):
    """
    Verify a license without requiring authentication.
    
    Returns license status and features.
    """
    try:
        license_service = get_license_service(db)
        result = license_service.check_license_status(license_key)
        
        return result
    
    except Exception as exc:
        logger.error(f"License verification error: {exc}")
        raise HTTPException(status_code=500, detail="Verification failed")


@router.get("/status/{license_key}")
async def get_license_status(
    license_key: str,
    db: Session = Depends(get_db),
    current_user: UserSchema = Depends(get_current_user),
):
    """
    Get detailed license status for the current user.
    """
    try:
        license_service = get_license_service(db)
        result = license_service.check_license_status(license_key)
        
        return {
            **result,
            "license_key": license_key,
        }
    
    except Exception as exc:
        logger.error(f"License status error: {exc}")
        raise HTTPException(status_code=500, detail="Status check failed")


@router.get("/list")
async def list_user_licenses(
    db: Session = Depends(get_db),
    current_user: UserSchema = Depends(get_current_user),
):
    """
    List all licenses for the current user.
    """
    try:
        license_service = get_license_service(db)
        licenses = license_service.get_user_licenses(current_user.id)
        
        return {
            "count": len(licenses),
            "licenses": licenses,
        }
    
    except Exception as exc:
        logger.error(f"License list error: {exc}")
        raise HTTPException(status_code=500, detail="List failed")


@router.post("/renew/{license_key}")
async def renew_license(
    license_key: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: UserSchema = Depends(get_current_user),
):
    """
    Renew an expiring license.
    """
    try:
        license_service = get_license_service(db)
        email_service = get_email_service()
        
        result = license_service.renew_license(license_key)
        
        if not result.get("renewed"):
            raise HTTPException(status_code=400, detail="License renewal failed")
        
        # Send renewal confirmation email
        background_tasks.add_task(
            email_service.send_renewal_invitation,
            recipient_email=current_user.email,
            license_key=license_key,
            license_type="pro",  # TODO: Get actual type from license
        )
        
        return {
            "success": True,
            "message": "License renewed successfully",
            "expires_at": result.get("expires_at"),
        }
    
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"License renewal error: {exc}")
        raise HTTPException(status_code=500, detail="Renewal failed")


@router.post("/revoke/{license_key}")
async def revoke_license(
    license_key: str,
    reason: str = Query("", max_length=500),
    db: Session = Depends(get_db),
    current_user: UserSchema = Depends(get_current_user),
):
    """
    Revoke a license (admin only).
    """
    if current_user.role not in ["admin", "super_admin"]:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    try:
        license_service = get_license_service(db)
        result = license_service.revoke_license(license_key, reason)
        
        if not result.get("revoked"):
            raise HTTPException(status_code=400, detail="Revocation failed")
        
        return {
            "success": True,
            "message": result["message"],
        }
    
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"License revocation error: {exc}")
        raise HTTPException(status_code=500, detail="Revocation failed")


# License Info Routes

@router.get("/pricing")
async def get_pricing():
    """Get license pricing information."""
    pricing = {}
    
    for license_type, price in LICENSE_PRICING.items():
        pricing[license_type.value] = {
            "price_usd": price,
            "features": [f.value for f in LICENSE_FEATURES.get(license_type, [])],
        }
    
    return {
        "pricing": pricing,
        "currency": "USD",
        "last_updated": datetime.now().isoformat(),
    }


@router.get("/features")
async def get_features():
    """Get available features by license type."""
    return {
        "features": {
            license_type.value: [f.value for f in features]
            for license_type, features in LICENSE_FEATURES.items()
        },
        "last_updated": datetime.now().isoformat(),
    }


@router.get("/payment-methods")
async def get_payment_methods():
    """Get available payment methods."""
    return {
        "payment_methods": [
            {
                "method": "card",
                "name": "Credit/Debit Card",
                "description": "Visa, Mastercard, and other major cards",
                "supported": True,
            },
            {
                "method": "paypal",
                "name": "PayPal",
                "description": "Fast and secure PayPal payments",
                "supported": True,
            },
            {
                "method": "crypto",
                "name": "Cryptocurrency",
                "description": "Bitcoin, Ethereum, USDC, USDT, and Litecoin",
                "supported": True,
                "currencies": ["btc", "eth", "ltc", "usdc", "usdt"],
            },
        ],
    }
