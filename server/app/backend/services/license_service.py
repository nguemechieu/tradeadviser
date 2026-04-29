"""
License Management Service - Server-side license generation, verification, and management.

Features:
- Generate unique license keys
- Verify license validity and expiration
- Track license activations
- Generate trial licenses
- Manage license revocation
- Track license usage and features
"""

from __future__ import annotations

import hashlib
import secrets
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from enum import Enum

logger = logging.getLogger(__name__)


class LicenseType(str, Enum):
    """Types of licenses."""
    TRIAL = "trial"           # 30-day free trial
    BASIC = "basic"           # $9.99/month - basic features
    PRO = "pro"               # $29.99/month - all features
    ENTERPRISE = "enterprise" # Custom - all features + support


class LicenseStatus(str, Enum):
    """License status."""
    ACTIVE = "active"
    EXPIRED = "expired"
    REVOKED = "revoked"
    PENDING = "pending"


class LicenseFeature(str, Enum):
    """Available features by license tier."""
    # Basic features
    BASIC_TRADING = "basic_trading"           # 1 strategy, 1 broker
    MULTIPLE_STRATEGIES = "multiple_strategies"  # Up to 5 strategies
    MULTIPLE_BROKERS = "multiple_brokers"    # Up to 3 brokers
    HISTORICAL_DATA = "historical_data"      # Past 1 year
    
    # Pro features
    ADVANCED_ANALYTICS = "advanced_analytics"    # ML models, backtesting
    PORTFOLIO_MONITORING = "portfolio_monitoring"  # Real-time monitoring
    RISK_MANAGEMENT = "risk_management"      # Position sizing, stop-loss
    API_ACCESS = "api_access"                # REST API access
    CUSTOM_INDICATORS = "custom_indicators"  # Custom TA indicators
    
    # Enterprise features
    WHITE_LABEL = "white_label"              # Custom branding
    TEAM_MANAGEMENT = "team_management"      # Multiple users
    PRIORITY_SUPPORT = "priority_support"    # 24/7 support
    DEDICATED_ACCOUNT = "dedicated_account"  # Dedicated account manager
    CUSTOM_INTEGRATIONS = "custom_integrations"  # Custom broker integrations


# Feature availability by license type
LICENSE_FEATURES = {
    LicenseType.TRIAL: [
        LicenseFeature.BASIC_TRADING,
        LicenseFeature.HISTORICAL_DATA,
    ],
    LicenseType.BASIC: [
        LicenseFeature.BASIC_TRADING,
        LicenseFeature.MULTIPLE_STRATEGIES,
        LicenseFeature.HISTORICAL_DATA,
    ],
    LicenseType.PRO: [
        LicenseFeature.BASIC_TRADING,
        LicenseFeature.MULTIPLE_STRATEGIES,
        LicenseFeature.MULTIPLE_BROKERS,
        LicenseFeature.HISTORICAL_DATA,
        LicenseFeature.ADVANCED_ANALYTICS,
        LicenseFeature.PORTFOLIO_MONITORING,
        LicenseFeature.RISK_MANAGEMENT,
        LicenseFeature.API_ACCESS,
        LicenseFeature.CUSTOM_INDICATORS,
    ],
    LicenseType.ENTERPRISE: [
        # All features
        LicenseFeature.BASIC_TRADING,
        LicenseFeature.MULTIPLE_STRATEGIES,
        LicenseFeature.MULTIPLE_BROKERS,
        LicenseFeature.HISTORICAL_DATA,
        LicenseFeature.ADVANCED_ANALYTICS,
        LicenseFeature.PORTFOLIO_MONITORING,
        LicenseFeature.RISK_MANAGEMENT,
        LicenseFeature.API_ACCESS,
        LicenseFeature.CUSTOM_INDICATORS,
        LicenseFeature.WHITE_LABEL,
        LicenseFeature.TEAM_MANAGEMENT,
        LicenseFeature.PRIORITY_SUPPORT,
        LicenseFeature.DEDICATED_ACCOUNT,
        LicenseFeature.CUSTOM_INTEGRATIONS,
    ],
}

# License pricing (in USD)
LICENSE_PRICING = {
    LicenseType.TRIAL: 0.00,        # Free 30-day trial
    LicenseType.BASIC: 9.99,        # $9.99/month
    LicenseType.PRO: 29.99,         # $29.99/month
    LicenseType.ENTERPRISE: None,   # Custom pricing
}

