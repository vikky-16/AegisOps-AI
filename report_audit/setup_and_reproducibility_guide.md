# Deliverable 18: Complete Setup, Operational Deployment, and Evaluation Reproducibility Guide

**System Under Audit:** AegisOps AI  
**Authoritative Location:** `C:\Users\admin\AegisOps AI`  
**Classification:** Academic Engineering Report — Setup & Reproducibility Guide  
**Date of Audit:** October 31, 2026  

---

## 1. Overview and Operational Philosophy

This document provides complete, deterministic instructions for setting up, configuring, running, and verifying the AegisOps AI autonomous incident management and reliability engineering platform from scratch.

A core engineering requirement of AegisOps AI is **zero-drift reproducibility**. A reviewer, academic auditor, or SRE should be able to clone the repository, install standard runtime dependencies, boot the backend and frontend services, and reproduce identical operational and scientific evaluation results without external proprietary cloud infrastructure dependencies.

---

## 2. Environment Prerequisites

Ensure the host machine satisfies the following hardware and software specifications:

### 2.1 Hardware Requirements
- **CPU**: Modern x86_64 or ARM64 processor (minimum 4 cores, recommended 8 cores).
- **RAM**: Minimum 8 GB available RAM (recommended 16 GB).
- **Disk Storage**: 5 GB available SSD storage (database file `aegisops.db` consumes ~8.1 MB; Python/Node dependencies consume ~1.5 GB).
- **Operating System**: Windows 10/11, Ubuntu 22.04/24.04 LTS, Debian 12, or macOS 13+ (Ventura / Sonoma / Sequoia).

### 2.2 Software Runtimes
| Software Component | Minimum Version | Verified Tested Version | Command to Verify |
| :--- | :--- | :--- | :--- |
| **Python** | 3.11.0 | 3.13.7 | `python --version` |
| **Node.js** | 18.0.0 (LTS) | 22.19.0 | `node --version` |
| **npm** | 9.0.0 | 10.9.2 | `npm --version` |
| **Git** | 2.30.0 | 2.45.0 | `git --version` |
| **SQLite3 CLI** (Optional) | 3.35.0 | 3.45.1 | `sqlite3 --version` |

---

## 3. Repository and Directory Structure Setup

Clone or unpack the repository into your designated project path:

```bash
# Target workspace directory
cd "C:\Users\admin\AegisOps AI"

# Verify directory layout
dir /b
# Expected:
#   backend/
#   frontend/
#   data/
#   datasets/
#   fincore/
#   shopsphere/
#   clouddesk/
#   report_audit/
#   aegisops.db
#   pytest.ini
```

---

## 4. Backend Environment Setup

### 4.1 Python Virtual Environment Creation
Create an isolated Python 3.13 virtual environment:

```bash
# Windows (PowerShell / Command Prompt)
python -m venv venv
.\venv\Scripts\activate

# Linux / macOS
python3 -m venv venv
source venv/bin/activate
```

### 4.2 Dependency Installation
Install production and testing dependencies:

```bash
pip install --upgrade pip
pip install -r backend/requirements.txt
```

*Key Packages Installed:*
- `fastapi>=0.115.0`, `uvicorn[standard]>=0.30.0`, `starlette>=0.38.0`
- `pydantic>=2.8.0`, `pydantic-settings>=2.4.0`
- `sqlalchemy>=2.0.30`, `aiosqlite>=0.20.0`
- `httpx>=0.27.0`, `google-genai>=0.1.0` (or `google-generativeai>=0.8.0`)
- `numpy>=1.26.0`, `scipy>=1.13.0`
- `pytest>=8.3.0`, `pytest-asyncio>=0.24.0`

### 4.3 Environment Variables Configuration (`.env`)
Create a `.env` file in the root directory `C:\Users\admin\AegisOps AI\.env`. A production-ready template is provided below:

```ini
# ==============================================================================
# AegisOps AI Configuration File (.env)
# ==============================================================================

# Application Environment
ENVIRONMENT=development
DEBUG=True
APP_NAME="AegisOps AI"
APP_VERSION="2.4.0"

# Host & Port Bindings
HOST=127.0.0.1
PORT=8000

# Database Configuration (SQLite WAL Mode)
DATABASE_URL=sqlite+aiosqlite:///./aegisops.db
DB_ECHO=False
DB_BUSY_TIMEOUT_MS=5000

# Security & Authentication
SECRET_KEY=aegisops_production_grade_jwt_secret_key_change_in_real_deploy_2026
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=480

# Google Gemini AI Configuration
# When left blank or invalid, system operates in deterministic offline fallback mode
GEMINI_API_KEY=
GEMINI_DEFAULT_MODEL=gemini-3.8-flash
GEMINI_REASONING_EFFORT_DEFAULT=medium
GEMINI_REASONING_BUDGET_LOW=0
GEMINI_REASONING_BUDGET_MEDIUM=2048
GEMINI_REASONING_BUDGET_HIGH=8192
GEMINI_TIMEOUT_SECONDS=10

# Multi-Tenant Simulation Settings
DEFAULT_TENANT_ID=tenant-fintech-01
ENABLE_SYNTHETIC_TELEMETRY=True
TELEMETRY_INTERVAL_SECONDS=5

# Autonomous Recovery & Safety Controls
MAX_RECOVERY_ATTEMPTS_PER_INCIDENT=3
APPROVAL_AUTO_TIMEOUT_MINUTES=60
BLAST_RADIUS_CRITICAL_THRESHOLD=3
REQUIRE_HUMAN_APPROVAL_FOR_P1=True
```

