# 📊 Teamsecfin DWH & Analytics Platform

> **Enterprise-Grade Data Warehouse, ETL Pipeline, and Analytics Gateway** designed with a strict focus on Zero Data Loss, Row-Level Security (RLS), and High-Performance OLAP processing.
```text
========================================================================================
                   TEAMSECFIN DWH & ANALYTICS - ENTERPRISE ARCHITECTURE
========================================================================================

 [ CLIENT / DATA ANALYST ]
           │
           ▼  (JWT Bearer Token / HTTP REST)
┌──────────────────────────────────────────────────────────────────────────────────────┐
│ 1. PRESENTATION LAYER (React + Vite + Tailwind + Recharts)                           │
│                                                                                      │
│    [ Dashboard (Charts) ]    [ DLQ Monitor (Admin Only) ]    [ Raw Data Explorer ]   │
└────────────────────────────────────────┬─────────────────────────────────────────────┘
                                         │
                                         ▼  (Secure API Calls)
┌──────────────────────────────────────────────────────────────────────────────────────┐
│ 2. API GATEWAY & BUSINESS LOGIC (FastAPI)                                            │
│                                                                                      │
│  ► Rate Limiter & RBAC Middleware (DDoS Shield)   <──────> [ POSTGRESQL (Port 5432) ]│
│  ► Auth Service (Bcrypt + JWT Generation)                    ├─ Users Table          │
│  ► Row-Level Security (RLS) Engine                           └─ Roles Table          │
│  ► SQLAlchemy ORM Query Builder                                                      │
└────────────────────────────────────────┬─────────────────────────────────────────────┘
                                         │
                                         ▼  (Optimized OLAP Queries)
┌──────────────────────────────────────────────────────────────────────────────────────┐
│ 3. ANALYTICAL DATA WAREHOUSE (ClickHouse - Port 9000)                                │
│                                                                                      │
│  [ Core Financial Datasets ]     [ system_dlq ]        [ data_quality_reports ]      │
│  (Retail & Commercial Tables)    (Quarantine Zone)     (IQR Anomaly Audits)          │
└────────────────────────────────────────▲─────────────────────────────────────────────┘
                                         │  (Bulk Inserts & Quarantine Routing)
┌────────────────────────────────────────┴─────────────────────────────────────────────┐
│ 4. ENTERPRISE ETL PIPELINE & DATA QUALITY (Python + Pandas + Pydantic)               │
│                                                                                      │
│  ► Data Extraction (Raw Masked CSVs)                                                 │
│  ► Date Normalization & Scrubbing (Pandas)                                           │
│  ► Strict Schema Validation (Pydantic Contracts)  ──── (If Invalid) ───> To DLQ      │
│  ► IQR Statistical Profiling (Anomaly Detection)  ──── (Metrics) ──────> To Reports  │
└──────────────────────────────────────────────────────────────────────────────────────┘
```

## 📌 Executive Summary

This project is a full-stack, Dockerized Enterprise Analytics Platform. It strategically decouples operational identity management (OLTP) from high-speed analytical workloads (OLAP) to ensure maximum scalability. 

The system features a robust Python-based ETL pipeline that ingests raw financial datasets, strictly validates them using data contracts (Pydantic), and quarantines faulty records into a **Dead Letter Queue (DLQ)**. The analytical insights are securely served via a FastAPI gateway, consumed by a modern React/Vite dashboard, and protected by globally enforced Rate Limiting and Role-Based Access Control (RBAC).

---

## 🏗️ Core Architecture & Design Patterns

* **Separation of Concerns (Database Level):** * **PostgreSQL (OLTP):** Acts as the source of truth for authentication, user sessions, and RBAC roles.
  * **ClickHouse (OLAP):** Optimized with `MergeTree` engines for lightning-fast financial aggregations and time-series querying.
* **Shift-Left Data Quality:** Data anomalies are caught *before* they corrupt the warehouse. The `EnterpriseDataProfiler` utilizes the **Interquartile Range (IQR)** statistical method to flag outliers, persisting audit logs directly into the DWH.
* **Defense in Depth (Security):** * In-memory **Sliding Window Rate Limiter** to mitigate DDoS attacks.
  * Stateless **JWT Authentication** injected via FastAPI dependency overrides.
  * Pre-flight CORS exception handling for secure cross-origin UI interactions.

---

## ✨ Enterprise Features

