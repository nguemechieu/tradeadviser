import hashlib
import json
import os
import platform
from datetime import datetime


class LicenseManager:

    def __init__(self, license_file=None):
        self.license_file = license_file or os.path.expanduser("~/.tradeadviser/license.json")

    def get_device_id(self):
        raw = platform.node() + platform.system()
        return hashlib.sha256(raw.encode()).hexdigest()

    def load_license(self):
        if not os.path.exists(self.license_file):
            return None
        with open(self.license_file, "r") as f:
            return json.load(f)

    def validate(self):
        data = self.load_license()

        if not data:
            return False, "No license found"

        if data.get("device_id") != self.get_device_id():
            return False, "Invalid device"

        expiry = data.get("expires_at")
        if expiry:
            if datetime.now() > datetime.fromisoformat(expiry):
                return False, "License expired"

        return True, "Valid license"