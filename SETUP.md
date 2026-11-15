# AegisOps AI - Setup & Installation Guide

## 💻 System Requirements
- **OS**: Windows 10/11, macOS, or Linux (Ubuntu 20.04+)
- **Python**: 3.10, 3.11, 3.12, or 3.13
- **Node.js**: v18.0.0+ and npm 9+
- **Hardware**: Standard x86_64 / ARM CPU (No GPU or CUDA required)

---

## 🛠️ Step-by-Step Installation

### Step 1: Clone Repository
```bash
cd "c:\Users\admin\AegisOps AI"
```

### Step 2: Setup Python Virtual Environment
```bash
# Create venv
python -m venv venv

# Activate venv
.\venv\Scripts\activate      # Windows PowerShell
# source venv/bin/activate   # Linux/macOS

# Install Backend Dependencies
pip install -r backend/requirements.txt
```

### Step 3: Setup Frontend
```bash
cd frontend
npm install
npm run build
cd ..
```

### Step 4: Run Multi-Process System
```bash
python scripts/start_all.py
```

### Step 5: Verify Setup
- Open [http://127.0.0.1:5173](http://127.0.0.1:5173) in your browser.
- Verify that all 4 microservice cards display `UP` and the health score shows `100%`.