### 🔐 1. Dynamic Row-Level Security (RLS)
The FastAPI layer dynamically filters ClickHouse payloads based on the active user's JWT claims:
* **Admin:** Unrestricted access to all data and DLQ Audit logs.
* **NormalUser:** Restricted strictly to their own tenant/customer ID (e.g., `CUST_00373`).
* **Guest:** Read-only access to high-level metric aggregations (Counts), completely blocking row-level visibility.

### 🛡️ 2. Zero-Loss ETL & Dead Letter Queue (DLQ)
Instead of silently dropping rows with missing values or invalid data types (e.g., negative loan amounts), the ClickHouseETL engine routes them to a dedicated `system_dlq` table. This guarantees **100% data traceability** and allows data engineers to investigate malformed records without halting the pipeline.

### 📈 3. React + Recharts Interactive Dashboard
A modern, decoupled SPA (Single Page Application) built with React and Vite. It parses JWT tokens client-side to enforce UI-level RBAC (hiding Admin-only DLQ tabs from Normal users) and provides dynamic, interactive charts and raw data explorers.

---

## 🛠️ Tech Stack

**Backend & Data Engineering:**
* **FastAPI:** High-performance async API Gateway.
* **Python (Pandas & Pydantic):** Data transformation, date normalization, and strict schema validation.
* **ClickHouse & ClickHouse-Driver:** Columnar DWH with native analytical performance.
* **PostgreSQL & SQLAlchemy:** Relational persistence and ORM modeling.
* **Passlib (Bcrypt) & JOSE:** Cryptography and JWT management.

**Frontend:**
* **React 18 & Vite:** Lightning-fast UI development environment.
* **Tailwind CSS:** Utility-first CSS framework for responsive design.
* **Recharts & Lucide-React:** Data visualization and modern iconography.

**DevOps & Infrastructure:**
* **Docker & Docker-Compose:** Multi-stage builds, isolated networks, and anonymous volume mapping for frictionless deployment.

---

## 🚀 Quick Start (Dockerized)

The entire infrastructure, including databases, ETL jobs, backend APIs, and the frontend dashboard, is containerized. 

### Prerequisites
* Docker Engine & Docker Compose installed.
* Ports `8000` (API), `5173` (UI), `5432` (Postgres), and `9000/8123` (ClickHouse) available.

# Enterprise Data Platform

## 🚀 Getting Started

To spin up the enterprise environment, run:

```bash
docker-compose up --build -d
```

---

## 🔗 Access the Platform

* **React Dashboard:** http://localhost:5173
* **FastAPI Swagger Docs:** http://localhost:8000/docs

---

## 🔑 Default Credentials (Seeded on Startup)

The system automatically bootstraps operational schemas and seeds the following test accounts:

| Role | Username | Password | Capabilities |
| :--- | :--- | :--- | :--- |
| **Admin** | `admin` | `123` | Full Access & DLQ Audits |
| **Normal User** | `normal` | `123` | Row-Level Restricted |
| **Guest** | `guest` | `123` | Aggregations Only |

---

## 🧪 Testing & Reliability

Engineered for CI/CD pipelines, the project boasts an **86%+ Test Coverage** across all business logic, ETL transformations, and security layers. Tests utilize zero-dependency mocking (`unittest.mock.patch`) to ensure database isolation.

**Coverage Report:**
```text
Name                    Stmts   Miss  Cover
-------------------------------------------
backend/database.py        20      0   100%
backend/dwh_models.py      24      2    92%
backend/main.py            91     24    74%
backend/middleware.py      44      3    93%
backend/models.py          20      0   100%
backend/security.py        14      1    93%
etl/data_analysis.py       61     10    84%
etl/etl_pipeline.py       166     21    87%
-------------------------------------------
TOTAL                     440     61    86%
================ 31 passed, 1 warning in 4.87s ================
```
To run the Enterprise Test Suite:

```bash
docker exec -it dwh_api pytest -v --cov=backend --cov=etl
```

> **Note:** The test suite includes Edge Case Coverage, ensuring the In-Memory Rate Limiter, DLQ fallbacks, and JWT middleware operate flawlessly under stress.

---

## 👨‍💻 Architect & Developer

**Yavuz Görkem Deniz** – AI Engineer & Data Analyst
**Contact info :**     - gorkeemdeniz@outlook.com

*Driven by a passion for scalable AI agents, agentic workflows, and robust data warehouse architectures. Designed this platform to demonstrate the seamless integration of Data Engineering, Backend Security, and Frontend UX.*
