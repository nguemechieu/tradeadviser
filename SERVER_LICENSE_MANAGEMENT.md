# Server-Side License Management System

## Overview

The **License Management System** handles user subscriptions and license key generation on the server. Users purchase licenses using Visa, Mastercard, or cryptocurrency, and receive license keys via email that they activate on their desktop application.

## Architecture

```
┌─────────────────────────────────────────────────────┐
│         USER PURCHASE FLOW                          │
├─────────────────────────────────────────────────────┤
│                                                     │
│  Desktop/Web UI                                     │
│      ↓ Select license type & payment method         │
│      ↓ Enter payment details (card/crypto)          │
│      ↓ POST /api/licenses/purchase                  │
│                                                     │
│  Server                                             │
│      ↓ Payment Service processes payment            │
│      ↓ Stripe/PayPal/CryptoProcessor handles $      │
│      ↓ License Service generates license key        │
│      ↓ Email Service sends license via email        │
│                                                     │
│  User                                               │
│      ↓ Receives email with license key              │
│      ↓ Opens desktop app                            │
│      ↓ Paste key in Settings → License              │
│      ↓ POST /api/licenses/activate                  │
│                                                     │
│  Server                                             │
│      ↓ Verifies license key                         │
│      ↓ Activates on device                          │
│      ↓ Returns features list                        │
│                                                     │
│  Desktop App                                        │
│      ↓ Unlocks all features for license type       │
│      ↓ User can start trading!                      │
│                                                     │
└─────────────────────────────────────────────────────┘
```

---

## License Types & Features

### Trial License (Free)
- **Duration**: 30 days
- **Price**: Free ($0.00)
- **Features**:
  - Basic trading (1 strategy, 1 broker)
  - Historical data access (1 year)
- **Use Case**: Users testing the platform

### Basic License ($9.99/month)
- **Duration**: 1 month
- **Price**: $9.99 USD
- **Features**:
  - Basic trading
  - Multiple strategies (up to 5)
  - Multiple brokers (up to 3)
  - Historical data (past 1 year)
- **Use Case**: Individual traders, small portfolios

### Pro License ($29.99/month)
- **Duration**: 1 month
- **Price**: $29.99 USD
- **Features**:
  - All Basic features
  - Advanced analytics (ML models, backtesting)
  - Portfolio monitoring (real-time)
  - Risk management (position sizing, stop-loss)
  - API access (REST API)
  - Custom technical indicators
- **Use Case**: Active traders, portfolio managers

### Enterprise License (Custom Pricing)
- **Duration**: 1 year (customizable)
- **Price**: Custom (contact sales)
- **Features**:
  - All Pro features
  - White-label (custom branding)
  - Team management (multiple users)
  - Priority 24/7 support
  - Dedicated account manager
  - Custom broker integrations
- **Use Case**: Financial institutions, hedge funds

---

## Payment Methods

### 1. Credit/Debit Card (Visa, Mastercard)
- **Processor**: Stripe
- **Processing**: Immediate
- **Fees**: Standard Stripe fees (2.9% + $0.30)
- **SSl**: Full PCI compliance
- **Webhook**: Automatic confirmation

**Flow**:
```
User enters card → Frontend tokenizes with Stripe → 
POST /api/licenses/purchase with card_token → 
Server processes with Stripe → 
License created immediately → Email sent
```

### 2. PayPal
- **Processor**: PayPal SDK
- **Processing**: User redirected to PayPal
- **Fees**: PayPal standard fees (2.2% + $0.30)
- **Webhook**: PayPal IPN for confirmation
- **Security**: OAuth 2.0

**Flow**:
```
User selects PayPal → 
POST /api/licenses/purchase →
Server creates PayPal payment request →
Return redirect URL →
User redirected to PayPal →
User confirms payment →
PayPal webhook → Server creates license → Email sent
```

### 3. Cryptocurrency (Bitcoin, Ethereum, USDC, USDT, Litecoin)
- **Processor**: Coinbase Commerce
- **Processing**: User sends crypto to wallet
- **Confirmation**: On-chain confirmation
- **Fees**: Fixed network fees (minimal)
- **Webhook**: Blockchain confirmation

**Flow**:
```
User selects crypto + currency →
POST /api/licenses/purchase with crypto_currency →
Server requests wallet address from Coinbase →
Return wallet address & QR code →
User sends crypto →
On-chain confirmation →
Webhook triggers →
Server creates license → Email sent
```

