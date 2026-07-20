@echo off
title AI Scam Guard Startup Tool
echo ===================================================================
echo               AI SCAM GUARD PLATFORM - LAUNCHER
echo ===================================================================
echo.

:: 1. Force the zero-dependency pure-Python fallback database to prevent onnxruntime DLL crashes
set USE_FALLBACK_DB=true

:: Default to real Whisper transcription unless set otherwise
set USE_MOCK_WHISPER=false

:: Detect virtualenv Python vs System Python
set PYTHON_EXE=python
if exist backend\venv\Scripts\python.exe (
    echo [INFO] Detected virtualenv at backend\venv
    set PYTHON_EXE=backend\venv\Scripts\python.exe
)

:: 2. Check if Python is installed
%PYTHON_EXE% --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python is not installed or not added to your PATH environment variable.
    echo Please install Python 3.10+ and select Add python.exe to PATH during installation.
    pause
    exit /b
)

:: 3. Check if Node.js is installed
node -v >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Node.js is not installed.
    echo Please install Node.js, including npm, from https://nodejs.org/
    pause
    exit /b
)

:: 4. Seed advisory DB only if it doesn't exist yet (preserves call logs in db.sqlite3)
echo [1/4] Checking vector database...
if not exist backend\chroma_db (
    echo    ChromaDB not found — seeding official regulatory advisories...
    %PYTHON_EXE% backend/app/rag/index_docs.py
    if %errorlevel% neq 0 (
        echo [ERROR] Failed to seed advisories database. Check your Python environment dependencies.
        pause
        exit /b
    )
) else (
    echo    ChromaDB already exists, skipping re-seed. Delete backend\chroma_db to force refresh.
)

:: 5. Launch Backend
echo [3/4] Starting FastAPI backend server in a separate window...
if exist backend\venv\Scripts\python.exe (
    start cmd /k "title AI Scam Backend Server && cd backend && echo Starting backend... && venv\Scripts\python.exe run.py"
) else (
    start cmd /k "title AI Scam Backend Server && cd backend && echo Starting backend... && python run.py"
)

:: 6. Launch Frontend
echo [4/4] Starting React Vite frontend server in a separate window...
start cmd /k "title AI Scam Frontend Server && cd frontend && echo Starting frontend... && npm run dev"

echo.
echo ===================================================================
echo SUCCESS: The application components are launching!
echo.
echo - Backend API: http://127.0.0.1:8000
echo - Swagger Docs: http://127.0.0.1:8000/docs
echo - Frontend Dashboard: Check the browser window opening or the terminal
echo   (typically http://localhost:5173 or http://127.0.0.1:5173)
echo ===================================================================
echo.
echo Opening frontend in your default browser...
start http://localhost:5173
echo.
echo You can close this window now. Keep the other two server windows open.
pause
