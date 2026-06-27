# GIS KPI Backend

FastAPI Backend for GIS KPI tracking and Telegram bot integration.

## Setup & Running

1. **Virtual Environment**:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```
2. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```
3. **Environment Configuration**:
   Create a `.env` file from the config template and customize your settings.
4. **Run Application**:
   ```bash
   uvicorn app.main:app --reload --port 8000
   ```
