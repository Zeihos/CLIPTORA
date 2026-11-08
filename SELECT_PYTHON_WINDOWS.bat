@echo off
rem Shared Python interpreter selector (called by all Windows entrypoints).
rem Deliberately use Python 3.12. A generic "py -3" can select Python 3.15.
set "CLIPTORA_PYTHON="
if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" (
    "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" -c "import sys; sys.exit(0 if sys.version_info[:2] == (3, 12) else 1)" >nul 2>&1
    if not errorlevel 1 set "CLIPTORA_PYTHON=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
)
if defined CLIPTORA_PYTHON exit /b 0
where py >nul 2>&1
if errorlevel 1 goto no_312
for /f "delims=" %%P in ('py -3.12 -c "import sys; print(sys.executable)" 2^>nul') do set "CLIPTORA_PYTHON=%%P"
if not defined CLIPTORA_PYTHON goto no_312
"%CLIPTORA_PYTHON%" -c "import sys; sys.exit(0 if sys.version_info[:2] == (3, 12) else 1)" >nul 2>&1
if not errorlevel 1 exit /b 0
:no_312
set "CLIPTORA_PYTHON="
exit /b 1
