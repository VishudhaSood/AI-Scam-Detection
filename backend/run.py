import ctypes
import os
import platform

# Preload system C++ runtime DLLs on Windows to prevent Anaconda DLL Hell crash
if platform.system() == "Windows":
    try:
        windir = os.environ.get("SystemRoot", os.environ.get("windir", "C:\\Windows"))
        system32 = os.path.join(windir, "System32")
        for dll in ["msvcp140.dll", "vcruntime140.dll", "vcruntime140_1.dll"]:
            dll_path = os.path.join(system32, dll)
            if os.path.exists(dll_path):
                ctypes.CDLL(dll_path)
    except Exception:
        pass

import uvicorn
import sys

# Ensure the backend directory is in the Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Default to using real Whisper transcription unless explicitly requested
os.environ.setdefault("USE_MOCK_WHISPER", "false")

if __name__ == "__main__":
    print("Starting AI Scam Detection Backend...")
    uvicorn.run(
        "app.main:app",
        host="127.0.0.1",
        port=8000,
        reload=True
    )
