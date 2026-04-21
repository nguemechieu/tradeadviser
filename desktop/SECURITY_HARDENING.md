# TradeAdviser Desktop - Security Hardening Guide

## 🔐 Security Overview

This guide provides comprehensive security hardening recommendations for deploying TradeAdviser Desktop in production environments.

---

## 1. Credential Management

### 1.1 Environment Variables

**Do Not Hardcode Credentials**

❌ **WRONG:**
```python
API_KEY = "sk-1234567890abcdef"
BROKER_SECRET = "secret123"
DB_PASSWORD = "password"
```

✅ **CORRECT:**
```python
import os
from dotenv import load_dotenv

load_dotenv()  # Load from .env file

API_KEY = os.getenv("API_KEY")
BROKER_SECRET = os.getenv("BROKER_SECRET")
DB_PASSWORD = os.getenv("DB_PASSWORD")

if not API_KEY:
    raise RuntimeError("API_KEY not configured in environment")
```

### 1.2 .env File Security

```bash
# Permissions: Owner read/write only (600)
chmod 600 .env

# Add to .gitignore to prevent accidental commits
echo ".env" >> .gitignore
echo ".env.local" >> .gitignore
echo ".env.production" >> .gitignore
```

### 1.3 Credential Rotation

```python
def rotate_credentials():
    """Rotate API credentials periodically"""
    from datetime import datetime, timedelta
    import os
    
    last_rotation = datetime.fromisoformat(os.getenv("LAST_CREDENTIAL_ROTATION", ""))
    if datetime.now() - last_rotation > timedelta(days=90):
        logger.warning("Credentials should be rotated")
        # Prompt user to update credentials
        return False
    return True
```

---

## 2. Authentication & Authorization

### 2.1 OAuth2 Implementation

```python
from fastapi_oauth2 import OAuth2PasswordBearer, OAuth2PasswordRequestForm
import jwt
from datetime import datetime, timedelta

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    """Create JWT access token"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(hours=24)
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(
        to_encode, 
        os.getenv("JWT_SECRET_KEY"), 
        algorithm="HS256"
    )
    return encoded_jwt

async def verify_token(token: str = Depends(oauth2_scheme)):
    """Verify JWT token"""
    try:
        payload = jwt.decode(
            token, 
            os.getenv("JWT_SECRET_KEY"), 
            algorithms=["HS256"]
        )
        username = payload.get("sub")
        if username is None:
            raise HTTPException(status_code=401, detail="Invalid token")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")
    return username
```

### 2.2 Password Hashing

```python
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def hash_password(password: str) -> str:
    """Hash password with bcrypt"""
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify password"""
    return pwd_context.verify(plain_password, hashed_password)
```

---

## 3. Data Protection

### 3.1 Encryption at Rest

```python
from cryptography.fernet import Fernet
import os

# Generate and store key securely
def setup_encryption():
    """Setup encryption key"""
    key_file = Path.home() / ".tradeadviser" / "encryption.key"
    if not key_file.exists():
        key = Fernet.generate_key()
        key_file.parent.mkdir(parents=True, exist_ok=True)
        key_file.write_bytes(key)
        os.chmod(str(key_file), 0o600)  # Owner read/write only
    return key_file.read_bytes()

cipher_suite = Fernet(setup_encryption())

def encrypt_data(data: str) -> str:
    """Encrypt sensitive data"""
    return cipher_suite.encrypt(data.encode()).decode()

def decrypt_data(encrypted_data: str) -> str:
    """Decrypt sensitive data"""
    return cipher_suite.decrypt(encrypted_data.encode()).decode()
```

### 3.2 Encryption in Transit

```python
# Always use HTTPS/TLS
import aiohttp
from ssl import create_default_context

ssl_context = create_default_context()
ssl_context.check_hostname = True
ssl_context.verify_mode = ssl.CERT_REQUIRED

async def secure_request(url: str):
    """Make secure HTTPS request"""
    connector = aiohttp.TCPConnector(ssl=ssl_context)
    async with aiohttp.ClientSession(connector=connector) as session:
        async with session.get(url) as resp:
            return await resp.json()
```

---

## 4. Input Validation & Sanitization

### 4.1 Data Validation

