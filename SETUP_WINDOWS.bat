@echo off
setlocal EnableExtensions DisableDelayedExpansion
cd /d "%~dp0"
echo ============================================
echo    CLIPTORA - SETUP
echo ============================================
echo [INFO] Selecting Python 3.12...
call "%~dp0SELECT_PYTHON_WINDOWS.bat"
if errorlevel 1 goto python_missing
"%CLIPTORA_PYTHON%" -c "import sys; print('[OK] Python', sys.version.split()[0], 'at', sys.executable)"
if errorlevel 1 goto python_missing
echo [INFO] Checking FFmpeg and FFprobe...
if exist "tools\ffmpeg.exe" if exist "tools\ffprobe.exe" goto ffmpeg_ok
where ffmpeg >nul 2>&1
if errorlevel 1 goto ffmpeg_missing
where ffprobe >nul 2>&1
if errorlevel 1 goto ffmpeg_missing
:ffmpeg_ok
echo [OK] FFmpeg and FFprobe are available.
goto ready
:ffmpeg_missing
echo [WARN] FFmpeg or FFprobe was not found.
where winget >nul 2>&1
if errorlevel 1 goto manual_ffmpeg
echo [INFO] Installing FFmpeg with winget...
winget install --id Gyan.FFmpeg --exact --source winget --accept-source-agreements --accept-package-agreements
if errorlevel 1 goto manual_ffmpeg
echo [INFO] Reopen your terminal after winget setup, then run this file again.
goto ready
:manual_ffmpeg
echo [HELP] Download FFmpeg and place ffmpeg.exe and ffprobe.exe in the tools folder.
echo [HELP] Or install with: winget install Gyan.FFmpeg
:ready
echo.
echo [INFO] Optional speech AI installer: INSTALL_AI_WINDOWS.bat
echo [INFO] Start the program with START_WINDOWS.bat
echo [INFO] Original video files are not changed.
pause
exit /b 0
:python_missing
echo [ERROR] Python 3.12 was not found. Python 3.15 is not used.
echo [HELP] Please install Python 3.12 from https://www.python.org/downloads/
echo [HELP] If Python 3.12 is installed, check:
echo        %%LOCALAPPDATA%%\Programs\Python\Python312\python.exe
echo        or run: py -3.12 --version
pause
exit /b 1
