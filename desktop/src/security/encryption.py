from __future__ import annotations

import os
import shutil
from pathlib import Path

from cryptography.fernet import Fernet
from dotenv import load_dotenv


class EncryptionManager:
    DEFAULT_ENV_VAR = "SOPOTEK_CREDENTIAL_KEY"

    def __init__(self, key: bytes | str):
        normalized_key = key.encode("utf-8") if isinstance(key, str) else key
        self.fernet = Fernet(normalized_key)

    def encrypt(self, value: str) -> str:
        return self.fernet.encrypt(str(value).encode("utf-8")).decode("utf-8")

    def decrypt(self, value: str) -> str:
        return self.fernet.decrypt(str(value).encode("utf-8")).decode("utf-8")

    @classmethod
    def from_environment(cls, env_var: str | None = None, env_path: str | Path | None = None):
        resolved_var = str(env_var or cls.DEFAULT_ENV_VAR).strip() or cls.DEFAULT_ENV_VAR
        load_dotenv(dotenv_path=env_path)
        key = os.getenv(resolved_var)
        if not key:
            key = cls._provision_key(resolved_var, env_path=env_path)
        return cls(key)

    @classmethod
    def _provision_key(cls, env_var: str, env_path: str | Path | None = None) -> str:
        key = Fernet.generate_key().decode("utf-8")
        os.environ[env_var] = key

        target_path = Path(env_path) if env_path else Path(".env")
        existing_lines = []
        
        # Handle case where target_path is a directory instead of a file
        if target_path.exists() and target_path.is_dir():
            # If .env is a directory, remove it and create the file instead
            shutil.rmtree(target_path, ignore_errors=True)
        
        if target_path.exists() and target_path.is_file():
            existing_lines = target_path.read_text(encoding="utf-8").splitlines()

        filtered_lines = [line for line in existing_lines if not line.startswith(f"{env_var}=")]
        filtered_lines.append(f"{env_var}={key}")
        target_path.write_text("\n".join(filtered_lines) + "\n", encoding="utf-8")
        return key