```python
from pydantic import BaseModel, validator, Field
import re

class TradeInput(BaseModel):
    symbol: str = Field(..., min_length=1, max_length=10)
    quantity: float = Field(..., gt=0, le=100000)
    price: float = Field(..., gt=0)
    order_type: str = Field("MARKET", pattern="^(MARKET|LIMIT|STOP)$")
    
    @validator('symbol')
    def validate_symbol(cls, v):
        # Only alphanumeric
        if not re.match(r'^[A-Z0-9]+$', v):
            raise ValueError('Invalid symbol format')
        return v.upper()
    
    @validator('quantity')
    def validate_quantity(cls, v):
        # Check for reasonable values
        if v % 1 != 0:  # Must be whole number for stocks
            raise ValueError('Quantity must be whole number')
        return int(v)
```

### 4.2 SQL Injection Prevention

```python
# Use parameterized queries, never string concatenation

# ❌ WRONG - SQL Injection vulnerable
query = f"SELECT * FROM users WHERE username = '{username}'"
result = db.execute(query)

# ✅ CORRECT - Parameterized query
query = "SELECT * FROM users WHERE username = ?"
result = db.execute(query, (username,))

# ✅ CORRECT - ORM (SQLAlchemy)
user = db.query(User).filter(User.username == username).first()
```

---

## 5. Logging & Monitoring

### 5.1 Secure Logging

```python
import logging
import json
from datetime import datetime

class SecureFormatter(logging.Formatter):
    """Formatter that redacts sensitive information"""
    
    SENSITIVE_KEYS = {
        'password', 'token', 'secret', 'key', 'credential',
        'api_key', 'api_secret', 'authorization', 'auth_token'
    }
    
    def format(self, record):
        log_data = {
            'timestamp': datetime.utcnow().isoformat(),
            'level': record.levelname,
            'message': record.getMessage(),
            'module': record.module,
        }
        
        # Redact sensitive information
        if hasattr(record, 'args') and isinstance(record.args, dict):
            filtered_args = {
                k: '***REDACTED***' if any(
                    sensitive in k.lower() 
                    for sensitive in self.SENSITIVE_KEYS
                ) else v
                for k, v in record.args.items()
            }
            log_data['args'] = filtered_args
        
        return json.dumps(log_data)
```

### 5.2 Audit Logging

```python
def audit_log(action: str, user: str, resource: str, result: str, details: dict = None):
    """Log audit trail"""
    logger.info(
        "AUDIT",
        extra={
            "action": action,  # LOGIN, TRADE_EXECUTE, CONFIG_CHANGE
            "user": user,
            "resource": resource,
            "result": result,  # SUCCESS, FAILURE
            "timestamp": datetime.utcnow().isoformat(),
            "details": details or {}
        }
    )
```

---

## 6. API Security

### 6.1 Rate Limiting

```python
from fastapi_limiter import FastAPILimiter
from fastapi_limiter.util import get_remote_address

@FastAPILimiter.limit("100/minute")
@app.get("/api/quotes")
async def get_quotes(request: Request):
    """Rate-limited API endpoint"""
    return {"quotes": [...]}
```

### 6.2 CORS Configuration

```python
from fastapi.middleware.cors import CORSMiddleware

# Restrict CORS to specific origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",  # Dev
        "https://app.tradeadviser.com",  # Prod
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST"],  # Restrict to necessary methods
    allow_headers=["Content-Type", "Authorization"],
)
```

### 6.3 CSRF Protection

```python
from fastapi.middleware import csrf

app.add_middleware(
    CSRFMiddleware,
    secret_key=os.getenv("CSRF_SECRET_KEY")
)

@app.post("/api/trades")
async def execute_trade(request: Request, trade: Trade):
    """CSRF protected endpoint"""
    # Middleware validates CSRF token automatically
    return {"status": "executed"}
```

---

## 7. Broker API Security

### 7.1 Interactive Brokers

```python
# Secure TWS connection
IBKR_CONFIG = {
    "port": 7497,  # Live
    "clientId": 1,
    "useSSL": True,  # Use SSL connection
    "verify": True,  # Verify SSL certificates
}

# Restrict API access in TWS:
# Edit → Settings → API
# - Enable "Read-Only API" for accounts that don't need trading
# - Whitelist specific IPs if possible
# - Use secure authentication
```

### 7.2 API Key Rotation

```python
def rotate_api_keys():
    """Rotate broker API keys quarterly"""
    last_rotation = get_setting("API_KEY_LAST_ROTATION")
    if (datetime.now() - last_rotation).days > 90:
        logger.warning("API keys should be rotated")
        # Notify administrator
        send_alert("API keys require rotation")
```

---

## 8. System Hardening

### 8.1 Windows System Security