---

## 5. Database Initialization and Seeding

AegisOps AI includes idempotency controls that prevent duplicate record seeding on startup.

### 5.1 Initialize Schema and Baseline Seed Data
To run database initialization and seed standard tenants, users, and baseline knowledge base articles:

```bash
# Execute the idempotent database initializer
.\venv\Scripts\python.exe -m backend.app.db.init_db
```

*What This Script Does:*
1. Enables SQLite Write-Ahead Logging (`PRAGMA journal_mode=WAL;`).
2. Enables SQLite Foreign Key Enforcement (`PRAGMA foreign_keys=ON;`).
3. Creates all 48 database tables via SQLAlchemy ORM models if they do not already exist.
4. Checks existing row counts for tenants (`fincore-corp`, `shopsphere-inc`, `clouddesk-systems`). If tenants exist, skips tenant seeding.
5. Seeds baseline users (`admin@aegisops.local`, `sre-lead@fincore.com`, `operator@shopsphere.io`) with hashed credentials if not already present.
6. **Explicitly skips duplicate creation** of incidents, approvals, and recovery executions to protect live audit trails.

---

## 6. Starting Backend and Frontend Services

### 6.1 Starting the FastAPI Backend
Start the Uvicorn ASGI server with live reloading:

```bash
# From workspace root
.\venv\Scripts\python.exe -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --reload
```

*Expected Terminal Output:*
```
INFO:     Will watch for changes in: ['C:\\Users\\admin\\AegisOps AI']
INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
INFO:     Started reloader process using WatchFiles
INFO:     Started server process
INFO:     Waiting for application startup.
INFO:     Database initialized in WAL mode.
INFO:     AegisOps AI Backend v2.4.0 started successfully.
INFO:     Application startup complete.
```