---

## License Key Format

**Format**: `TRADE-XXXXX-XXXXX-XXXXX-XXXXX`

- **Prefix**: `TRADE` (always)
- **Segments**: 4 groups of 5 alphanumeric characters
- **Example**: `TRADE-A1B2C-D3E4F-G5H6I-J7K8L`
- **Uniqueness**: Generated from user ID + license type + timestamp
- **Validation**: Format check on POST /api/licenses/activate

---

## REST API Endpoints

### Purchase License

**POST /api/licenses/purchase**

**Request**:
```json
{
  "license_type": "pro",
  "payment_method": "card|paypal|crypto",
  "card_token": "tok_visa",              // Required for card
  "crypto_currency": "btc"                // Required for crypto
}
```

**Response (Card - Success)**:
```json
{
  "success": true,
  "message": "License purchased successfully",
  "payment_id": "pay_abc123xyz",
  "license_key": "TRADE-A1B2C-D3E4F-G5H6I-J7K8L",
  "expires_at": "2026-05-26T10:30:45Z",
  "features": [
    "basic_trading",
    "multiple_strategies",
    "multiple_brokers",
    "historical_data",
    "advanced_analytics",
    "portfolio_monitoring",
    "risk_management",
    "api_access",
    "custom_indicators"
  ]
}
```

**Response (PayPal - Pending)**:
```json
{
  "success": true,
  "message": "Redirect to PayPal to complete payment",
  "payment_id": "pay_def456uvw",
  "redirect_url": "https://www.paypal.com/checkout?token=EC-..."
}
```

**Response (Crypto - Pending)**:
```json
{
  "success": true,
  "message": "Send BTC to complete payment",
  "payment_id": "pay_ghi789xyz",
  "currency": "btc",
  "amount_crypto": 0.00063,
  "amount_usd": 29.99,
  "wallet_address": "1A1z7agoat...",
  "expires_at": "2026-04-26T11:30:45Z"
}
```

### Activate License

**POST /api/licenses/activate**

Requires authentication.

**Request**:
```json
{
  "license_key": "TRADE-A1B2C-D3E4F-G5H6I-J7K8L",
  "hardware_id": "device_uuid"  // Optional, defaults to "default_device"
}
```

**Response**:
```json
{
  "success": true,
  "message": "License activated successfully",
  "features": [
    "basic_trading",
    "multiple_strategies",
    ...
  ]
}
```

### Verify License

**GET /api/licenses/verify?license_key=TRADE-A1B2C-D3E4F-G5H6I-J7K8L**

Does NOT require authentication.

**Response**:
```json
{
  "valid": true,
  "status": "active|expired|revoked",
  "license_type": "pro",
  "days_remaining": 14,
  "features": [
    "basic_trading",
    "multiple_strategies",
    ...
  ],
  "message": "License active. 14 days remaining."
}
```

### Get License Status

**GET /api/licenses/status/{license_key}**

Requires authentication.

**Response**:
```json
{
  "valid": true,
  "status": "active",
  "license_type": "pro",
  "days_remaining": 14,
  "features": [...],
  "message": "License active. 14 days remaining.",
  "license_key": "TRADE-A1B2C-D3E4F-G5H6I-J7K8L"
}
```

### List User's Licenses

**GET /api/licenses/list**

Requires authentication.

**Response**:
```json
{
  "count": 2,
  "licenses": [
    {
      "license_key": "TRADE-A1B2C-D3E4F-G5H6I-J7K8L",
      "type": "pro",
      "status": "active",
      "created_at": "2026-03-26T10:30:45Z",
      "expires_at": "2026-05-26T10:30:45Z",
      "features": [...]
    },
    {
      "license_key": "TRADE-M9N0O-P1Q2R-S3T4U-V5W6X",
      "type": "trial",
      "status": "expired",
      "created_at": "2026-02-24T10:30:45Z",
      "expires_at": "2026-03-26T10:30:45Z",
      "features": [...]
    }
  ]
}
```

### Renew License

**POST /api/licenses/renew/{license_key}**

Requires authentication.

**Response**:
```json
{
  "success": true,
  "message": "License renewed successfully",
  "expires_at": "2026-06-26T10:30:45Z"
}
```

### Revoke License

**POST /api/licenses/revoke/{license_key}?reason=fraud**

Requires admin authentication.

**Response**:
```json
{
  "success": true,
  "message": "License revoked successfully"
}
```