# License duration in days
LICENSE_DURATION = {
    LicenseType.TRIAL: 30,          # 30 days
    LicenseType.BASIC: 30,          # Monthly
    LicenseType.PRO: 30,            # Monthly
    LicenseType.ENTERPRISE: 365,    # Yearly (default)
}


class LicenseKeyGenerator:
    """Generate and validate license keys."""
    
    @staticmethod
    def generate(user_id: str, license_type: LicenseType) -> str:
        """
        Generate a unique license key.
        
        Format: TRADE-XXXXX-XXXXX-XXXXX-XXXXX
        """
        # Create a unique seed from user ID, license type, and timestamp
        seed = f"{user_id}:{license_type}:{datetime.utcnow().isoformat()}"
        
        # Generate a hash of the seed
        hash_obj = hashlib.sha256(seed.encode())
        hash_hex = hash_obj.hexdigest()
        
        # Take first 20 chars and split into 4 groups of 5
        hash_truncated = hash_hex[:20].upper()
        parts = [hash_truncated[i:i+5] for i in range(0, 20, 5)]
        
        # Add random component for uniqueness
        random_part = secrets.token_hex(8).upper()
        
        # Format as TRADE-XXXXX-XXXXX-XXXXX-XXXXX
        return f"TRADE-{'-'.join(parts[:4])}"
    
    @staticmethod
    def validate_format(key: str) -> bool:
        """Check if key matches expected format."""
        if not key or not isinstance(key, str):
            return False
        
        parts = key.split("-")
        if len(parts) != 5:
            return False
        
        if parts[0] != "TRADE":
            return False
        
        for part in parts[1:]:
            if len(part) != 5 or not part.isalnum():
                return False
        
        return True


