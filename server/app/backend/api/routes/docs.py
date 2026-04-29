"""
Routes documentation endpoint for API discovery.
Lists all available API endpoints with their descriptions, methods, and required roles.
"""

from fastapi import APIRouter, Depends, status
from server.app.backend.dependencies import ServerServiceContainer, get_services

router = APIRouter(prefix="/api/v3/docs", tags=["Documentation"])


# Comprehensive route documentation
ROUTES_DOCUMENTATION = {
    "Authentication": [
        {
            "method": "POST",
            "endpoint": "/api/auth/login",
            "description": "User login with credentials",
            "roles": ["public"],
            "parameters": "identifier (email/username), password, remember_me (boolean)",
            "example": '{"identifier": "user@example.com", "password": "pass", "remember_me": true}',
        },
        {
            "method": "POST",
            "endpoint": "/api/auth/register",
            "description": "Create new user account",
            "roles": ["public"],
            "parameters": "email, password, username (optional), display_name (optional)",
            "example": '{"email": "user@example.com", "password": "securepass", "username": "john"}',
        },
        {
            "method": "POST",
            "endpoint": "/api/auth/refresh",
            "description": "Refresh access token using refresh token",
            "roles": ["public"],
            "parameters": "refresh_token, remember_me (boolean)",
            "example": '{"refresh_token": "token_here", "remember_me": true}',
        },
        {
            "method": "GET",
            "endpoint": "/api/auth/me",
            "description": "Get current user profile and information",
            "roles": ["all"],
        },
        {
            "method": "POST",
            "endpoint": "/api/auth/forgot-password",
            "description": "Request password reset for user account",
            "roles": ["public"],
            "parameters": "identifier (email/username)",
        },
        {
            "method": "POST",
            "endpoint": "/api/auth/reset-password",
            "description": "Reset password with reset token",
            "roles": ["public"],
            "parameters": "reset_token, new_password",
        },
    ],
    "Admin - Operations": [
        {
            "method": "GET",
            "endpoint": "/api/admin/operations/health",
            "description": "System health status including service availability",
            "roles": ["operations", "admin", "super_admin"],
        },
        {
            "method": "GET",
            "endpoint": "/api/admin/operations/broker-status",
            "description": "Broker connectivity and status information",
            "roles": ["operations", "admin", "super_admin"],
        },
        {
            "method": "GET",
            "endpoint": "/api/admin/operations/active-connections",
            "description": "List of active connections to the system",
            "roles": ["operations", "admin", "super_admin"],
        },
        {
            "method": "GET",
            "endpoint": "/api/admin/operations/deployment-status",
            "description": "Current deployment status and version info",
            "roles": ["operations", "admin", "super_admin"],
        },
    ],
    "Admin - Risk Management": [
        {
            "method": "GET",
            "endpoint": "/api/admin/risk/overview",
            "description": "Portfolio risk overview for all users",
            "roles": ["risk_manager", "admin", "super_admin"],
        },
        {
            "method": "GET",
            "endpoint": "/api/admin/risk/breaches",
            "description": "Risk limit breaches and violations",
            "roles": ["risk_manager", "admin", "super_admin"],
        },
        {
            "method": "GET",
            "endpoint": "/api/admin/risk/limits/{user_id}",
            "description": "Get risk limits for specific user",
            "roles": ["risk_manager", "admin", "super_admin"],
            "parameters": "user_id (URL parameter)",
        },
        {
            "method": "PUT",
            "endpoint": "/api/admin/risk/limits/{user_id}",
            "description": "Update risk limits for specific user",
            "roles": ["admin", "super_admin"],
            "parameters": "max_position_size, max_daily_loss, max_leverage",
        },
    ],
    "Admin - Users & Licenses": [
        {
            "method": "GET",
            "endpoint": "/api/admin/users",
            "description": "List all users in the system",
            "roles": ["admin", "super_admin"],
        },
        {
            "method": "POST",
            "endpoint": "/api/admin/users",
            "description": "Create new user account",
            "roles": ["admin", "super_admin"],
            "parameters": "email, password, role, display_name",
        },
        {
            "method": "GET",
            "endpoint": "/api/admin/users/{user_id}",
            "description": "Get details for specific user",
            "roles": ["admin", "super_admin"],
        },
        {
            "method": "PUT",
            "endpoint": "/api/admin/users/{user_id}/status",
            "description": "Update user account status (active/inactive)",
            "roles": ["admin", "super_admin"],
        },
        {
            "method": "PUT",
            "endpoint": "/api/admin/users/{user_id}/role",
            "description": "Update user role assignment",
            "roles": ["admin", "super_admin"],
        },
        {
            "method": "GET",
            "endpoint": "/api/admin/users-licenses/licenses",
            "description": "List all active licenses",
            "roles": ["admin", "super_admin"],
        },
        {
            "method": "POST",
            "endpoint": "/api/admin/users-licenses/licenses",
            "description": "Create new license",
            "roles": ["admin", "super_admin"],
        },
        {
            "method": "DELETE",
            "endpoint": "/api/admin/users-licenses/licenses/{license_id}",
            "description": "Revoke/delete specific license",
            "roles": ["admin", "super_admin"],
        },
    ],
    "Admin - AI Agents": [
        {
            "method": "GET",
            "endpoint": "/api/admin/agents",
            "description": "List all deployed trading agents",
            "roles": ["admin", "super_admin"],
        },
        {
            "method": "POST",
            "endpoint": "/api/admin/agents",
            "description": "Deploy new trading agent",
            "roles": ["admin", "super_admin"],
            "parameters": "name, strategy, config (JSON)",
        },
        {
            "method": "PUT",
            "endpoint": "/api/admin/agents/{agent_id}",
            "description": "Update existing agent configuration",
            "roles": ["admin", "super_admin"],
        },
        {
            "method": "DELETE",
            "endpoint": "/api/admin/agents/{agent_id}",
            "description": "Remove/undeploy trading agent",
            "roles": ["admin", "super_admin"],
        },
    ],
    "Admin - Performance & Audit": [
        {
            "method": "GET",
            "endpoint": "/api/admin/performance-audit/overview",
            "description": "Performance audit overview and statistics",
            "roles": ["admin", "super_admin"],
        },
        {
            "method": "GET",
            "endpoint": "/api/admin/performance-audit/audit-logs",
            "description": "System audit logs with filtering",
            "roles": ["admin", "super_admin"],
        },
        {
            "method": "GET",
            "endpoint": "/api/admin/performance-audit/audit-trail",
            "description": "Detailed audit trail of all system changes",
            "roles": ["admin", "super_admin"],
        },
    ],
}


