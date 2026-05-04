"""
Enterprise API Test Suite.
Validates Authentication, Role-Based Access Control (RBAC), Row-Level Security (RLS),
and graceful error handling utilizing FastAPI dependency overrides for SQLAlchemy ORM mocking.
"""

import pytest
from typing import Dict, Generator
from fastapi.testclient import TestClient
from unittest.mock import MagicMock
from fastapi import HTTPException

from backend.main import app, get_clickhouse_session, get_analytics_data
from backend.database import get_db

# Initialize the test client to interact with the FastAPI application
client = TestClient(app)

# =====================================================================
# FIXTURES & HELPERS
# =====================================================================

@pytest.fixture(autouse=True)
def reset_rate_limiter() -> Generator:
    """
    SENIOR FIXTURE: Automatically runs before and after EVERY test.
    Guarantees that the In-Memory Rate Limiter state is completely wiped,
    preventing "Test Pollution" (where one test's 20 requests block the next test).
    """
    from backend.middleware import request_tracker
    request_tracker.clear() # Setup
    yield                   # Test runs here
    request_tracker.clear() # Teardown (Even if the test fails)


def get_auth_token(username: str, password: str = "123") -> str:
    """
    Helper function to authenticate a user and retrieve a JWT access token.
    """
    response = client.post("/token", data={"username": username, "password": password})
    return response.json().get("access_token", "")

def get_auth_headers(token: str) -> Dict[str, str]:
    """
    Helper function to construct authorization headers using a JWT token.
    """
    return {"Authorization": f"Bearer {token}"}

# =====================================================================
# 1. GENERAL & SYSTEM TESTS
# =====================================================================

def test_root_endpoint_status():
    """
    Validates that the root endpoint is reachable and returns the correct welcome message.
    """
    response = client.get("/")
    assert response.status_code == 200
    assert "message" in response.json()
    assert response.json()["message"] == "Welcome to Teamsecfin DWH Analytics API!"

# =====================================================================
# 2. AUTHENTICATION TESTS
# =====================================================================

def test_login_success():
    """
    Validates successful authentication and JWT access token issuance.
    """
    response = client.post("/token", data={"username": "admin", "password": "123"})
    assert response.status_code == 200
    assert "access_token" in response.json()
    assert response.json()["token_type"] == "bearer"

def test_login_failure_wrong_password():
    """
    Validates that unauthorized access is blocked when an incorrect password is used.
    """
    response = client.post("/token", data={"username": "admin", "password": "wrong_password"})
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid username or password"

def test_login_failure_invalid_user():
    """
    Validates the behavior of the token endpoint when a non-existent user attempts to authenticate.
    """
    response = client.post("/token", data={"username": "non_existent_user", "password": "123"})
    assert response.status_code == 401

# =====================================================================
# 3. SECURITY & MIDDLEWARE TESTS
# =====================================================================

def test_protected_route_missing_token():
    """
    Validates that the RBACMiddleware correctly blocks requests missing the Authorization header.
    """
    response = client.get("/analytics/data?table=retail_credit")
    assert response.status_code == 401
    # SENIOR FIX: Aligned with the updated middleware error message
    assert response.json()["detail"] == "Missing or invalid authorization token"

def test_protected_route_invalid_token():
    """
    Validates that the RBACMiddleware correctly blocks requests with an invalid/malformed token.
    """
    headers = get_auth_headers("invalid.jwt.token.string")
    response = client.get("/analytics/data?table=retail_credit", headers=headers)
    assert response.status_code == 401

# =====================================================================
# 4. BUSINESS LOGIC & RBAC TESTS
# =====================================================================

def test_admin_data_access_limit():
    """
    Validates that an Admin user can successfully retrieve records with no data-level restrictions.
    """
    token = get_auth_token("admin")
    headers = get_auth_headers(token)
    response = client.get("/analytics/data?table=retail_credit", headers=headers)
    
    assert response.status_code == 200
    data = response.json()
    assert data["user"] == "admin"
    assert data["active_role"] == "Admin"
    assert isinstance(data["data"], list)
    assert len(data["data"]) <= 1000

def test_normal_user_row_level_security():
    """
    Validates that a NormalUser's access is restricted to their specific tenant rows (RLS).
    """
    token = get_auth_token("normal")
    headers = get_auth_headers(token)
    response = client.get("/analytics/data?table=retail_credit", headers=headers)
    
    assert response.status_code == 200
    data = response.json()
    assert data["user"] == "normal"
    assert data["active_role"] == "NormalUser"
    
    if len(data["data"]) > 0:
        for row in data["data"]:
            assert row.get("customer_id") == "CUST_00373"