### Get Pricing

**GET /api/licenses/pricing**

Public endpoint (no auth required).

**Response**:
```json
{
  "pricing": {
    "trial": {
      "price_usd": 0.00,
      "features": ["basic_trading", "historical_data"]
    },
    "basic": {
      "price_usd": 9.99,
      "features": ["basic_trading", "multiple_strategies", "multiple_brokers", "historical_data"]
    },
    "pro": {
      "price_usd": 29.99,
      "features": [...]
    },
    "enterprise": {
      "price_usd": null,
      "features": [...]
    }
  },
  "currency": "USD",
  "last_updated": "2026-04-26T10:30:45Z"
}
```

### Get Features

**GET /api/licenses/features**

Public endpoint (no auth required).

**Response**:
```json
{
  "features": {
    "trial": ["basic_trading", "historical_data"],
    "basic": ["basic_trading", "multiple_strategies", ...],
    "pro": [...],
    "enterprise": [...]
  },
  "last_updated": "2026-04-26T10:30:45Z"
}
```

### Get Payment Methods

**GET /api/licenses/payment-methods**

Public endpoint (no auth required).

**Response**:
```json
{
  "payment_methods": [
    {
      "method": "card",
      "name": "Credit/Debit Card",
      "description": "Visa, Mastercard, and other major cards",
      "supported": true
    },
    {
      "method": "paypal",
      "name": "PayPal",
      "description": "Fast and secure PayPal payments",
      "supported": true
    },
    {
      "method": "crypto",
      "name": "Cryptocurrency",
      "description": "Bitcoin, Ethereum, USDC, USDT, and Litecoin",
      "supported": true,
      "currencies": ["btc", "eth", "ltc", "usdc", "usdt"]
    }
  ]
}
```

---

## Email Notifications

### 1. License Delivery Email

**Sent After**: Purchase confirmation (card) or payment confirmation (PayPal/Crypto)

**Contains**:
- License key (TRADE-XXXXX-XXXXX-XXXXX-XXXXX)
- License type (trial/basic/pro/enterprise)
- Expiration date
- Feature list
- Activation instructions

**Example Subject**: "Your PRO License Key - TradeAdviser"

### 2. Payment Confirmation Email

**Sent After**: Successful payment

**Contains**:
- Transaction ID
- Amount paid
- License type
- Payment method used
- Note about license delivery email

**Example Subject**: "Payment Confirmed - TradeAdviser License Purchase"

### 3. License Expiration Reminder

**Sent**: 7 days before expiration

**Contains**:
- License key
- Days remaining (7)
- Renewal link
- Feature list

**Example Subject**: "Your PRO License Expires in 7 Days"

### 4. Renewal Invitation

**Sent**: After expiration (if enabled)

**Contains**:
- Current license key
- Renewal discount (if applicable)
- Renewal link
- Benefits of renewal

**Example Subject**: "Renew Your PRO License - Special Offer!"

---

## Desktop App Integration

### Check License Status

The desktop app should check license status on startup:

```python
import requests

async def check_license():
    license_key = read_from_settings("license_key")
    
    response = await requests.get(
        "https://api.tradeadviser.io/api/licenses/verify",
        params={"license_key": license_key}
    )
    
    data = response.json()
    
    if not data["valid"]:
        show_license_error(data["message"])
        return False
    
    # Store features in app state
    app_state.features = data["features"]
    app_state.days_remaining = data["days_remaining"]
    
    # Show expiration warning if < 7 days
    if data["days_remaining"] < 7:
        show_renewal_reminder(data["days_remaining"])
    
    return True
```

### Activate License

When user enters license key:

```python
async def activate_license(license_key):
    response = await requests.post(
        "https://api.tradeadviser.io/api/licenses/activate",
        json={
            "license_key": license_key,
            "hardware_id": get_hardware_id()
        },
        headers={"Authorization": f"Bearer {jwt_token}"}
    )
    
    if response.status_code == 200:
        data = response.json()
        save_to_settings("license_key", license_key)
        app_state.features = data["features"]
        show_success("License activated!")
    else:
        show_error(response.json()["detail"])
```

### Check Feature Availability

```python
def is_feature_enabled(feature_name):
    return feature_name in app_state.features

# Usage
if is_feature_enabled("api_access"):
    enable_api_endpoints()
    
if is_feature_enabled("advanced_analytics"):
    enable_ml_models()
    enable_backtesting()
```

---

## Database Schema