class LicenseService:
    """Service for managing licenses."""
    
    def __init__(self, db=None):
        self.db = db
        self.key_generator = LicenseKeyGenerator()
    
    def create_license(
        self,
        user_id: str,
        email: str,
        license_type: LicenseType,
        duration_days: Optional[int] = None,
        notes: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Create a new license for a user.
        
        Returns:
            {
                "license_key": "TRADE-XXXXX-XXXXX-XXXXX-XXXXX",
                "user_id": "user123",
                "email": "user@example.com",
                "type": "pro",
                "status": "active",
                "created_at": "2026-04-26T10:30:45Z",
                "expires_at": "2026-05-26T10:30:45Z",
                "features": [...]
            }
        """
        # Generate unique license key
        license_key = self.key_generator.generate(user_id, license_type)
        
        # Determine duration
        if duration_days is None:
            duration_days = LICENSE_DURATION.get(license_type, 30)
        
        now = datetime.utcnow()
        expires_at = now + timedelta(days=duration_days)
        
        license_data = {
            "license_key": license_key,
            "user_id": user_id,
            "email": email,
            "type": license_type.value,
            "status": LicenseStatus.ACTIVE.value,
            "created_at": now.isoformat(),
            "expires_at": expires_at.isoformat(),
            "duration_days": duration_days,
            "features": [f.value for f in LICENSE_FEATURES.get(license_type, [])],
            "activations": [],
            "notes": notes or "",
        }
        
        # TODO: Save to database
        # db.query(License).add(License(**license_data))
        # db.commit()
        
        logger.info(f"License created: {license_key} for user {user_id}")
        return license_data
    
    def verify_license(self, license_key: str) -> Dict[str, Any] | None:
        """
        Verify a license key and return license details.
        
        Returns None if invalid or expired.
        """
        # Validate key format
        if not self.key_generator.validate_format(license_key):
            logger.warning(f"Invalid license key format: {license_key}")
            return None
        
        # TODO: Query database
        # license = db.query(License).filter_by(license_key=license_key).first()
        
        # For now, return None (would query DB in production)
        return None
    
    def check_license_status(self, license_key: str) -> Dict[str, Any]:
        """
        Check license status without full verification.
        
        Returns:
            {
                "valid": bool,
                "status": "active|expired|revoked",
                "license_type": "trial|basic|pro|enterprise",
                "days_remaining": int,
                "features": [...],
                "message": str
            }
        """
        license_data = self.verify_license(license_key)
        
        if not license_data:
            return {
                "valid": False,
                "status": "invalid",
                "message": "License key not found or invalid",
            }
        
        now = datetime.utcnow()
        expires_at = datetime.fromisoformat(license_data["expires_at"])
        days_remaining = (expires_at - now).days
        
        # Determine status
        if license_data["status"] == LicenseStatus.REVOKED.value:
            status = "revoked"
            valid = False
            message = "License has been revoked"
        elif days_remaining <= 0:
            status = "expired"
            valid = False
            message = "License has expired"
        else:
            status = "active"
            valid = True
            message = f"License active. {days_remaining} days remaining."
        
        return {
            "valid": valid,
            "status": status,
            "license_type": license_data["type"],
            "days_remaining": max(days_remaining, 0),
            "features": license_data["features"],
            "message": message,
        }
    
    def activate_license(self, license_key: str, hardware_id: str) -> Dict[str, Any]:
        """
        Activate a license on a device.
        
        Returns:
            {
                "activated": bool,
                "message": str,
                "features": [...]
            }
        """
        license_data = self.verify_license(license_key)
        
        if not license_data:
            return {
                "activated": False,
                "message": "License key not found",
                "features": [],
            }
        
        # Check if already activated on this device
        if hardware_id in [act.get("hardware_id") for act in license_data.get("activations", [])]:
            return {
                "activated": True,
                "message": "License already activated on this device",
                "features": license_data["features"],
            }
        
        # Add activation record
        activation = {
            "hardware_id": hardware_id,
            "activated_at": datetime.utcnow().isoformat(),
        }
        
        if "activations" not in license_data:
            license_data["activations"] = []
        
        license_data["activations"].append(activation)
        
        # TODO: Update database
        # db.query(License).filter_by(license_key=license_key).update({"activations": license_data["activations"]})
        # db.commit()
        
        logger.info(f"License activated: {license_key} on device {hardware_id}")
        
        return {
            "activated": True,
            "message": "License activated successfully",
            "features": license_data["features"],
        }
    
    def revoke_license(self, license_key: str, reason: str = "") -> Dict[str, Any]:
        """Revoke a license."""
        license_data = self.verify_license(license_key)
        
        if not license_data:
            return {
                "revoked": False,
                "message": "License not found",
            }
        
        license_data["status"] = LicenseStatus.REVOKED.value
        license_data["revoked_at"] = datetime.utcnow().isoformat()
        license_data["revocation_reason"] = reason
        
        # TODO: Update database
        logger.info(f"License revoked: {license_key}. Reason: {reason}")
        
        return {
            "revoked": True,
            "message": "License revoked successfully",
        }
    
    def renew_license(self, license_key: str, duration_days: Optional[int] = None) -> Dict[str, Any]:
        """Renew a license."""
        license_data = self.verify_license(license_key)
        
        if not license_data:
            return {
                "renewed": False,
                "message": "License not found",
            }
        
        license_type = LicenseType(license_data["type"])
        
        if duration_days is None:
            duration_days = LICENSE_DURATION.get(license_type, 30)
        
        # Set new expiration from now
        new_expires_at = datetime.utcnow() + timedelta(days=duration_days)
        license_data["expires_at"] = new_expires_at.isoformat()
        license_data["status"] = LicenseStatus.ACTIVE.value
        
        # TODO: Update database
        logger.info(f"License renewed: {license_key}. Expires: {new_expires_at.isoformat()}")
        
        return {
            "renewed": True,
            "message": "License renewed successfully",
            "expires_at": new_expires_at.isoformat(),
        }
    
    def get_user_licenses(self, user_id: str) -> List[Dict[str, Any]]:
        """Get all licenses for a user."""
        # TODO: Query database
        # licenses = db.query(License).filter_by(user_id=user_id).all()
        return []
    
    def get_trial_license_info(self, user_id: str) -> Dict[str, Any] | None:
        """Get trial license info for a user."""
        # TODO: Query database
        # trial = db.query(License).filter_by(user_id=user_id, type='trial').first()
        return None


# Global license service instance
_license_service: LicenseService | None = None


def get_license_service(db=None) -> LicenseService:
    """Get or create the global license service instance."""
    global _license_service
    if _license_service is None:
        _license_service = LicenseService(db=db)
    return _license_service
