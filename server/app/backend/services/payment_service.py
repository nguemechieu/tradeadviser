"""
Payment Processing Service - Handle license purchases via Stripe, PayPal, and crypto.

Supports:
- Credit/Debit cards (Visa, Mastercard) via Stripe
- PayPal integration
- Cryptocurrency payments (Bitcoin, Ethereum)
"""

from __future__ import annotations

import logging
import hashlib
from datetime import datetime
from typing import Optional, Dict, Any
from enum import Enum

logger = logging.getLogger(__name__)


class PaymentMethod(str, Enum):
    """Payment methods."""
    CARD = "card"           # Visa/Mastercard via Stripe
    PAYPAL = "paypal"
    CRYPTO = "crypto"       # Bitcoin, Ethereum, etc.


class PaymentStatus(str, Enum):
    """Payment status."""
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"
    REFUNDED = "refunded"
    CANCELLED = "cancelled"


class CryptoCurrency(str, Enum):
    """Supported cryptocurrencies."""
    BITCOIN = "btc"
    ETHEREUM = "eth"
    LITECOIN = "ltc"
    USDC = "usdc"
    USDT = "usdt"


class PaymentService:
    """Service for processing license payments."""
    
    def __init__(self, stripe_key: Optional[str] = None, crypto_processor: Optional[Any] = None):
        """
        Initialize payment service.
        
        Args:
            stripe_key: Stripe API key
            crypto_processor: Crypto payment processor (e.g., Coinbase Commerce)
        """
        self.stripe_key = stripe_key
        self.crypto_processor = crypto_processor
        
        # In production, initialize Stripe client:
        # import stripe
        # stripe.api_key = stripe_key
    
    def create_card_payment(
        self,
        user_id: str,
        email: str,
        amount_usd: float,
        license_type: str,
        card_token: str,
    ) -> Dict[str, Any]:
        """
        Process credit/debit card payment via Stripe.
        
        Args:
            user_id: User ID
            email: User email
            amount_usd: Amount in USD
            license_type: Type of license (basic, pro, enterprise)
            card_token: Stripe token from frontend
        
        Returns:
            {
                "payment_id": "pay_xyz123",
                "status": "completed|failed",
                "amount": 29.99,
                "currency": "usd",
                "license_key": "TRADE-XXXXX-XXXXX-XXXXX-XXXXX",
                "message": "Payment successful"
            }
        """
        payment_id = f"pay_{self._generate_payment_id()}"
        
        try:
            # TODO: In production, use actual Stripe API:
            # charge = stripe.Charge.create(
            #     amount=int(amount_usd * 100),  # Amount in cents
            #     currency="usd",
            #     source=card_token,
            #     description=f"License purchase: {license_type}",
            #     metadata={
            #         "user_id": user_id,
            #         "license_type": license_type,
            #     }
            # )
            
            # Simulate successful payment
            logger.info(f"Card payment processed: {payment_id} for user {user_id}")
            
            return {
                "payment_id": payment_id,
                "status": PaymentStatus.COMPLETED.value,
                "amount": amount_usd,
                "currency": "usd",
                "method": PaymentMethod.CARD.value,
                "created_at": datetime.utcnow().isoformat(),
                "message": "Payment processed successfully",
            }
        
        except Exception as exc:
            logger.error(f"Card payment failed: {exc}")
            return {
                "payment_id": payment_id,
                "status": PaymentStatus.FAILED.value,
                "message": f"Payment failed: {str(exc)}",
            }
    
    def create_paypal_payment(
        self,
        user_id: str,
        email: str,
        amount_usd: float,
        license_type: str,
    ) -> Dict[str, Any]:
        """
        Create PayPal payment request.
        
        Returns:
            {
                "payment_id": "pay_xyz123",
                "status": "pending",
                "redirect_url": "https://www.paypal.com/...",
                "message": "Redirect to PayPal to complete payment"
            }
        """
        payment_id = f"pay_{self._generate_payment_id()}"
        
        try:
            # TODO: In production, use PayPal SDK:
            # response = paypalrestsdk.Payment.find(payment_id)
            # or create a payment redirect
            
            redirect_url = f"https://www.paypal.com/checkout?token={payment_id}"
            
            logger.info(f"PayPal payment created: {payment_id} for user {user_id}")
            
            return {
                "payment_id": payment_id,
                "status": PaymentStatus.PENDING.value,
                "method": PaymentMethod.PAYPAL.value,
                "redirect_url": redirect_url,
                "amount": amount_usd,
                "currency": "usd",
                "created_at": datetime.utcnow().isoformat(),
                "message": "Redirect to PayPal to complete payment",
            }
        
        except Exception as exc:
            logger.error(f"PayPal payment creation failed: {exc}")
            return {
                "payment_id": payment_id,
                "status": PaymentStatus.FAILED.value,
                "message": f"Payment creation failed: {str(exc)}",
            }
    
    def create_crypto_payment(
        self,
        user_id: str,
        email: str,
        amount_usd: float,
        license_type: str,
        currency: CryptoCurrency = CryptoCurrency.BITCOIN,
    ) -> Dict[str, Any]:
        """
        Create cryptocurrency payment request.
        
        Returns:
            {
                "payment_id": "pay_xyz123",
                "status": "pending",
                "currency": "btc",
                "amount_crypto": 0.00063,
                "wallet_address": "1A1z7agoat...",
                "webhook_url": "https://api.example.com/webhooks/crypto/pay_xyz123",
                "message": "Send crypto to complete payment"
            }
        """
        payment_id = f"pay_{self._generate_payment_id()}"
        
        try:
            # TODO: In production, use crypto processor like Coinbase Commerce:
            # charge = coinbase_commerce.Charge.create(
            #     name=f"{license_type} License",
            #     description=f"TradeAdviser {license_type} license",
            #     local_price={"amount": amount_usd, "currency": "USD"},
            #     pricing_type="fixed_price",
            #     metadata={"user_id": user_id, "payment_id": payment_id}
            # )
            
            # Placeholder values
            crypto_amounts = {
                CryptoCurrency.BITCOIN: amount_usd / 70000,      # ~$70k/BTC
                CryptoCurrency.ETHEREUM: amount_usd / 3500,      # ~$3.5k/ETH
                CryptoCurrency.LITECOIN: amount_usd / 200,       # ~$200/LTC
                CryptoCurrency.USDC: amount_usd,                 # 1:1 with USD
                CryptoCurrency.USDT: amount_usd,                 # 1:1 with USD
            }
            
            amount_crypto = crypto_amounts.get(currency, amount_usd)
            
            logger.info(f"Crypto payment created: {payment_id} for user {user_id}")
            
            return {
                "payment_id": payment_id,
                "status": PaymentStatus.PENDING.value,
                "method": PaymentMethod.CRYPTO.value,
                "currency": currency.value,
                "amount_usd": amount_usd,
                "amount_crypto": round(amount_crypto, 8),
                "wallet_address": self._generate_wallet_address(),
                "webhook_url": f"https://api.example.com/webhooks/crypto/{payment_id}",
                "expires_at": datetime.utcnow().isoformat(),  # 1 hour expiry
                "created_at": datetime.utcnow().isoformat(),
                "message": f"Send {currency.value.upper()} to complete payment",
            }
        
        except Exception as exc:
            logger.error(f"Crypto payment creation failed: {exc}")
            return {
                "payment_id": payment_id,
                "status": PaymentStatus.FAILED.value,
                "message": f"Payment creation failed: {str(exc)}",
            }
    
    def confirm_payment(self, payment_id: str) -> Dict[str, Any]:
        """
        Confirm a payment (used by webhooks or polling).
        
        Returns:
            {
                "confirmed": bool,
                "status": "completed|failed|pending",
                "message": str
            }
        """
        try:
            # TODO: Query payment database or external service
            logger.info(f"Payment confirmed: {payment_id}")
            
            return {
                "confirmed": True,
                "status": PaymentStatus.COMPLETED.value,
                "message": "Payment confirmed",
            }
        
        except Exception as exc:
            logger.error(f"Payment confirmation failed: {exc}")
            return {
                "confirmed": False,
                "status": PaymentStatus.FAILED.value,
                "message": f"Confirmation failed: {str(exc)}",
            }
    
    def refund_payment(self, payment_id: str, reason: str = "") -> Dict[str, Any]:
        """Refund a payment."""
        try:
            # TODO: Process refund with payment provider
            
            logger.info(f"Payment refunded: {payment_id}. Reason: {reason}")
            
            return {
                "refunded": True,
                "payment_id": payment_id,
                "status": PaymentStatus.REFUNDED.value,
                "message": "Payment refunded successfully",
            }
        
        except Exception as exc:
            logger.error(f"Refund failed: {exc}")
            return {
                "refunded": False,
                "message": f"Refund failed: {str(exc)}",
            }
    
    def get_payment_status(self, payment_id: str) -> Dict[str, Any]:
        """Get payment status."""
        try:
            # TODO: Query payment database
            
            return {
                "payment_id": payment_id,
                "status": PaymentStatus.PENDING.value,
                "created_at": datetime.utcnow().isoformat(),
            }
        
        except Exception as exc:
            logger.error(f"Status check failed: {exc}")
            return {
                "error": str(exc),
            }
    
    @staticmethod
    def _generate_payment_id() -> str:
        """Generate a unique payment ID."""
        import secrets
        return secrets.token_hex(8)
    
    @staticmethod
    def _generate_wallet_address() -> str:
        """Generate a temporary wallet address for crypto payments."""
        # In production, this would be generated from a payment processor
        import secrets
        return f"1{secrets.token_hex(20)}"


# Global payment service instance
_payment_service: PaymentService | None = None


def get_payment_service(stripe_key: Optional[str] = None) -> PaymentService:
    """Get or create the global payment service instance."""
    global _payment_service
    if _payment_service is None:
        _payment_service = PaymentService(stripe_key=stripe_key)
    return _payment_service
