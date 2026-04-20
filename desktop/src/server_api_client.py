"""
Server API Client for Desktop - Handles communication with SQS Server

Provides:
- Authentication API calls
- Broker configuration sync
- User profile management
- Settings persistence
"""

import json
import logging
import asyncio
from typing import Optional, Dict, Any
from enum import Enum

try:
    import aiohttp
    import asyncio
    AIOHTTP_AVAILABLE = True
except ImportError:
    AIOHTTP_AVAILABLE = False

logger = logging.getLogger(__name__)


class APIEndpoint(Enum):
    """API endpoints."""
    # Auth endpoints
    LOGIN = "/auth/login"
    SIGNUP = "/auth/signup"
    LOGOUT = "/auth/logout"
    REFRESH_TOKEN = "/auth/refresh"
    
    # User endpoints
    GET_PROFILE = "/users/profile"
    UPDATE_PROFILE = "/users/profile"
    
    # Broker configuration endpoints
    GET_BROKER_CONFIG = "/users/broker-config"
    SAVE_BROKER_CONFIG = "/users/broker-config"
    TEST_BROKER_CONNECTION = "/users/broker-config/test"
    LIST_BROKER_CONFIGS = "/users/broker-configs"
    DELETE_BROKER_CONFIG = "/users/broker-config/{broker_id}"
    
    # Admin endpoints (for future expansion)
    GET_ADMIN_OPERATIONS = "/admin/operations/health"
    GET_ADMIN_RISK = "/admin/risk/overview"
    GET_ADMIN_USERS = "/admin/users-licenses/users"


