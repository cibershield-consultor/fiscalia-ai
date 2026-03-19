"""
FiscalIA — Rate limiting with slowapi
Protects AI endpoints from abuse.
"""
from slowapi import Limiter
from slowapi.util import get_remote_address

# Use IP address as the key
limiter = Limiter(key_func=get_remote_address, default_limits=["200/minute"])

# Specific limits per endpoint type:
# - Chat AI: 30 req/min (expensive)
# - Auth: 10 req/min (brute force protection)
# - General API: 200 req/min
CHAT_LIMIT    = "30/minute"
AUTH_LIMIT    = "10/minute"
INVOICE_LIMIT = "60/minute"
EXCEL_LIMIT   = "10/minute"
