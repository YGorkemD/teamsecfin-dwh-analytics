"""
Global Security & Rate Limiting Middleware for FastAPI.
Enforces IP-based Rate Limiting, JWT authentication, and Role-Based Access Control (RBAC) globally.
"""

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from jose import jwt, JWTError
import logging
import time
from collections import defaultdict

from config import settings

logger = logging.getLogger(__name__)

# --- ENTERPRISE RATE LIMITER CONFIGURATION ---
# In a production environment, this is typically backed by Redis.
# For this architecture, we utilize a robust In-Memory "Sliding Window" algorithm.
RATE_LIMIT_MAX_REQUESTS = 20    # Maximum allowed HTTP requests...
RATE_LIMIT_WINDOW_SECONDS = 10  # ...within this sliding time window (in seconds).

# In-memory dictionary to track request timestamps per IP address
request_tracker = defaultdict(list)


class RBACMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        client_ip = request.client.host
        current_time = time.time()

        # --- 1. RATE LIMITING (DDoS & Abuse Protection) ---
        # Filter out timestamps that are older than our defined time window
        request_tracker[client_ip] = [
            timestamp for timestamp in request_tracker[client_ip] 
            if current_time - timestamp < RATE_LIMIT_WINDOW_SECONDS
        ]
        
        # Check if the client has exceeded the threshold
        if len(request_tracker[client_ip]) >= RATE_LIMIT_MAX_REQUESTS:
            logger.warning(f"RATE LIMIT THRESHOLD CROSSED: Temporarily blocking IP {client_ip}.")
            return JSONResponse(
                status_code=429, 
                content={"detail": "Too Many Requests. Rate limit exceeded. Please pause and try again shortly."}
            )
        
        # Log the current valid request timestamp
        request_tracker[client_ip].append(current_time)

        # --- 2. CORS PREFLIGHT EXCEPTION ---
        # Modern browsers send an HTTP 'OPTIONS' request to verify CORS policies.
        # These requests bypass JWT validation.
        if request.method == "OPTIONS":
            return await call_next(request)

        # --- 3. PUBLIC PATHS BYPASS ---
        public_paths = ["/", "/token", "/docs", "/openapi.json"]
        if request.url.path in public_paths:
            return await call_next(request)

        # --- 4. JWT AUTHENTICATION ENFORCEMENT ---
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            logger.warning(f"Unauthorized access attempt blocked to endpoint: {request.url.path}")
            return JSONResponse(status_code=401, content={"detail": "Missing or invalid authorization token"})

        token = auth_header.split(" ")[1]
        
        # --- 5. TOKEN DECODING & IDENTITY EXTRACTION ---
        try:
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
            username = payload.get("sub")
            role_name = payload.get("role")
            
            if not username or not role_name:
                logger.error("Token payload validation failed: Missing essential identity or role claims.")
                return JSONResponse(status_code=401, content={"detail": "Invalid or corrupted token structure"})
            
            # Inject identity into the FastAPI Request state memory
            request.state.user = {"username": username, "role": role_name}
            
        except JWTError as e:
            logger.warning(f"JWT Validation failed: {str(e)}")
            return JSONResponse(status_code=401, content={"detail": "Token has expired or is invalid"})

        # --- 6. ROUTE TO ENDPOINT ---
        response = await call_next(request)
        return response