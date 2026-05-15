@echo off
cd /d "%~dp0"
echo Installing backend dependencies...
pip install -r backend/requirements.txt
echo.
echo Starting FastAPI server on http://localhost:8000
python -m uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