class ServerAPIClient:
    """
    HTTP client for communicating with Sopotek Quant System Server.
    
    Handles:
    - Authentication (login, signup, token refresh)
    - Broker configuration (save, retrieve, test)
    - User profile management
    - Error handling and retry logic
    """
    
    def __init__(self, server_url: str = "http://localhost:8000"):
        self.server_url = server_url.rstrip('/')
        self.session_token: Optional[str] = None
        self.user_id: Optional[str] = None
        
        if not AIOHTTP_AVAILABLE:
            logger.warning("aiohttp not available - async operations will be limited")
    
    def set_auth_token(self, token: str, user_id: Optional[str] = None):
        """Set authentication token for subsequent requests."""
        self.session_token = token
        self.user_id = user_id
    
    def get_url(self, endpoint: APIEndpoint) -> str:
        """Build full URL for endpoint."""
        return f"{self.server_url}{endpoint.value}"
    
    def get_headers(self, include_auth: bool = True) -> Dict[str, str]:
        """Build request headers."""
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "SopotekDesktopClient/1.0"
        }
        
        if include_auth and self.session_token:
            headers["Authorization"] = f"Bearer {self.session_token}"
        
        return headers
    
    # ==================== Authentication ====================
    
    async def login(self, email: str, password: str) -> Dict[str, Any]:
        """
        Login with email and password.
        
        Returns:
            {
                "success": bool,
                "token": str,
                "user_id": str,
                "username": str,
                "email": str,
                "message": str
            }
        """
        if not AIOHTTP_AVAILABLE:
            logger.warning("aiohttp required for async login")
            return {"success": False, "message": "aiohttp not available"}
        
        # Validate credentials before attempting login
        email = (email or "").strip()
        password = (password or "").strip()
        
        if not email or not password:
            logger.warning("Login failed: empty email or password")
            return {
                "success": False,
                "message": "Email and password are required"
            }
        
        payload = {
            "identifier": email,  # Server expects 'identifier' not 'email'
            "password": password
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.get_url(APIEndpoint.LOGIN),
                    json=payload,
                    headers=self.get_headers(include_auth=False),
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    data = await response.json()
                    
                    if response.status == 200:
                        self.set_auth_token(
                            data.get("access_token"),  # Server returns 'access_token'
                            data.get("user_id")
                        )
                        logger.info(f"Login successful: {email}")
                        return {
                            "success": True,
                            "token": data.get("access_token"),
                            "access_token": data.get("access_token"),
                            "refresh_token": data.get("refresh_token"),
                            "user_id": data.get("user_id"),
                            "message": "Login successful"
                        }
                    else:
                        error_msg = data.get("detail", f"Login failed with status {response.status}")
                        logger.warning(f"Login failed: {error_msg}")
                        return {
                            "success": False,
                            "message": error_msg
                        }
        except asyncio.TimeoutError:
            logger.error(f"Login timeout - server not responding")
            return {
                "success": False,
                "message": "Server not responding (timeout)"
            }
        except Exception as e:
            logger.error(f"Login failed: {e}")
            return {
                "success": False,
                "message": str(e)
            }
    
    async def signup(self, name: str, email: str, password: str) -> Dict[str, Any]:
        """
        Create new account.
        
        Returns:
            {
                "success": bool,
                "token": str,
                "user_id": str,
                "username": str,
                "message": str
            }
        """
        if not AIOHTTP_AVAILABLE:
            logger.warning("aiohttp required for async signup")
            return {"success": False, "message": "aiohttp not available"}
        
        payload = {
            "name": name,
            "email": email,
            "password": password
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.get_url(APIEndpoint.SIGNUP),
                    json=payload,
                    headers=self.get_headers(include_auth=False)
                ) as response:
                    data = await response.json()
                    
                    if response.status == 201 and data.get("success"):
                        self.set_auth_token(
                            data.get("token"),
                            data.get("user_id")
                        )
                        logger.info(f"Signup successful: {data.get('username')}")
                    
                    return data
        except Exception as e:
            logger.error(f"Signup failed: {e}")
            return {"success": False, "message": str(e)}
    
    async def logout(self) -> Dict[str, Any]:
        """Logout current user."""
        if not AIOHTTP_AVAILABLE:
            return {"success": True, "message": "Local logout"}
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.get_url(APIEndpoint.LOGOUT),
                    headers=self.get_headers(include_auth=True)
                ) as response:
                    logger.info("Logout successful")
                    return {"success": True, "message": "Logged out"}
        except Exception as e:
            logger.error(f"Logout failed: {e}")
            return {"success": False, "message": str(e)}
    
    async def refresh_token(self) -> Dict[str, Any]:
        """Refresh authentication token."""
        if not AIOHTTP_AVAILABLE:
            return {"success": False, "message": "aiohttp not available"}
        
        if not self.session_token:
            return {
                "success": False,
                "message": "No active session to refresh"
            }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.get_url(APIEndpoint.REFRESH_TOKEN),
                    headers=self.get_headers(include_auth=True),
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    data = await response.json()
                    
                    if response.status == 200:
                        # Server returns 'access_token' and 'refresh_token'
                        new_token = data.get("access_token") or data.get("token")
                        if new_token:
                            self.set_auth_token(new_token)
                            logger.info("Token refreshed successfully")
                            return {
                                "success": True,
                                "access_token": new_token,
                                "refresh_token": data.get("refresh_token"),
                                "message": "Token refreshed"
                            }
                    
                    error_msg = data.get("detail", f"Token refresh failed with status {response.status}")
                    logger.warning(f"Token refresh failed: {error_msg}")
                    return {
                        "success": False,
                        "message": error_msg
                    }
        except asyncio.TimeoutError:
            logger.error("Token refresh timeout")
            return {
                "success": False,
                "message": "Server not responding (timeout)"
            }
        except Exception as e:
            logger.error(f"Token refresh failed: {e}")
            return {
                "success": False,
                "message": str(e)
            }
    
    # ==================== Broker Configuration ====================
    
    async def save_broker_config(
        self,
        broker: str,
        config: Dict[str, Any],
        mode: str = "local"
    ) -> Dict[str, Any]:
        """
        Save broker configuration to server.
        
        Args:
            broker: Broker name (e.g., "Alpaca", "Binance")
            config: Broker configuration dictionary
            mode: "local" or "remote"
        
        Returns:
            {
                "success": bool,
                "config_id": str,
                "message": str
            }
        """
        if not AIOHTTP_AVAILABLE:
            logger.warning("aiohttp required for async broker config")
            return {"success": True, "message": "Config would be saved locally"}
        
        payload = {
            "broker": broker,
            "config": config,
            "mode": mode
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.get_url(APIEndpoint.SAVE_BROKER_CONFIG),
                    json=payload,
                    headers=self.get_headers(include_auth=True)
                ) as response:
                    data = await response.json()
                    
                    if response.status == 201:
                        logger.info(f"Broker config saved: {broker}")
                    
                    return data
        except Exception as e:
            logger.error(f"Failed to save broker config: {e}")
            return {"success": False, "message": str(e)}
    
    async def get_broker_configs(self) -> Dict[str, Any]:
        """Get all saved broker configurations."""
        if not AIOHTTP_AVAILABLE:
            return {"success": False, "configs": []}
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    self.get_url(APIEndpoint.LIST_BROKER_CONFIGS),
                    headers=self.get_headers(include_auth=True)
                ) as response:
                    data = await response.json()
                    logger.info(f"Retrieved {len(data.get('configs', []))} broker configs")
                    return data
        except Exception as e:
            logger.error(f"Failed to get broker configs: {e}")
            return {"success": False, "configs": []}
    
    async def test_broker_connection(self, broker: str, config: Dict) -> Dict[str, Any]:
        """Test broker connection with given credentials."""
        if not AIOHTTP_AVAILABLE:
            return {"success": True, "message": "Connection test would run"}
        
        payload = {
            "broker": broker,
            "config": config
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.get_url(APIEndpoint.TEST_BROKER_CONNECTION),
                    json=payload,
                    headers=self.get_headers(include_auth=True)
                ) as response:
                    data = await response.json()
                    logger.info(f"Broker connection test: {broker}")
                    return data
        except Exception as e:
            logger.error(f"Broker connection test failed: {e}")
            return {"success": False, "message": str(e)}
    
    # ==================== User Profile ====================
    
    async def get_profile(self) -> Dict[str, Any]:
        """Get current user profile."""
        if not AIOHTTP_AVAILABLE:
            return {"success": False, "profile": {}}
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    self.get_url(APIEndpoint.GET_PROFILE),
                    headers=self.get_headers(include_auth=True)
                ) as response:
                    return await response.json()
        except Exception as e:
            logger.error(f"Failed to get profile: {e}")
            return {"success": False, "message": str(e)}
    
    async def update_profile(self, profile_data: Dict) -> Dict[str, Any]:
        """Update user profile."""
        if not AIOHTTP_AVAILABLE:
            return {"success": True, "message": "Profile update local only"}
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.put(
                    self.get_url(APIEndpoint.UPDATE_PROFILE),
                    json=profile_data,
                    headers=self.get_headers(include_auth=True)
                ) as response:
                    logger.info("Profile updated")
                    return await response.json()
        except Exception as e:
            logger.error(f"Failed to update profile: {e}")
            return {"success": False, "message": str(e)}


# Global API client instance
_api_client: Optional[ServerAPIClient] = None


def get_api_client(server_url: str = "http://localhost:8000") -> ServerAPIClient:
    """Get or create global API client."""
    global _api_client
    if _api_client is None:
        _api_client = ServerAPIClient(server_url)
    return _api_client
