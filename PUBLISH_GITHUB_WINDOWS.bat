@echo off
setlocal EnableExtensions DisableDelayedExpansion
cd /d "%~dp0"
echo ============================================
echo    CLIPTORA - GITHUB PUBLISH
echo ============================================
where git >nul 2>&1
if errorlevel 1 goto no_git
where gh >nul 2>&1
if errorlevel 1 goto no_gh
gh auth status >nul 2>&1
if errorlevel 1 goto no_auth
if exist ".git" goto existing_local
 git init -b main
if errorlevel 1 goto failed
:existing_local
git add .
if errorlevel 1 goto failed
git diff --cached --quiet
if not errorlevel 1 goto publish
 git commit -m "Initial CLIPTORA public alpha 0.1.3"
if errorlevel 1 goto no_identity
:publish
gh repo view Zeihos/CLIPTORA >nul 2>&1
if not errorlevel 1 goto repo_exists
echo [INFO] Creating PUBLIC repository Zeihos/CLIPTORA...
gh repo create Zeihos/CLIPTORA --public --source=. --remote=origin --push
if errorlevel 1 goto failed
goto complete
:repo_exists
echo [INFO] Target repository already exists.
set "CURRENT_ORIGIN="
for /f "delims=" %%U in ('git remote get-url origin 2^>nul') do set "CURRENT_ORIGIN=%%U"
if defined CURRENT_ORIGIN goto check_remote
 git remote add origin https://github.com/Zeihos/CLIPTORA.git
if errorlevel 1 goto failed
goto push_existing
:check_remote
 echo %CURRENT_ORIGIN% | findstr /i /c:"github.com/Zeihos/CLIPTORA" >nul
if errorlevel 1 goto wrong_remote
:push_existing
git branch -M main
gh auth setup-git >nul 2>&1
git push -u origin main
if errorlevel 1 goto failed
:complete
echo [OK] Verify repository: https://github.com/Zeihos/CLIPTORA
echo [INFO] Set description and topics as documented in GITHUB_SETUP.md.
pause
exit /b 0
:wrong_remote
echo [ERROR] Git remote origin points to a different repository. Refusing to push.
goto failed
:no_git
echo [ERROR] Git is not installed. See GITHUB_SETUP.md.
goto failed
:no_gh
echo [ERROR] GitHub CLI is not installed. See GITHUB_SETUP.md.
goto failed
:no_auth
echo [ERROR] Run "gh auth login" to connect your GitHub account.
goto failed
:no_identity
echo [ERROR] Configure Git identity: git config --global user.name and user.email.
:failed
echo [ERROR] Publish was not completed. No force push was attempted.
pause
exit /b 1