def test_guest_user_aggregation_only():
    """
    Validates that a Guest user is restricted to receiving aggregated statistics.
    """
    token = get_auth_token("guest")
    headers = get_auth_headers(token)
    response = client.get("/analytics/data?table=retail_credit", headers=headers)
    
    assert response.status_code == 200
    data = response.json()
    assert data["user"] == "guest"
    assert data["active_role"] == "Guest"
    assert len(data["data"]) == 1
    assert "total_records" in data["data"][0]

def test_normal_user_loan_table_security():
    """
    Validates that a NormalUser's Row-Level Security (RLS) works for non-credit tables.
    """
    token = get_auth_token("normal")
    headers = get_auth_headers(token)
    response = client.get("/analytics/data?table=retail_payment_plan", headers=headers)
    
    assert response.status_code == 200
    data = response.json()
    assert data["user"] == "normal"
    
    if len(data["data"]) > 0:
        for row in data["data"]:
            assert row.get("loan_account_number") == "LOAN_004442"

def test_analytics_invalid_role():
    """
    Validates that the API correctly raises a 403 Forbidden exception 
    when an unrecognized role is passed through the request state.
    """
    # Setup a mock request with an unsupported role name
    mock_request = MagicMock()
    mock_request.state.user = {"username": "admin", "role": "UnsupportedRole"}
    mock_session = MagicMock()

    with pytest.raises(HTTPException) as exc_info:
        get_analytics_data(request=mock_request, table="retail_credit", ch_session=mock_session, _token="dummy")

    assert exc_info.value.status_code == 403
    assert exc_info.value.detail == "Invalid role authorization"

# =====================================================================
# 5. EDGE CASES & LIFECYCLE TESTS (MOCKING ORM SESSIONS)
# =====================================================================

def test_analytics_dwh_failure():
    """
    Validates the 500 Internal Server Error handling when the ClickHouse
    ORM connection crashes. Utilizes FastAPI's dependency overrides safely.
    """
    token = get_auth_token("admin")
    headers = get_auth_headers(token)

    # Simulate an ORM database crash
    mock_session = MagicMock()
    mock_session.query.side_effect = Exception("Simulated ORM Crash")
    
    # SENIOR FIX: Safe Try-Finally block ensures dependency override is cleared 
    # even if the test assertion fails.
    try:
        app.dependency_overrides[get_clickhouse_session] = lambda: mock_session
        response = client.get("/analytics/data?table=retail_credit", headers=headers)
        
        assert response.status_code == 500
        assert response.json()["detail"] == "Data warehouse is currently not responding"
    finally:
        app.dependency_overrides.clear()

def test_analytics_empty_data_handling():
    """
    Covers the scenario where ClickHouse returns an empty dataset.
    Ensures main.py processes and returns empty lists gracefully without throwing errors.
    """
    token = get_auth_token("admin")
    headers = get_auth_headers(token)
    
    # Mock the SQLAlchemy query chain: session.query().limit().all() -> []
    mock_session = MagicMock()
    mock_session.query.return_value.limit.return_value.all.return_value = []
    
    try:
        app.dependency_overrides[get_clickhouse_session] = lambda: mock_session
        response = client.get("/analytics/data?table=retail_credit", headers=headers)
        
        assert response.status_code == 200
        assert response.json()["data"] == []
    finally:
        app.dependency_overrides.clear()

def test_get_db_dependency_lifecycle():
    """
    Covers the database session generator's lifecycle (yield and finally block)
    to ensure PostgreSQL connections are safely closed.
    """
    db_generator = get_db()
    session = next(db_generator)
    assert session is not None
    
    # Trigger the 'finally' block to safely close the session
    try:
        next(db_generator)
    except StopIteration:
        pass

def test_analytics_sql_injection_prevention():
    """
    Covers the input validation block that rejects malicious 
    or unmapped table names to prevent SQL Injection attacks.
    """
    token = get_auth_token("admin")
    headers = get_auth_headers(token)
    
    # Send a malicious table name containing a semicolon
    response = client.get("/analytics/data?table=retail_credit; DROP TABLE users;", headers=headers)
    
    # The system should instantly reject this with a 400 Bad Request
    assert response.status_code == 400
    assert response.json()["detail"] == "Invalid table name format."

# =====================================================================
# 6. SECURITY & RATE LIMITING TESTS (DDOS PROTECTION)
# =====================================================================

def test_rate_limiting_defense():
    """
    Validates that the In-Memory Rate Limiter blocks excessive requests 
    (DDoS protection) by simulating a rapid burst of API calls.
    Note: Teardown/Setup is automatically handled by the 'reset_rate_limiter' fixture.
    """
    # 1. Send 20 requests quickly (filling the allowed limit window)
    for _ in range(20):
        response = client.get("/")
        assert response.status_code == 200

    # 2. Send the 21st request (The threshold breaker)
    blocked_response = client.get("/")
    
    # 3. Verify the system shields the API with a 429 Too Many Requests response
    assert blocked_response.status_code == 429
    assert "Too Many Requests" in blocked_response.json()["detail"]