"""
Email Notification Service - Send license keys and payment confirmations to users.

Supports:
- License delivery via email
- Payment confirmations
- License expiration reminders
- Renewal notifications
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional, Dict, Any, List
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import smtplib

logger = logging.getLogger(__name__)


class EmailService:
    """Service for sending email notifications."""
    
    def __init__(
        self,
        smtp_host: str = "smtp.gmail.com",
        smtp_port: int = 587,
        sender_email: Optional[str] = None,
        sender_password: Optional[str] = None,
        from_name: str = "TradeAdviser",
    ):
        """
        Initialize email service.
        
        Args:
            smtp_host: SMTP server host
            smtp_port: SMTP server port
            sender_email: Sender email address
            sender_password: Sender email password (or app password for Gmail)
            from_name: Display name for sender
        """
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port
        self.sender_email = sender_email
        self.sender_password = sender_password
        self.from_name = from_name
    
    def send_license_email(
        self,
        recipient_email: str,
        license_key: str,
        license_type: str,
        expires_at: str,
        features: List[str],
    ) -> Dict[str, Any]:
        """
        Send license key to user via email.
        
        Args:
            recipient_email: User's email address
            license_key: License key (TRADE-XXXXX-XXXXX-XXXXX-XXXXX)
            license_type: Type of license (trial, basic, pro, enterprise)
            expires_at: Expiration date/time
            features: List of available features
        
        Returns:
            {
                "sent": bool,
                "message": str
            }
        """
        try:
            subject = f"Your {license_type.upper()} License Key - TradeAdviser"
            
            # Create email body
            body = self._create_license_email_body(
                license_key=license_key,
                license_type=license_type,
                expires_at=expires_at,
                features=features,
            )
            
            self._send_email(recipient_email, subject, body)
            
            logger.info(f"License email sent to {recipient_email}")
            
            return {
                "sent": True,
                "message": "License key sent to your email",
            }
        
        except Exception as exc:
            logger.error(f"Failed to send license email: {exc}")
            return {
                "sent": False,
                "message": f"Failed to send email: {str(exc)}",
            }
    
    def send_payment_confirmation(
        self,
        recipient_email: str,
        payment_id: str,
        amount_usd: float,
        license_type: str,
        payment_method: str,
    ) -> Dict[str, Any]:
        """
        Send payment confirmation email.
        
        Args:
            recipient_email: User's email address
            payment_id: Payment transaction ID
            amount_usd: Amount paid in USD
            license_type: Type of license purchased
            payment_method: Payment method used (card, paypal, crypto)
        
        Returns:
            {
                "sent": bool,
                "message": str
            }
        """
        try:
            subject = f"Payment Confirmation - TradeAdviser License Purchase"
            
            body = self._create_payment_confirmation_email_body(
                payment_id=payment_id,
                amount_usd=amount_usd,
                license_type=license_type,
                payment_method=payment_method,
            )
            
            self._send_email(recipient_email, subject, body)
            
            logger.info(f"Payment confirmation sent to {recipient_email}")
            
            return {
                "sent": True,
                "message": "Payment confirmation sent to your email",
            }
        
        except Exception as exc:
            logger.error(f"Failed to send payment confirmation: {exc}")
            return {
                "sent": False,
                "message": f"Failed to send email: {str(exc)}",
            }
    
    def send_license_expiration_reminder(
        self,
        recipient_email: str,
        license_key: str,
        license_type: str,
        days_remaining: int,
    ) -> Dict[str, Any]:
        """
        Send license expiration reminder email.
        
        Args:
            recipient_email: User's email address
            license_key: License key
            license_type: Type of license
            days_remaining: Days until expiration
        
        Returns:
            {
                "sent": bool,
                "message": str
            }
        """
        try:
            subject = f"Your {license_type.upper()} License Expires in {days_remaining} Days"
            
            body = self._create_expiration_reminder_email_body(
                license_key=license_key,
                license_type=license_type,
                days_remaining=days_remaining,
            )
            
            self._send_email(recipient_email, subject, body)
            
            logger.info(f"License expiration reminder sent to {recipient_email}")
            
            return {
                "sent": True,
                "message": "Expiration reminder sent to your email",
            }
        
        except Exception as exc:
            logger.error(f"Failed to send expiration reminder: {exc}")
            return {
                "sent": False,
                "message": f"Failed to send email: {str(exc)}",
            }
    
    def send_renewal_invitation(
        self,
        recipient_email: str,
        license_key: str,
        license_type: str,
        renewal_discount: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Send license renewal invitation.
        
        Args:
            recipient_email: User's email address
            license_key: Current license key
            license_type: Type of license
            renewal_discount: Discount percentage for renewal (e.g., 10.0 for 10% off)
        
        Returns:
            {
                "sent": bool,
                "message": str
            }
        """
        try:
            subject = f"Renew Your {license_type.upper()} License - Special Offer!"
            
            body = self._create_renewal_invitation_email_body(
                license_key=license_key,
                license_type=license_type,
                renewal_discount=renewal_discount,
            )
            
            self._send_email(recipient_email, subject, body)
            
            logger.info(f"Renewal invitation sent to {recipient_email}")
            
            return {
                "sent": True,
                "message": "Renewal invitation sent to your email",
            }
        
        except Exception as exc:
            logger.error(f"Failed to send renewal invitation: {exc}")
            return {
                "sent": False,
                "message": f"Failed to send email: {str(exc)}",
            }
    
    def _send_email(self, to_email: str, subject: str, body: str) -> None:
        """
        Send an email.
        
        Note: In production, use a service like SendGrid, Mailgun, or AWS SES
        for better reliability and deliverability.
        """
        if not self.sender_email or not self.sender_password:
            logger.warning("Email service not configured. Email not sent.")
            return
        
        try:
            # Create message
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = f"{self.from_name} <{self.sender_email}>"
            msg["To"] = to_email
            
            # Attach HTML body
            msg.attach(MIMEText(body, "html"))
            
            # Send via SMTP
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                server.starttls()
                server.login(self.sender_email, self.sender_password)
                server.send_message(msg)
            
            logger.debug(f"Email sent to {to_email}: {subject}")
        
        except Exception as exc:
            logger.error(f"SMTP error: {exc}")
            raise
    
    @staticmethod
    def _create_license_email_body(
        license_key: str,
        license_type: str,
        expires_at: str,
        features: List[str],
    ) -> str:
        """Create HTML email body for license delivery."""
        features_html = "".join([f"<li>{feature}</li>" for feature in features])
        
        return f"""
        <html>
            <body style="font-family: Arial, sans-serif; color: #333;">
                <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                    <h2 style="color: #2c3e50;">Welcome to TradeAdviser!</h2>
                    
                    <p>Thank you for purchasing a <strong>{license_type.upper()}</strong> license.</p>
                    
                    <div style="background-color: #ecf0f1; padding: 20px; border-radius: 5px; margin: 20px 0;">
                        <h3>Your License Key</h3>
                        <p style="font-size: 18px; font-weight: bold; font-family: monospace; color: #2980b9;">
                            {license_key}
                        </p>
                        <p style="color: #7f8c8d;">Keep this key safe. You'll need it to activate your license.</p>
                    </div>
                    
                    <h3>License Details</h3>
                    <ul>
                        <li><strong>Type:</strong> {license_type.upper()}</li>
                        <li><strong>Expires:</strong> {expires_at}</li>
                        <li><strong>Features:</strong>
                            <ul>
                                {features_html}
                            </ul>
                        </li>
                    </ul>
                    
                    <h3>How to Activate</h3>
                    <ol>
                        <li>Open the TradeAdviser desktop application</li>
                        <li>Go to Settings → License</li>
                        <li>Paste your license key and click "Activate"</li>
                    </ol>
                    
                    <p style="margin-top: 40px; padding-top: 20px; border-top: 1px solid #ecf0f1; color: #7f8c8d; font-size: 12px;">
                        If you have any questions, please contact our support team at support@tradeadviser.io
                    </p>
                </div>
            </body>
        </html>
        """
    
    @staticmethod
    def _create_payment_confirmation_email_body(
        payment_id: str,
        amount_usd: float,
        license_type: str,
        payment_method: str,
    ) -> str:
        """Create HTML email body for payment confirmation."""
        payment_method_display = {
            "card": "Credit/Debit Card",
            "paypal": "PayPal",
            "crypto": "Cryptocurrency",
        }.get(payment_method, payment_method)
        
        return f"""
        <html>
            <body style="font-family: Arial, sans-serif; color: #333;">
                <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                    <h2 style="color: #27ae60;">✓ Payment Confirmed</h2>
                    
                    <p>Your payment has been successfully processed!</p>
                    
                    <div style="background-color: #d5f4e6; padding: 20px; border-radius: 5px; margin: 20px 0;">
                        <h3>Transaction Details</h3>
                        <table style="width: 100%; border-collapse: collapse;">
                            <tr>
                                <td style="padding: 8px;"><strong>Transaction ID:</strong></td>
                                <td style="padding: 8px; text-align: right; font-family: monospace;">{payment_id}</td>
                            </tr>
                            <tr style="background-color: #c8e6c9;">
                                <td style="padding: 8px;"><strong>Amount:</strong></td>
                                <td style="padding: 8px; text-align: right;"><strong>${amount_usd:.2f} USD</strong></td>
                            </tr>
                            <tr>
                                <td style="padding: 8px;"><strong>License Type:</strong></td>
                                <td style="padding: 8px; text-align: right;">{license_type.upper()}</td>
                            </tr>
                            <tr>
                                <td style="padding: 8px;"><strong>Payment Method:</strong></td>
                                <td style="padding: 8px; text-align: right;">{payment_method_display}</td>
                            </tr>
                        </table>
                    </div>
                    
                    <p>Your license key will be sent to you shortly. Check your inbox (and spam folder) for the license delivery email.</p>
                    
                    <p style="margin-top: 40px; padding-top: 20px; border-top: 1px solid #ecf0f1; color: #7f8c8d; font-size: 12px;">
                        If you have any questions, please contact our support team at support@tradeadviser.io
                    </p>
                </div>
            </body>
        </html>
        """
    
    @staticmethod
    def _create_expiration_reminder_email_body(
        license_key: str,
        license_type: str,
        days_remaining: int,
    ) -> str:
        """Create HTML email body for expiration reminder."""
        return f"""
        <html>
            <body style="font-family: Arial, sans-serif; color: #333;">
                <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                    <h2 style="color: #e67e22;">⚠ License Expiring Soon</h2>
                    
                    <p>Your <strong>{license_type.upper()}</strong> license will expire in <strong>{days_remaining} days</strong>.</p>
                    
                    <div style="background-color: #fff3cd; padding: 20px; border-radius: 5px; margin: 20px 0;">
                        <p>To continue using all features, please renew your license.</p>
                        <p style="margin-top: 15px;">
                            <a href="https://app.tradeadviser.io/renew?license={license_key}" 
                               style="display: inline-block; background-color: #e67e22; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">
                                Renew Now
                            </a>
                        </p>
                    </div>
                    
                    <p style="margin-top: 40px; padding-top: 20px; border-top: 1px solid #ecf0f1; color: #7f8c8d; font-size: 12px;">
                        If you have any questions, please contact our support team at support@tradeadviser.io
                    </p>
                </div>
            </body>
        </html>
        """
    
    @staticmethod
    def _create_renewal_invitation_email_body(
        license_key: str,
        license_type: str,
        renewal_discount: Optional[float] = None,
    ) -> str:
        """Create HTML email body for renewal invitation."""
        discount_text = ""
        if renewal_discount:
            discount_text = f"<p style='color: #27ae60; font-size: 18px; font-weight: bold;'>Special Offer: {renewal_discount}% OFF renewal!</p>"
        
        return f"""
        <html>
            <body style="font-family: Arial, sans-serif; color: #333;">
                <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                    <h2 style="color: #2980b9;">Renew Your {license_type.upper()} License</h2>
                    
                    <p>Your current license is about to expire. Don't lose access to your trading tools!</p>
                    
                    {discount_text}
                    
                    <div style="background-color: #e8f4f8; padding: 20px; border-radius: 5px; margin: 20px 0;">
                        <h3>Why Renew?</h3>
                        <ul>
                            <li>Continue trading without interruption</li>
                            <li>Keep all your strategies and data</li>
                            <li>Get the latest features and improvements</li>
                            <li>Priority support</li>
                        </ul>
                    </div>
                    
                    <p style="margin-top: 20px;">
                        <a href="https://app.tradeadviser.io/renew?license={license_key}" 
                           style="display: inline-block; background-color: #2980b9; color: white; padding: 12px 24px; text-decoration: none; border-radius: 5px; font-size: 16px;">
                            Renew Your License
                        </a>
                    </p>
                    
                    <p style="margin-top: 40px; padding-top: 20px; border-top: 1px solid #ecf0f1; color: #7f8c8d; font-size: 12px;">
                        If you have any questions, please contact our support team at support@tradeadviser.io
                    </p>
                </div>
            </body>
        </html>
        """


# Global email service instance
_email_service: EmailService | None = None


def get_email_service(
    smtp_host: str = "smtp.gmail.com",
    smtp_port: int = 587,
    sender_email: Optional[str] = None,
    sender_password: Optional[str] = None,
) -> EmailService:
    """Get or create the global email service instance."""
    global _email_service
    if _email_service is None:
        _email_service = EmailService(
            smtp_host=smtp_host,
            smtp_port=smtp_port,
            sender_email=sender_email,
            sender_password=sender_password,
        )
    return _email_service
