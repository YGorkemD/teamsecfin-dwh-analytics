# ==============================================================================
# BACKEND - ENTERPRISE MULTI-STAGE DOCKERFILE
# Stage 1: Builder (Compiles dependencies and QA tools)
# ==============================================================================
FROM python:3.11-slim AS builder

WORKDIR /build

# Install system dependencies required for building Python packages (e.g., psycopg2)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install them into a specific prefix directory
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# Install QA tools for Test Coverage 
RUN pip install --no-cache-dir --prefix=/install pytest pytest-cov httpx

# ==============================================================================
# Stage 2: Production Runner (Lean, Secure, and Ready for Deployment)
# ==============================================================================
FROM python:3.11-slim AS runner

WORKDIR /app

# Copy ONLY the compiled libraries from the builder stage (Huge size reduction)
COPY --from=builder /install /usr/local

# Install only runtime libraries (like PostgreSQL client) to keep image small
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

# Copy the actual application code and configuration files
COPY . .
COPY config.py .env ./

# Security: Run container as a non-root user to prevent privilege escalation
RUN useradd -m appuser && chown -R appuser /app
USER appuser

# Define the entrypoint command for FastAPI
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
