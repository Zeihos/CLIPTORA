@echo off
setlocal EnableExtensions DisableDelayedExpansion
cd /d "%~dp0"
echo ============================================
echo    CLIPTORA - START
echo ============================================
call "%~dp0SELECT_PYTHON_WINDOWS.bat"
if errorlevel 1 goto no_python
echo [INFO] Using Python 3.12: "%CLIPTORA_PYTHON%"
echo [INFO] Opening local studio at http://127.0.0.1:8765
echo [INFO] Leave this window open while you use the studio.
"%CLIPTORA_PYTHON%" server.py
set "RESULT=%errorlevel%"
if not "%RESULT%"=="0" echo [ERROR] Studio stopped with code %RESULT%.
echo [INFO] To exit, close this window.
pause
exit /b %RESULT%
:no_python
echo [ERROR] Python 3.12 not found. Run SETUP_WINDOWS.bat.
pause
exit /b 1
