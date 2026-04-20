import requests
import json

# Test super admin login
url = "http://localhost:8000/api/auth/login"
payload = {
    "identifier": "superadmin",
    "password": "SuperAdmin@2026",
    "remember_me": True
}

try:
    response = requests.post(url, json=payload)
    print(f"Status Code: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
    
    if response.status_code == 200:
        print("\n✓ Super admin account exists and login successful!")
    else:
        print("\n✗ Login failed")
except Exception as e:
    print(f"Error: {e}")
