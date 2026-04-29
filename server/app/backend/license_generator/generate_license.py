import json
from datetime import datetime, timedelta
from security.license_manager import LicenseManager

lm = LicenseManager()

def generate_license(days=30):
    device_id = lm.get_device_id()

    license_data = {
        "device_id": device_id,
        "expires_at": (datetime.utcnow() + timedelta(days=days)).isoformat()
    }

    with open("license.json", "w") as f:
        json.dump(license_data, f, indent=2)

    print("License generated!")

generate_license(30)