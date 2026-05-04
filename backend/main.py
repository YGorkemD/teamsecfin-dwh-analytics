"""
Main Application Module for the Enterprise DWH & Analytics Platform API.
Acts as the API Gateway, managing routing, dynamic role-based data access (Row-Level Security),
and database bootstrapping utilizing SQLAlchemy ORM.

Security Note: 
Authentication and RBAC (Role-Based Access Control) have been decoupled from 
individual endpoints and are now handled globally via 'RBACMiddleware'.
"""

import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

# Relational and Analytical Model Imports
from backend.database import engine, get_db, SessionLocal, get_clickhouse_session
from backend.models import Base, User, Role
from backend.dwh_models import RetailCreditDWH, RetailPaymentPlanDWH
from backend.security import verify_password, get_password_hash, create_access_token
from backend.middleware import RBACMiddleware

# Configure application-level logging for observability
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Provision operational PostgreSQL schema automatically on startup
Base.metadata.create_all(bind=engine)

# Swagger UI configuration for JWT Bearer token authentication
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan context manager to handle startup/shutdown events.
    Responsible for executing database seeding operations (Roles & Users mapping)
    safely within the operational PostgreSQL database.
    """
    db = SessionLocal()
    try:
        # --- 1. PROVISION ESSENTIAL ROLES ---
        roles_data = [
            {"name": "Admin", "description": "Unrestricted system and data access."},
            {"name": "NormalUser", "description": "Row-level restricted access to tenant data."},
            {"name": "Guest", "description": "Read-only access strictly limited to aggregate metrics."}
        ]
        
        for r in roles_data:
            if not db.query(Role).filter(Role.name == r["name"]).first():
                db.add(Role(name=r["name"], description=r["description"]))
        
        db.commit() 

        # --- 2. PROVISION TEST ACCOUNTS WITH FOREIGN KEY BINDINGS ---
        users_to_create = [
            {"username": "admin", "password": "123", "role_name": "Admin"},
            {"username": "normal", "password": "123", "role_name": "NormalUser"},
            {"username": "guest", "password": "123", "role_name": "Guest"}
        ]
        
        for u in users_to_create:
            if not db.query(User).filter(User.username == u["username"]).first():
                user_role = db.query(Role).filter(Role.name == u["role_name"]).first()
                if user_role:
                    new_user = User(
                        username=u["username"],
                        hashed_password=get_password_hash(u["password"]),
                        role_id=user_role.id
                    )
                    db.add(new_user)
                    
        db.commit()
        logger.info("System Initialization: Core Roles and Service Accounts successfully provisioned.")
    except Exception as e:
        logger.error(f"Critical failure during database bootstrapping: {str(e)}")
        db.rollback()  # Rollback transactions to maintain database integrity
    finally:
        db.close()
        
    yield

# Initialize the FastAPI application with metadata
app = FastAPI(
    title="Data Warehouse & Analytics Platform API",
    description="Enterprise Multi-Tenant Analytics Gateway featuring ORM-driven DWH queries and Centralized RBAC.",
    version="1.0.0",
    lifespan=lifespan
)

# --- CORS INTEGRATION ---
# Essential for decoupling the frontend (React/Vite) from the backend services.
# Overcomes Cross-Origin Resource Sharing blocks enforced by modern browsers.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Note: In a strict production environment, this should be restricted to specific UI domains.
    allow_credentials=True,
    allow_methods=["*"],  # Permits all standard HTTP methods (GET, POST, OPTIONS, etc.)
    allow_headers=["*"],  # Permits all headers, including 'Authorization' for JWT Bearer Tokens
)

# --- MIDDLEWARE INTEGRATION ---
app.add_middleware(RBACMiddleware)

@app.get("/", tags=["General"])
def root():
    """Health check endpoint to verify API availability and uptime."""
    return {"message": "Welcome to Teamsecfin DWH Analytics API!"}

@app.post("/token", tags=["Authentication"])
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    """
    Authenticates identities against the PostgreSQL operational database 
    and provisions stateless JWT tokens.
    """
    user = db.query(User).filter(User.username == form_data.username).first()
    
    if not user or not verify_password(form_data.password, user.hashed_password):
        logger.warning(f"Authentication rejected for identity: {form_data.username}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, 
            detail="Invalid username or password"
        )
    
    access_token = create_access_token(data={"sub": user.username, "role": user.role.name})
    logger.info(f"Identity '{user.username}' authenticated. Token issued.")
    
    return {"access_token": access_token, "token_type": "bearer"}

@app.get("/analytics/data", tags=["Analytics"])
def get_analytics_data(
    request: Request, 
    table: str = "retail_credit", 
    ch_session: Session = Depends(get_clickhouse_session),
    _token: str = Depends(oauth2_scheme)
):
    """
    Executes analytical queries against the DWH utilizing SQLAlchemy ORM.
    Enforces Row-Level Security dynamically depending on the active identity's Role.
    """
    active_user = request.state.user
    role_name = active_user.get("role")
    username = active_user.get("username")
    
    # Input Sanitization against SQL Injection attempts
    if ";" in table or "DROP" in table.upper():
        logger.warning(f"Malicious table name injected by {username}: {table}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid table name format.")

    data_payload = []
    
    try:
        # --- 1. FULL ACCESS TIER (ADMIN) ---
        if role_name == "Admin":
            if "credit" in table:
                results = ch_session.query(RetailCreditDWH).limit(1000).all()
                data_payload = [
                    {
                        "customer_id": r.customer_id, 
                        "loan_account_number": r.loan_account_number, 
                        "kkdf_amount": r.kkdf_amount, 
                        "days_past_due": r.days_past_due
                    } for r in results
                ]
            else:
                results = ch_session.query(RetailPaymentPlanDWH).limit(1000).all()
                data_payload = [
                    {
                        "loan_account_number": r.loan_account_number, 
                        "installment_amount": r.installment_amount
                    } for r in results
                ]
                
        # --- 2. RESTRICTED ROW-LEVEL SECURITY TIER (NORMAL) ---
        elif role_name == "NormalUser":
            if "credit" in table:
                # Simulated mapping: In production, user_id maps directly to customer_id
                mock_tenant_id = "CUST_00373" 
                results = ch_session.query(RetailCreditDWH).filter(RetailCreditDWH.customer_id == mock_tenant_id).all()
                data_payload = [
                    {
                        "customer_id": r.customer_id, 
                        "loan_account_number": r.loan_account_number, 
                        "kkdf_amount": r.kkdf_amount
                    } for r in results
                ]
            else:
                mock_tenant_id = "LOAN_004442"
                results = ch_session.query(RetailPaymentPlanDWH).filter(RetailPaymentPlanDWH.loan_account_number == mock_tenant_id).all()
                data_payload = [
                    {
                        "loan_account_number": r.loan_account_number, 
                        "installment_amount": r.installment_amount
                    } for r in results
                ]
                
        # --- 3. METRIC AGGREGATION TIER (GUEST) ---
        elif role_name == "Guest":
            if "credit" in table:
                count = ch_session.query(RetailCreditDWH).count()
            else:
                count = ch_session.query(RetailPaymentPlanDWH).count()
            data_payload = [{"total_records": count, "metric_type": "aggregate_count"}]
            
        else:
            logger.critical(f"Data access violation. Unmapped role: {role_name}")
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid role authorization")

    except HTTPException:
        # Prevents intentional 400/403 exceptions from being masked by the general Exception block
        raise
    except Exception as e:
        logger.error(f"DWH Query Execution Failure for User '{username}': {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail="Data warehouse is currently not responding"
        )

    logger.info(f"Query successful. Extracted {len(data_payload)} records for {username} ({role_name}).")
    
    return {
        "user": username,
        "table": table,
        "record_count": len(data_payload),
        "data": data_payload,
        "active_role": role_name
    }