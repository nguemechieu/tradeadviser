#!/bin/bash
# Security Audit Script for TradeAdviser
# Scans for common vulnerabilities and security issues

set -e

echo "🔐 TradeAdviser Security Audit"
echo "=============================="
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

FAILED_CHECKS=0
PASSED_CHECKS=0
WARNING_CHECKS=0

# Helper functions
check_pass() {
    echo -e "${GREEN}✓${NC} $1"
    ((PASSED_CHECKS++))
}

check_fail() {
    echo -e "${RED}✗${NC} $1"
    ((FAILED_CHECKS++))
}

check_warn() {
    echo -e "${YELLOW}⚠${NC} $1"
    ((WARNING_CHECKS++))
}

# 1. Check for hardcoded secrets
echo "1. Scanning for hardcoded secrets..."
if grep -r "password.*=" app/ --include="*.py" --include="*.js" | grep -v "test_" | grep -v ".env" | grep -q "password"; then
    check_warn "Found potential hardcoded passwords in source code"
else
    check_pass "No obvious hardcoded passwords found"
fi

# 2. Check for debug mode
echo ""
echo "2. Checking debug mode configuration..."
if grep -q "DEBUG.*=.*True" app/backend/main.py; then
    check_fail "Debug mode is enabled"
else
    check_pass "Debug mode is disabled"
fi

# 3. Python dependency audit
echo ""
echo "3. Auditing Python dependencies..."
if command -v pip &> /dev/null; then
    if pip audit --quiet 2>/dev/null; then
        check_pass "No known vulnerabilities in Python packages"
    else
        check_fail "Found vulnerabilities in Python packages - run 'pip audit' for details"
    fi
else
    check_warn "pip not found - skipping Python audit"
fi

# 4. Node dependency audit
echo ""
echo "4. Auditing Node dependencies..."
if command -v npm &> /dev/null; then
    if cd app/frontend && npm audit --production 2>/dev/null | grep -q "0 vulnerabilities"; then
        check_pass "No known vulnerabilities in Node packages"
    else
        check_warn "Found vulnerabilities in Node packages - run 'npm audit' for details"
    fi
    cd - > /dev/null
else
    check_warn "npm not found - skipping Node audit"
fi

# 5. Check for SQL injection vulnerabilities (basic check)
echo ""
echo "5. Scanning for SQL injection vulnerabilities..."
if grep -r "execute.*\+" app/backend --include="*.py" 2>/dev/null | grep -v ".pyc" | grep -q .; then
    check_warn "Found potential SQL concatenation - review for SQL injection"
else
    check_pass "No obvious SQL injection patterns found"
fi

# 6. Check for hardcoded API keys
echo ""
echo "6. Scanning for hardcoded API keys..."
if grep -r "api_key.*=" app/ --include="*.py" --include="*.js" | grep -v "test_" | grep -v ".env" | grep -q "api_key"; then
    check_fail "Found potential hardcoded API keys"
else
    check_pass "No hardcoded API keys found"
fi

# 7. Check CORS configuration
echo ""
echo "7. Checking CORS configuration..."
if grep -q 'allow_origins=\["*"\]' app/backend/main.py; then
    check_fail "CORS allows all origins (*) - should be restricted"
else
    check_pass "CORS is restricted to specific origins"
fi

# 8. Check for XSS vulnerabilities (basic)
echo ""
echo "8. Scanning for potential XSS vulnerabilities..."
if grep -r "innerHTML" app/frontend/src --include="*.jsx" 2>/dev/null | grep -q .; then
    check_warn "Found innerHTML usage - ensure data is sanitized"
else
    check_pass "No direct innerHTML usage found"
fi

# 9. Check for sensitive data logging
echo ""
echo "9. Checking for sensitive data logging..."
if grep -r "print.*password\|console.log.*password" app/ --include="*.py" --include="*.js" 2>/dev/null | grep -q .; then
    check_fail "Found logging of sensitive data (passwords)"
else
    check_pass "No obvious sensitive data logging found"
fi

# 10. Check Docker files for non-root user
echo ""
echo "10. Checking Docker security..."
if grep -q "^USER" docker/Dockerfile.backend; then
    check_pass "Backend runs as non-root user"
else
    check_warn "Backend Dockerfile should specify non-root user"
fi

if grep -q "^USER" docker/Dockerfile.frontend; then
    check_pass "Frontend runs as non-root user"
else
    check_warn "Frontend Dockerfile should specify non-root user"
fi

# 11. Check for security headers in backend
echo ""
echo "11. Checking security headers configuration..."
if grep -q "X-Frame-Options" app/backend/main.py; then
    check_pass "Security headers middleware is implemented"
else
    check_fail "Security headers middleware not found"
fi

# 12. Check environment file exists
echo ""
echo "12. Checking configuration files..."
if [ -f ".env.security" ]; then
    check_pass "Security configuration file exists (.env.security)"
else
    check_warn "Security configuration file not found (.env.security)"
fi

# 13. Check for token expiration
echo ""
echo "13. Checking token expiration..."
if grep -q "ACCESS_TOKEN_EXPIRE_MINUTES\|token.*expir" app/backend --include="*.py" -r 2>/dev/null | grep -q .; then
    check_pass "Token expiration is configured"
else
    check_warn "Verify token expiration is properly configured"
fi

# 14. Check for rate limiting
echo ""
echo "14. Checking rate limiting..."
if grep -q "rate.*limit\|RateLimit" app/ --include="*.py" -r 2>/dev/null | grep -q .; then
    check_pass "Rate limiting logic appears to be implemented"
else
    check_warn "Verify rate limiting is properly configured"
fi

# 15. Check SSL/TLS configuration
echo ""
echo "15. Checking SSL/TLS configuration..."
if grep -q "ssl\|tls\|https" docker/Dockerfile.nginx 2>/dev/null; then
    check_pass "SSL/TLS configuration found"
else
    check_warn "Verify SSL/TLS is properly configured"
fi

# Summary
echo ""
echo "=============================="
echo "Security Audit Summary"
echo "=============================="
echo -e "${GREEN}Passed:${NC} $PASSED_CHECKS"
echo -e "${YELLOW}Warnings:${NC} $WARNING_CHECKS"
echo -e "${RED}Failed:${NC} $FAILED_CHECKS"
echo ""

if [ $FAILED_CHECKS -eq 0 ]; then
    echo -e "${GREEN}✓ No critical security issues found${NC}"
    exit 0
else
    echo -e "${RED}✗ Found $FAILED_CHECKS critical security issues${NC}"
    exit 1
fi
