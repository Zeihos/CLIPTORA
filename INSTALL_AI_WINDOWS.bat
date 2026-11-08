@echo off
setlocal EnableExtensions DisableDelayedExpansion
cd /d "%~dp0"
echo ============================================
echo    CLIPTORA - SPEECH AI
echo ============================================
call "%~dp0SELECT_PYTHON_WINDOWS.bat"
if errorlevel 1 goto no_python
"%CLIPTORA_PYTHON%" -c "import sys; print('[INFO] Using Python',sys.version.split()[0],sys.executable)"
if errorlevel 1 goto no_python
"%CLIPTORA_PYTHON%" -c "import faster_whisper; print('[OK] faster-whisper already installed')" >nul 2>&1
if not errorlevel 1 goto verify_ai
echo [INFO] Installing faster-whisper for Python 3.12...
"%CLIPTORA_PYTHON%" -m pip install --only-binary=:all: "faster-whisper==1.2.1"
if errorlevel 1 goto ai_failed
:verify_ai
"%CLIPTORA_PYTHON%" -c "import faster_whisper; print('[OK] faster-whisper is ready')"
if errorlevel 1 goto ai_failed
echo [INFO] Speech recognition models download on first use.
echo [INFO] Optional local dialogue model: https://ollama.com/download/windows
echo [INFO] Optional model command: ollama pull qwen3:8b
echo [INFO] You can now run START_WINDOWS.bat.
pause
exit /b 0
:no_python
echo [ERROR] Python 3.12 not found. Run SETUP_WINDOWS.bat.
pause
exit /b 1
:ai_failed
echo [ERROR] faster-whisper installation or verification failed for Python 3.12.
echo [HELP] Manual command:
echo "%CLIPTORA_PYTHON%" -m pip install --only-binary=:all: "faster-whisper==1.2.1"
pause
exit /b 1
