"""
Enterprise ClickHouse Data Warehouse ORM Models.
Leverages clickhouse-sqlalchemy to provide a robust, type-safe query interface
for OLAP analytical workloads while maintaining MergeTree performance optimizations.
"""

from sqlalchemy import Column, String, Float, Integer
from sqlalchemy.orm import declarative_base
from clickhouse_sqlalchemy import engines

# Initialize declarative base for Data Warehouse models
DWHBase = declarative_base()

class RetailCreditDWH(DWHBase):
    """
    ORM representation of the 'retail_credit' table in the Data Warehouse.
    Stores core credit information and outstanding balances for retail customers.
    """
    __tablename__ = 'retail_credit'
    
    # Composite Primary Key to prevent SQLAlchemy deduplication trap.
    # A single customer can hold multiple distinct loan accounts.
    customer_id = Column(String, primary_key=True)
    loan_account_number = Column(String, primary_key=True)
    
    # Financial metrics
    kkdf_amount = Column(Float)
    days_past_due = Column(Integer)
    
    # Status indicators
    loan_status_code = Column(String)
    
    # Enforce ClickHouse native MergeTree engine for analytical query performance
    # Ordered by customer_id to optimize row-level security (RLS) filter queries
    __table_args__ = (
        engines.MergeTree(order_by=['customer_id']),
    )

    def __repr__(self) -> str:
        """Provides a human-readable string representation for debugging and logging."""
        return f"<RetailCreditDWH(customer_id='{self.customer_id}', loan_account='{self.loan_account_number}')>"

class RetailPaymentPlanDWH(DWHBase):
    """
    ORM representation of the 'retail_payment_plan' table in the Data Warehouse.
    Contains detailed installment breakdown for retail credit accounts.
    """
    __tablename__ = 'retail_payment_plan'
    
    # Composite Primary Key to prevent SQLAlchemy deduplication trap.
    # A single loan account consists of multiple distinct installments.
    loan_account_number = Column(String, primary_key=True)
    installment_number = Column(Integer, primary_key=True)
    
    # Payment components
    installment_amount = Column(Float)
    principal_component = Column(Float)
    interest_component = Column(Float)
    
    # Enforce ClickHouse native MergeTree engine
    # Ordered by loan_account_number to optimize JOINs and specific loan queries
    __table_args__ = (
        engines.MergeTree(order_by=['loan_account_number']),
    )

    def __repr__(self) -> str:
        """Provides a human-readable string representation for debugging and logging."""
        return f"<RetailPaymentPlanDWH(loan_account='{self.loan_account_number}', installment={self.installment_number})>"