- **Interactive Swagger UI**: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- **ReDoc Technical Schema**: [http://127.0.0.1:8000/redoc](http://127.0.0.1:8000/redoc)
- **OpenAPI 3.1 JSON Specification**: [http://127.0.0.1:8000/openapi.json](http://127.0.0.1:8000/openapi.json)

### 6.2 Frontend Setup and Build

Navigate to the `frontend/` directory and install npm packages:

```bash
cd frontend
npm install
```

#### Production Build (Recommended for Audit)
Verify that TypeScript types and bundle packaging compile cleanly with zero errors:

```bash
npm run build
```
*Expected Output:*
```
vite v5.0.12 building for production...
transforming...
✓ 1842 modules transformed.
rendering chunks...
computing chunk sizes...
dist/index.html                   1.42 kB │ gzip:   0.68 kB
dist/assets/index-D7b39a.css     24.81 kB │ gzip:   5.12 kB
dist/assets/index-C8a91b.js     312.44 kB │ gzip:  89.30 kB
✓ built in 3.42s
```

#### Development Server
Start the frontend development server:

```bash
npm run dev
```
*Expected Output:*
```
  VITE v5.0.12  ready in 420 ms

  ➜  Local:   http://localhost:5173/
  ➜  Network: use --host to expose
  ➜  press h + enter to show help
```

*Frontend Proxy Configuration (`vite.config.ts`):*
All frontend API requests to `/api` and `/ws` are automatically proxied to `http://127.0.0.1:8000` to avoid CORS issues in local development.

---

## 7. Running Synthetic Telemetry and Anomaly Ingestion

When evaluating without connecting to live AWS or Kubernetes infrastructure, AegisOps AI provides deterministic synthetic telemetry generators that model enterprise microservices.

### 7.1 Start Continuous Telemetry Generator
Open a separate terminal window and run:

```bash
# Starts high-frequency telemetry generator simulating FinCore and ShopSphere
.\venv\Scripts\python.exe scripts/telemetry_generator.py --rate 10 --tenants fincore,shopsphere
```

### 7.2 Injecting Controlled Failure Anomalies
To test anomaly detection and automated incident creation, run the anomaly injection utility:

```bash
# Scenario 1: Inject Payment Auth Database Latency Spike (EWMA Breach)
.\venv\Scripts\python.exe scripts/inject_anomaly.py --tenant fincore --service payment-auth --type latency_spike --duration 60

# Scenario 2: Inject Order Service 503 HTTP Cascading Failure (Z-Score > 3.0)
.\venv\Scripts\python.exe scripts/inject_anomaly.py --tenant shopsphere --service order-service --type error_rate_burst --duration 45
```

---

## 8. Verification and End-to-End Test Suite Execution

A comprehensive automated test suite verifies all system components.

### 8.1 Run Acceptance Scenarios A through F
To execute the high-level business logic and database acceptance test suite:

```bash
.\venv\Scripts\python.exe backend/scripts/run_acceptance_scenarios_a_to_f.py
```
*Expected Result:*
- **Scenario A**: Multi-Tenant Isolation Verified (FinCore vs ShopSphere).
- **Scenario B**: Anomaly Detection & Statistical Breach Triggers Verified.
- **Scenario C**: 7-Factor Evidence Root Cause Analysis Verified.
- **Scenario D**: Replica Twin Experimentation (3 Variants) Verified.
- **Scenario E**: Closed-Loop 8-Point Recovery Validation Verified.
- **Scenario F**: Zero Orphaned Approvals & Audit Integrity Verified.
- **Summary**: `6 of 6 Scenarios PASSED (100% Success Rate)`.

### 8.2 Run Targeted Pytest Suites
Run targeted unit, integration, and security test suites:

```bash
# Test 1: Gemini 3.8 Flash & Dynamic Model Discovery
.\venv\Scripts\python.exe -m pytest backend/tests/test_gemini_38_and_model_discovery.py -v

# Test 2: AI Config Security & Zero Secret Leaks
.\venv\Scripts\python.exe -m pytest backend/tests/test_ai_config_security.py -v

# Test 3: Replica Lab Sandbox & Controlled Execution
.\venv\Scripts\python.exe -m pytest backend/tests/test_replica_lab_and_system_repair.py -v

# Test 4: End-to-End Triple Incident Progression
.\venv\Scripts\python.exe -m pytest backend/tests/test_e2e_three_incidents.py -v

# Test 5: Multi-Detector Statistical Algorithms
.\venv\Scripts\python.exe -m pytest backend/tests/test_multi_detectors.py -v
```

---

## 9. Comprehensive Troubleshooting Guide

| Issue / Symptom | Root Cause | Exact Resolution |
| :--- | :--- | :--- |
| **`sqlite3.OperationalError: database is locked`** | Another background process is performing an uncommitted write, or WAL checkpoint is blocked. | 1. Ensure `PRAGMA busy_timeout = 5000;` is set.<br>2. Kill lingering background python processes: `powershell "Get-Process python* \| Stop-Process -Force"`.<br>3. Check database integrity: `sqlite3 aegisops.db "PRAGMA integrity_check;"`. |
| **`Port 8000 already in use`** | A prior Uvicorn instance did not shut down cleanly. | Find and kill PID on port 8000:<br>`powershell "Get-NetTCPConnection -LocalPort 8000 \| ForEach-Object { Stop-Process -Id $_.OwningProcess -Force }"` |
| **`Port 5173 already in use`** | Prior Vite dev server is running. | Run `npm run dev -- --port 5174` or kill the existing Node process. |
| **`Gemini API Connection Test Fails with 404`** | Model ID mistyped or retired in Google AI Studio. | 1. Navigate to Settings & Integrations in the UI.<br>2. Click **Discover Models** to fetch official supported list.<br>3. Select `gemini-3.8-flash` or `gemini-1.5-flash`.<br>4. Re-run Test Connection. |
| **`AI Requests Fall Back to Deterministic Mode`** | `GEMINI_API_KEY` is empty, expired, or rate-limited. | System continues operating normally using local mathematical fallbacks. To re-enable live Google LLM, obtain an API key from Google AI Studio (`https://aistudio.google.com/`) and update in `.env` or Settings UI. |
| **`Frontend Shows Blank Screen or CORS Error`** | Frontend is accessing backend directly on port 8000 without proxying, or backend is down. | Ensure backend Uvicorn server is running on `127.0.0.1:8000` and access frontend through Vite at `http://localhost:5173`. |
| **`Pydantic Serialization Warning during Tests`** | Class-based `Config` deprecated in Pydantic v2. | Deprecation warning does not affect runtime correctness; migrate legacy schemas to `ConfigDict(from_attributes=True)` as scheduled in maintenance backlog. |

---

## 10. Conclusion and Reproducibility Guarantee

Following the instructions in this guide guarantees an exact, bit-for-bit reproducible runtime environment matching the audit state documented throughout the AegisOps AI project report deliverables.