@router.get("/routes", status_code=status.HTTP_200_OK)
async def get_routes_documentation(
    services: ServerServiceContainer = Depends(get_services),
) -> dict:
    """
    Get comprehensive API routes documentation.
    
    Returns all available API endpoints grouped by category with:
    - HTTP method
    - Endpoint path
    - Description
    - Required roles
    - Parameters (if applicable)
    - Example usage (if available)
    """
    return {
        "title": "TradeAdviser API Routes Documentation",
        "version": "1.0.0",
        "description": "Complete reference of all available API endpoints for the TradeAdviser platform",
        "base_url": "/api",
        "authentication": {
            "type": "Bearer Token",
            "header": "Authorization: Bearer <access_token>",
            "token_duration": "30 minutes (access), 30 days (refresh)",
        },
        "routes": ROUTES_DOCUMENTATION,
        "usage_guide": {
            "step_1_login": "POST /api/auth/login with credentials to get access_token and refresh_token",
            "step_2_use_token": "Include access_token in Authorization header for protected routes",
            "step_3_refresh": "When access_token expires, use refresh_token to get a new one via POST /api/auth/refresh",
        },
    }


@router.get("/routes/by-role/{role}", status_code=status.HTTP_200_OK)
async def get_routes_by_role(
    role: str,
    services: ServerServiceContainer = Depends(get_services),
) -> dict:
    """
    Get API routes filtered by user role.
    
    Returns only the endpoints that are accessible by the specified role.
    Supported roles: trader, risk_manager, operations, admin, super_admin
    """
    role = role.lower()
    valid_roles = ["trader", "risk_manager", "operations", "admin", "super_admin"]
    
    if role not in valid_roles:
        return {
            "error": f"Invalid role. Valid roles are: {', '.join(valid_roles)}",
            "status": 400,
        }

    filtered_routes = {}
    for category, endpoints in ROUTES_DOCUMENTATION.items():
        filtered_endpoints = [
            endpoint
            for endpoint in endpoints
            if endpoint["roles"][0] == "public" or role in endpoint["roles"]
        ]
        if filtered_endpoints:
            filtered_routes[category] = filtered_endpoints

    return {
        "role": role,
        "title": f"TradeAdviser API Routes for {role.upper()}",
        "routes": filtered_routes,
    }


@router.get("/openapi", status_code=status.HTTP_200_OK)
async def get_openapi_info(
    services: ServerServiceContainer = Depends(get_services),
) -> dict:
    """
    Get OpenAPI/Swagger information about the API.
    
    Useful for API client generation and documentation tools.
    """
    return {
        "info": {
            "title": "TradeAdviser API",
            "version": "1.0.0",
            "description": "Intelligent Trading Advisory Platform API",
        },
        "servers": [
            {"url": "http://localhost:8000", "description": "Development"},
            {"url": "https://api.tradeadviser.com", "description": "Production"},
        ],
        "components": {
            "securitySchemes": {
                "BearerAuth": {
                    "type": "http",
                    "scheme": "bearer",
                    "bearerFormat": "JWT",
                }
            }
        },
    }
