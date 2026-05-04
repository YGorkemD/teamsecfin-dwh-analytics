"""
Enterprise ETL pipeline module for ClickHouse.
Implements Object-Relational Mapping (ORM) style insertion with strict schema validation.
Features a Dead Letter Queue (DLQ) mechanism to capture and store validation failures,
preventing silent data loss and enabling data quality auditing.
"""

import time
import logging
import json
from datetime import datetime
import pandas as pd
import numpy as np
from pathlib import Path
from pydantic import BaseModel, Field, field_validator
from clickhouse_driver import Client
from typing import List, Dict, Any, Optional

from config import settings

# Configure module-level logging for pipeline observability
logger = logging.getLogger(__name__)

# =====================================================================
# 1. DWH ORM MODELS (DATA CONTRACTS)
# =====================================================================

class RetailCreditModel(BaseModel):
    """ORM Model defining the schema and validation for Retail Credit."""
    customer_id: str
    customer_type: str = "Unknown"
    loan_account_number: str
    loan_status_code: str = "UNKNOWN"
    days_past_due: int = 0
    final_maturity_date: Optional[str] = None
    total_installment_count: int = 0
    outstanding_installment_count: int = 0
    paid_installment_count: int = 0
    first_payment_date: Optional[str] = None
    
    kkdf_amount: float = Field(default=0.0, ge=0.0) 
    nominal_interest_rate: float = Field(default=0.0, ge=0.0)

    @field_validator('days_past_due', 'total_installment_count', 'outstanding_installment_count', 'paid_installment_count', mode='before')
    def parse_int(cls, v):
        try:
            return int(float(v)) if v else 0
        except (ValueError, TypeError):
            return 0

class CommercialCreditModel(BaseModel):
    """ORM Model defining the schema for Commercial Credit."""
    loan_account_number: str
    customer_type: str = "Unknown"
    customer_id: str
    loan_product_type: str = "Unknown"
    loan_status_code: str = "UNKNOWN"
    loan_status_flag: str = "UNKNOWN"
    days_past_due: int = 0
    final_maturity_date: Optional[str] = None
    total_installment_count: int = 0
    outstanding_installment_count: int = 0
    paid_installment_count: int = 0
    first_payment_date: Optional[str] = None
    original_loan_amount: float = Field(default=0.0, ge=0.0)

    @field_validator('days_past_due', 'total_installment_count', 'outstanding_installment_count', 'paid_installment_count', mode='before')
    def parse_int(cls, v):
        try:
            return int(float(v)) if v else 0
        except (ValueError, TypeError):
            return 0

class RetailPaymentPlanModel(BaseModel):
    """ORM Model defining the schema for Retail Payment Plans."""
    loan_account_number: str
    installment_number: int = 0
    actual_payment_date: Optional[str] = None
    scheduled_payment_date: Optional[str] = None
    installment_amount: float = Field(default=0.0, ge=0.0)
    principal_component: float = Field(default=0.0, ge=0.0)
    interest_component: float = Field(default=0.0, ge=0.0)
    kkdf_component: float = Field(default=0.0, ge=0.0)
    bsmv_component: float = Field(default=0.0, ge=0.0)
    installment_status: str = "UNKNOWN"
    remaining_principal: float = Field(default=0.0, ge=0.0)
    remaining_interest: float = Field(default=0.0, ge=0.0)

    @field_validator('installment_number', mode='before')
    def parse_int(cls, v):
        try:
            return int(float(v)) if v else 0
        except (ValueError, TypeError):
            return 0

class CommercialPaymentPlanModel(BaseModel):
    """ORM Model defining the schema for Commercial Payment Plans."""
    loan_account_number: str
    installment_number: int = 0
    actual_payment_date: Optional[str] = None
    scheduled_payment_date: Optional[str] = None
    installment_amount: float = Field(default=0.0, ge=0.0)
    principal_component: float = Field(default=0.0, ge=0.0)
    interest_component: float = Field(default=0.0, ge=0.0)
    kkdf_component: float = Field(default=0.0, ge=0.0)
    bsmv_component: float = Field(default=0.0, ge=0.0)
    installment_status: str = "UNKNOWN"

    @field_validator('installment_number', mode='before')
    def parse_int(cls, v):
        try:
            return int(float(v)) if v else 0
        except (ValueError, TypeError):
            return 0

# =====================================================================
# 2. ENTERPRISE ETL PIPELINE ENGINE
# =====================================================================