```sql
-- Licenses table
CREATE TABLE licenses (
    id UUID PRIMARY KEY,
    license_key VARCHAR(50) UNIQUE NOT NULL,
    user_id UUID NOT NULL REFERENCES users(id),
    type VARCHAR(20) NOT NULL,          -- trial, basic, pro, enterprise
    status VARCHAR(20) NOT NULL,        -- active, expired, revoked, pending
    created_at TIMESTAMP DEFAULT NOW(),
    expires_at TIMESTAMP NOT NULL,
    features TEXT[] NOT NULL,           -- Array of feature strings
    activations JSONB,                  -- Array of activation records
    revoked_at TIMESTAMP,
    revocation_reason TEXT,
    notes TEXT
);

-- Payments table
CREATE TABLE payments (
    id VARCHAR(50) PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES users(id),
    license_key VARCHAR(50) REFERENCES licenses(license_key),
    amount_usd DECIMAL(10, 2),
    currency VARCHAR(10),
    method VARCHAR(20),                 -- card, paypal, crypto
    status VARCHAR(20),                 -- completed, failed, refunded, pending
    created_at TIMESTAMP DEFAULT NOW(),
    completed_at TIMESTAMP,
    transaction_id VARCHAR(100),
    metadata JSONB
);

-- Create indexes
CREATE INDEX idx_licenses_user ON licenses(user_id);
CREATE INDEX idx_licenses_key ON licenses(license_key);
CREATE INDEX idx_licenses_status ON licenses(status);
CREATE INDEX idx_payments_user ON payments(user_id);
CREATE INDEX idx_payments_status ON payments(status);
```

---

## Webhook Handlers

### Stripe Webhook

```python
@app.post("/webhooks/stripe")
async def stripe_webhook(request: Request):
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")
    
    event = stripe.Webhook.construct_event(payload, sig_header, endpoint_secret)
    
    if event["type"] == "charge.succeeded":
        payment_id = event["data"]["object"]["id"]
        # Mark payment as completed
        # Create license
        # Send email
    
    return {"received": True}
```

### PayPal Webhook (IPN)

```python
@app.post("/webhooks/paypal")
async def paypal_webhook(request: Request):
    data = await request.form()
    
    if data.get("txn_type") == "web_accept":
        # Payment completed
        payment_id = data.get("txn_id")
        # Mark payment as completed
        # Create license
        # Send email
    
    return {"received": True}
```

### Coinbase Commerce Webhook

```python
@app.post("/webhooks/crypto")
async def crypto_webhook(request: Request):
    payload = await request.json()
    sig_header = request.headers.get("X-CC-Webhook-Signature")
    
    if verify_signature(payload, sig_header):
        if payload["type"] == "charge:confirmed":
            payment_id = payload["data"]["id"]
            # Mark payment as completed
            # Create license
            # Send email
    
    return {"received": True}
```

---

## Configuration

Required environment variables:

```bash
# Email Service
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SENDER_EMAIL=licenses@tradeadviser.io
SENDER_PASSWORD=<app-password>

# Stripe
STRIPE_API_KEY=sk_live_...
STRIPE_WEBHOOK_SECRET=whsec_...

# PayPal
PAYPAL_CLIENT_ID=...
PAYPAL_CLIENT_SECRET=...

# Coinbase Commerce
COINBASE_COMMERCE_API_KEY=...
```

---

## Security Considerations

1. **PCI Compliance**: Use Stripe tokenization, never handle raw card data
2. **License Keys**: Generated with high entropy, validated on every use
3. **Rate Limiting**: Implement rate limits on purchase and activation endpoints
4. **HTTPS Only**: All license endpoints require HTTPS
5. **JWT Tokens**: User authentication via JWT in Authorization header
6. **Webhook Verification**: Verify signatures on all webhook events
7. **Database Encryption**: Store payment details encrypted
8. **Audit Logging**: Log all license creation, activation, revocation

---

## Roadmap

- [ ] Integrate with Stripe API (production)
- [ ] Integrate with PayPal SDK (production)
- [ ] Integrate with Coinbase Commerce (production)
- [ ] Database migration for licenses/payments tables
- [ ] Webhook handlers for payment providers
- [ ] Admin dashboard for license management
- [ ] License transfer between users
- [ ] Upgrade/downgrade license type
- [ ] Discount codes and promo codes
- [ ] Auto-renewal on payment method
- [ ] Churn reduction emails and retry logic
