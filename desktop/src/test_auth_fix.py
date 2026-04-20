#!/usr/bin/env python3
"""
Diagnostic script to test the authentication fixes for platform sync.

This script validates:
1. Credential validation
2. Server connectivity
3. Authentication flow
4. Concurrent task handling
"""

import asyncio
import json
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from server_api_client import ServerAPIClient
from ui.components.services.platform_sync_service import (
    PlatformSyncService,
    PlatformSyncStore,
    PlatformSyncError,
)


def print_section(title):
    """Print a formatted section header."""
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")


def print_test(name, passed, message=""):
    """Print a test result."""
    status = "✓ PASS" if passed else "✗ FAIL"
    print(f"  {status}: {name}")
    if message:
        print(f"    → {message}")


async def test_server_connectivity(server_url: str = "http://localhost:8000"):
    """Test if the server is reachable."""
    print_section("1. Server Connectivity Test")
    
    client = ServerAPIClient(server_url)
    print(f"  Testing connection to: {server_url}")
    
    try:
        # Try to call a simple endpoint that doesn't require auth
        import aiohttp
        timeout = aiohttp.ClientTimeout(total=5)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(f"{server_url}/docs") as resp:
                connected = resp.status in [200, 404]
                print_test("Server reachable", connected, f"Status: {resp.status}")
                return connected
    except Exception as e:
        print_test("Server reachable", False, f"Error: {str(e)}")
        return False


async def test_credential_validation():
    """Test credential validation logic."""
    print_section("2. Credential Validation Test")
    
    sync_service = PlatformSyncService()
    
    # Test 1: Missing email
    test_profile = {
        "base_url": "http://localhost:8000",
        "email": "",
        "password": "password123",
    }
    is_valid, msg = sync_service.validate_credentials(test_profile)
    print_test("Detects missing email", not is_valid, msg)
    
    # Test 2: Missing password
    test_profile = {
        "base_url": "http://localhost:8000",
        "email": "user@example.com",
        "password": "",
    }
    is_valid, msg = sync_service.validate_credentials(test_profile)
    print_test("Detects missing password", not is_valid, msg)
    
    # Test 3: Invalid server URL
    test_profile = {
        "base_url": "invalid-url",
        "email": "user@example.com",
        "password": "password123",
    }
    is_valid, msg = sync_service.validate_credentials(test_profile)
    print_test("Detects invalid URL format", not is_valid, msg)
    
    # Test 4: Valid credentials
    test_profile = {
        "base_url": "http://localhost:8000",
        "email": "user@example.com",
        "password": "password123",
    }
    is_valid, msg = sync_service.validate_credentials(test_profile)
    print_test("Accepts valid credentials", is_valid, msg)


async def test_api_client_login():
    """Test the updated API client login."""
    print_section("3. API Client Login Test")
    
    client = ServerAPIClient("http://localhost:8000")
    
    # Test 1: Empty credentials
    result = await client.login("", "")
    passed = not result.get("success")
    print_test("Rejects empty credentials", passed, result.get("message"))
    
    # Test 2: Invalid credentials (should fail with server)
    result = await client.login("invalid@test.com", "wrongpassword")
    passed = not result.get("success")
    print_test(
        "Invalid credentials rejected",
        passed,
        result.get("message", "No error message"),
    )


async def test_async_locking():
    """Test that async locking prevents concurrent auth attempts."""
    print_section("4. Async Locking Test")
    
    sync_service = PlatformSyncService()
    profile = sync_service.load_profile()
    
    # Check that the lock exists
    has_lock = hasattr(sync_service, "_auth_lock")
    print_test("Auth lock exists", has_lock)
    
    # Check that the lock is an asyncio.Lock
    is_lock = isinstance(sync_service._auth_lock, asyncio.Lock)
    print_test("Auth lock is asyncio.Lock", is_lock)
    
    # Test that multiple tasks can safely access token checking
    async def check_token(delay: float):
        await asyncio.sleep(delay)
        # This should safely acquire the lock even if multiple tasks call it
        return await sync_service._ensure_access_token(profile)
    
    try:
        # Run 3 concurrent tasks to check for lock contention
        results = await asyncio.gather(
            check_token(0.0),
            check_token(0.01),
            check_token(0.02),
            return_exceptions=True,
        )
        
        # Check if any task failed with "Cannot enter into task" error
        has_lock_error = any(
            isinstance(r, Exception) and "Cannot enter into task" in str(r)
            for r in results
        )
        print_test("Concurrent token checks work", not has_lock_error)
    except Exception as e:
        print_test("Concurrent token checks work", False, str(e))


async def test_error_messages():
    """Test that error messages are clear and helpful."""
    print_section("5. Error Message Quality Test")
    
    sync_service = PlatformSyncService()
    
    # Create a profile with invalid credentials
    store = PlatformSyncStore()
    store.save_profile({
        "base_url": "http://invalid-server:9999",
        "email": "",
        "password": "test",
    })
    
    sync_service.store = store
    profile = sync_service.load_profile()
    
    # Try to ensure token and check error message
    try:
        await sync_service._ensure_access_token(profile)
        print_test("Error handling", False, "Should have raised error")
    except PlatformSyncError as exc:
        error_msg = str(exc)
        has_helpful_msg = (
            "configuration" in error_msg.lower()
            or "email" in error_msg.lower()
            or "not configured" in error_msg.lower()
        )
        print_test("Error message is helpful", has_helpful_msg, error_msg)
    except Exception as e:
        print_test("Error handling", False, f"Unexpected error: {type(e).__name__}")


async def main():
    """Run all diagnostic tests."""
    print("\n" + "=" * 60)
    print("  SOPOTEK PLATFORM SYNC - AUTHENTICATION FIX DIAGNOSTICS")
    print("=" * 60)
    
    # Test connectivity
    server_ok = await test_server_connectivity()
    
    # Always run validation tests (don't depend on server)
    await test_credential_validation()
    await test_api_client_login()
    await test_async_locking()
    await test_error_messages()
    
    print_section("Summary")
    print("""
This diagnostic script tested:
  1. Server connectivity
  2. Credential validation logic
  3. API client login handling
  4. Async locking mechanism
  5. Error message quality

If you see mostly ✓ PASS results, the authentication fixes are working.

Next steps:
  - If server is not reachable: Check that sqs_server is running
  - If credential validation fails: Check your sync settings
  - If login fails: Verify your email and password are correct
  - For concurrent task errors: The async lock should prevent them now
    """)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user.")
    except Exception as e:
        print(f"\n\nFatal error: {e}")
        import traceback
        traceback.print_exc()