class ClickHouseETL:
    """
    Orchestrator for extracting data, enforcing schema validation, 
    processing bulk inserts, and routing invalid records to a Dead Letter Queue.
    """
    def __init__(self, host: str, port: int, user: str, password: str, database: str):
        self.client = Client(host=host, port=port, user=user, password=password, database=database)
        
        self.model_registry = {
            "retail_credit": RetailCreditModel,
            "commercial_credit": CommercialCreditModel,
            "retail_payment_plan": RetailPaymentPlanModel,
            "commercial_payment_plan": CommercialPaymentPlanModel
        }
        
        # Provision the DLQ table upon initialization
        self._init_dlq_table()

    def _init_dlq_table(self) -> None:
        """
        Creates a system_dlq (Dead Letter Queue) table to store records 
        that failed Pydantic validation, ensuring zero silent data loss.
        """
        query = """
        CREATE TABLE IF NOT EXISTS system_dlq (
            timestamp DateTime,
            target_table String,
            raw_payload String,
            error_message String
        ) ENGINE = MergeTree() 
        ORDER BY timestamp
        """
        self.client.execute(query)
        logger.info("System DLQ (Dead Letter Queue) table is ready.")

    def _map_pydantic_to_clickhouse(self, model_class: BaseModel) -> str:
        """Translates Pydantic type annotations into ClickHouse schema definitions."""
        columns_def = []
        for field_name, field_info in model_class.model_fields.items():
            field_type = field_info.annotation
            if field_type == int:
                ch_type = "Int64"
            elif field_type == float:
                ch_type = "Float64"
            else:
                ch_type = "Nullable(String)" 
            columns_def.append(f"{field_name} {ch_type}")
        return ", ".join(columns_def)

    def _create_table(self, table_name: str, model_class: BaseModel) -> None:
        """Provisions a performant ClickHouse table using the MergeTree engine."""
        schema_def = self._map_pydantic_to_clickhouse(model_class)
        self.client.execute(f"DROP TABLE IF EXISTS {table_name}")
        
        first_col = list(model_class.model_fields.keys())[0]
        create_query = (
            f"CREATE TABLE {table_name} ({schema_def}) "
            f"ENGINE = MergeTree() "
            f"ORDER BY {first_col} "
            f"SETTINGS allow_nullable_key = 1"
        )
        self.client.execute(create_query)

    def transform(self, df: pd.DataFrame) -> pd.DataFrame:
        """Normalizes dates and scrubs unwanted columns prior to validation."""
        date_cols = ['actual_payment_date', 'scheduled_payment_date', 
                     'final_maturity_date', 'first_payment_date', 'loan_start_date']
        
        for col in date_cols:
            if col in df.columns:
                format_str = '%Y%m%d' if 'payment_date' in col or 'maturity_date' in col else None
                df[col] = pd.to_datetime(df[col], format=format_str, errors='coerce').dt.strftime('%Y-%m-%d %H:%M:%S')

        if 'loan_closing_date' in df.columns:
            df.drop('loan_closing_date', axis=1, inplace=True)
        return df

    def _bulk_insert(self, data_dicts: List[Dict[str, Any]], table_name: str) -> None:
        """Executes a high-performance BULK INSERT operation."""
        if data_dicts:
            self.client.execute(f"INSERT INTO {table_name} VALUES", data_dicts)

    def process_file(self, table_name: str, file_path: str, chunk_size: int = 50000) -> None:
        """
        Reads CSV chunks, validates against schemas, routes valid records to the 
        target table, and routes invalid records to the DLQ.
        """
        start_time = time.time()
        logger.info(f"Starting pipeline for {table_name}...")
        
        model_class = self.model_registry.get(table_name)
        if not model_class:
            return

        self._create_table(table_name, model_class)

        try:
            chunk_iterator = pd.read_csv(file_path, sep=";", chunksize=chunk_size, low_memory=False)
            total_valid_rows = 0
            total_dlq_rows = 0
            
            for i, chunk in enumerate(chunk_iterator):
                cleaned_chunk = self.transform(chunk)
                records = cleaned_chunk.replace({np.nan: None}).to_dict('records')
                
                validated_data = []
                dlq_data = []
                
                for record in records:
                    try:
                        # Attempt strict schema validation
                        obj = model_class(**record)
                        validated_data.append(obj.model_dump()) 
                    except Exception as e:
                        # Route failed records to DLQ instead of silently dropping them
                        error_msg = str(e).replace('\n', ' | ')
                        dlq_data.append({
                            "timestamp": datetime.now(),
                            "target_table": table_name,
                            "raw_payload": str(record)[:1000],  
                            "error_message": error_msg[:500]    
                        })
                
                # Insert valid records to target table
                self._bulk_insert(validated_data, table_name)
                total_valid_rows += len(validated_data)
                
                # Insert failed records to Dead Letter Queue (DLQ)
                if dlq_data:
                    self._bulk_insert(dlq_data, "system_dlq")
                    total_dlq_rows += len(dlq_data)
                
                logger.info(f"[{table_name}] Chunk {i+1} | Valid: {total_valid_rows:,} | DLQ (Failed): {total_dlq_rows:,}")

            elapsed = time.time() - start_time
            logger.info(f"Pipeline completed for {table_name}. Valid Insertions: {total_valid_rows:,} | Quarantined to DLQ: {total_dlq_rows:,} | Time: {elapsed:.2f}s")
            
        except Exception as e:
            logger.error(f"Pipeline failed for {table_name}. Reason: {str(e)}")
            raise

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

    file_paths = {
        "commercial_credit": "data/commercial_credit_masked.csv",
        "commercial_payment_plan": "data/commercial_payment_plan_masked.csv",
        "retail_credit": "data/retail_credit_masked.csv",
        "retail_payment_plan": "data/retail_payment_plan_masked.csv"
    }

    etl_job = ClickHouseETL(
        host=settings.CLICKHOUSE_HOST,
        port=settings.CLICKHOUSE_PORT,
        user=settings.CLICKHOUSE_USER,
        password=settings.CLICKHOUSE_PASSWORD,
        database=settings.CLICKHOUSE_DB
    )

    for table, path in file_paths.items():
        if Path(path).exists():
            etl_job.process_file(table, path)