```powershell
# Windows Defender
Set-MpPreference -DisableRealtimeMonitoring $false

# Windows Firewall - Allow only necessary ports
New-NetFirewallRule -DisplayName "TradeAdviser API" `
    -Direction Inbound -Protocol TCP -LocalPort 8000 -Action Allow

# Disable unnecessary services
Get-Service | Where-Object {$_.Name -match "Telemetry"} | Disable-Service

# Enable Windows Update
Set-Service -Name wuauserv -StartupType Automatic
Start-Service -Name wuauserv
```

### 8.2 File Permissions

```bash
# Restrict file permissions
chmod 700 ~/.tradeadviser  # Owner read/write/execute only
chmod 600 ~/.tradeadviser/.env
chmod 600 ~/.tradeadviser/credentials.json

# Windows equivalent (PowerShell)
$acl = Get-Acl "C:\Users\$env:USERNAME\.tradeadviser"
$acl.Access | Remove-Item
# Only allow current user
```

### 8.3 Service Account

```bash
# Run application as limited service account (not admin)
# Create service account with minimal permissions
# Run TradeAdviser service under this account

# Windows example
New-LocalUser -Name "tradeadviser-svc" -NoPassword
Add-LocalGroupMember -Group "Users" -Member "tradeadviser-svc"
# Grant only necessary permissions to this account
```

---

## 9. Backup & Disaster Recovery

### 9.1 Secure Backups

```python
import shutil
from pathlib import Path

def create_backup():
    """Create encrypted backup"""
    backup_dir = Path.home() / ".tradeadviser" / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    
    # Backup database
    db_backup = backup_dir / f"db_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.sql"
    
    # Encrypt backup
    encrypted_backup = encrypt_data(db_backup.read_text())
    
    # Store with restricted permissions
    (backup_dir / "encrypted.bak").write_text(encrypted_backup)
    os.chmod(str(backup_dir / "encrypted.bak"), 0o600)
    
    logger.info("Backup created and encrypted")
```

### 9.2 Backup Verification

```python
def verify_backup():
    """Verify backup integrity"""
    backups = list(Path.home() / ".tradeadviser" / "backups").glob("*.bak")
    
    for backup in backups:
        try:
            # Try to decrypt
            encrypted = backup.read_text()
            decrypted = decrypt_data(encrypted)
            logger.info(f"✓ Backup {backup.name} verified")
        except Exception as e:
            logger.error(f"✗ Backup {backup.name} corrupted: {e}")
```

---

## 10. Third-Party Dependencies

### 10.1 Dependency Verification

```bash
# Check for known vulnerabilities
pip install safety
safety check --json

# Update to latest secure versions
pip list --outdated
pip install --upgrade package-name

# Lock exact versions in requirements
pip freeze > requirements-locked.txt
```

### 10.2 Minimal Dependencies

```
# Only include necessary dependencies
# Remove unused packages

# Before
requirements.txt (50+ packages)

# After  
requirements-prod.txt (25 core packages only)
```

---

## 11. Security Checklist

### Pre-Deployment

- [ ] All API keys and secrets in environment variables
- [ ] .env files excluded from version control
- [ ] SSL/TLS enabled for all communications
- [ ] Input validation implemented on all endpoints
- [ ] Database queries use parameterized statements
- [ ] Logging doesn't contain sensitive data
- [ ] Passwords hashed with bcrypt
- [ ] JWT tokens use secure key and expiration
- [ ] CORS configured for specific origins
- [ ] Rate limiting implemented
- [ ] Security headers set (CSP, X-Frame-Options, etc.)
- [ ] Dependencies scanned for vulnerabilities
- [ ] Code review completed
- [ ] Penetration testing done
- [ ] Security audit completed

### Ongoing

- [ ] Monitor for security updates
- [ ] Rotate credentials quarterly
- [ ] Review access logs monthly
- [ ] Audit database access
- [ ] Test disaster recovery procedures
- [ ] Keep systems patched and updated

---

## 12. Security Resources

- **OWASP Top 10**: https://owasp.org/Top10/
- **CWE/SANS Top 25**: https://cwe.mitre.org/top25/
- **Python Security**: https://python.readthedocs.io/en/latest/library/security_warnings.html
- **FastAPI Security**: https://fastapi.tiangolo.com/tutorial/security/
- **Cryptography Library**: https://cryptography.io/

---

## Contact & Reporting

**Found a security vulnerability?**

Please report security issues responsibly:
- Email: security@tradeadviser.com
- Do not create public issues for security vulnerabilities
- Allow time for remediation before disclosure

---

**Last Updated**: 2024
**Status**: Production Ready
