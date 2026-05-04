"""
Enterprise Data Quality & Anomaly Detection Profiler.
Utilizes the IQR (Interquartile Range) statistical method to identify outliers.
Persists analytical insights directly into the ClickHouse Data Warehouse 
for long-term auditing and reporting (Zero-Loss Profiling).
"""

import logging
import pandas as pd
import numpy as np
from datetime import datetime
from pathlib import Path
from clickhouse_driver import Client
from typing import Dict, Any

from config import settings

# Configure module-level logging
logger = logging.getLogger(__name__)

class EnterpriseDataProfiler:
    """
    Scans datasets for statistical anomalies and persists the insights 
    into a dedicated Data Warehouse reporting table.
    """
    def __init__(self, host: str, port: int, user: str, password: str, database: str):
        self.client = Client(host=host, port=port, user=user, password=password, database=database)
        self._init_reporting_table()

    def _init_reporting_table(self) -> None:
        """
        Provisions the 'data_quality_reports' table in ClickHouse to persist analytical insights.
        """
        query = """
        CREATE TABLE IF NOT EXISTS data_quality_reports (
            analysis_timestamp DateTime,
            target_table String,
            column_name String,
            outlier_count Int32,
            anomaly_description String
        ) ENGINE = MergeTree() 
        ORDER BY analysis_timestamp
        """
        self.client.execute(query)
        logger.info("Data Quality Reporting table ('data_quality_reports') is ready.")

    def detect_outliers_iqr(self, df: pd.DataFrame, multiplier: float = 1.5) -> Dict[str, int]:
        """
        Applies the Interquartile Range (IQR) method to identify statistical outliers 
        in numerical columns. Returns a dictionary mapping column names to outlier counts.
        """
        outliers_report = {}
        # Select only numerical columns for statistical profiling
        numeric_cols = df.select_dtypes(include=[np.number]).columns

        for col in numeric_cols:
            # Drop NaNs to ensure accurate statistical boundaries
            clean_series = df[col].dropna()
            if clean_series.empty:
                continue

            Q1 = clean_series.quantile(0.25)
            Q3 = clean_series.quantile(0.75)
            IQR = Q3 - Q1

            lower_bound = Q1 - (multiplier * IQR)
            upper_bound = Q3 + (multiplier * IQR)

            # Count rows that fall outside the acceptable statistical boundaries
            outlier_count = clean_series[(clean_series < lower_bound) | (clean_series > upper_bound)].count()
            
            if outlier_count > 0:
                outliers_report[col] = int(outlier_count)

        return outliers_report

    def profile_dataset(self, table_name: str, file_path: str) -> None:
        """
        Reads a dataset, performs outlier detection, and logs the findings 
        both to the console (stdout) and to the ClickHouse DWH.
        """
        logger.info(f"Initiating advanced IQR profiling for: {table_name}")
        
        try:
            # Read sample or full dataset (using chunking for safety on massive files)
            df = pd.read_csv(file_path, sep=";", low_memory=False)
            
            outliers = self.detect_outliers_iqr(df)
            
            if not outliers:
                logger.info(f"No significant outliers detected for {table_name}.")
                return

            db_records = []
            current_time = datetime.now()

            # Prepare records for database insertion
            for col, count in outliers.items():
                description = f"Exceeds IQR boundaries (Multiplier: 1.5)"
                db_records.append({
                    "analysis_timestamp": current_time,
                    "target_table": table_name,
                    "column_name": col,
                    "outlier_count": count,
                    "anomaly_description": description
                })

            # Persist insights to the Data Warehouse
            if db_records:
                self.client.execute("INSERT INTO data_quality_reports VALUES", db_records)
                logger.warning(f"Persisted {len(outliers)} outlier metrics to DWH for '{table_name}'.")

        except Exception as e:
            logger.error(f"Profiling failed for {table_name}. Error: {e}")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    logger.info("Initiating Enterprise Batch Business Logic & IQR Profiling...")

    file_paths = {
        "commercial_credit": "data/commercial_credit_masked.csv",
        "commercial_payment_plan": "data/commercial_payment_plan_masked.csv",
        "retail_credit": "data/retail_credit_masked.csv",
        "retail_payment_plan": "data/retail_payment_plan_masked.csv"
    }

    profiler = EnterpriseDataProfiler(
        host=settings.CLICKHOUSE_HOST,
        port=settings.CLICKHOUSE_PORT,
        user=settings.CLICKHOUSE_USER,
        password=settings.CLICKHOUSE_PASSWORD,
        database=settings.CLICKHOUSE_DB
    )

    for table, path in file_paths.items():
        if Path(path).exists():
            profiler.profile_dataset(table, path)
        else:
            logger.warning(f"File not found for profiling: {path}")
            
    logger.info("Enterprise Data Quality Profiling and Persistence finished.")