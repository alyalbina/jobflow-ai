@echo off
cd /d "%~dp0"
py -3.12 -m venv .venv
if errorlevel 1 (
  echo Install Python 3.12 from python.org and retry.
  pause
  exit /b 1
)
.venv\Scripts\python.exe -m pip install --no-cache-dir pip==26.2.1 setuptools==84.0.0 wheel==0.48.0
if errorlevel 1 exit /b 1
.venv\Scripts\python.exe -m pip install --force-reinstall --no-cache-dir --no-build-isolation pyaes==1.6.1
if errorlevel 1 exit /b 1
.venv\Scripts\python.exe -m pip install --no-cache-dir --no-build-isolation -r requirements.txt
if errorlevel 1 (
  echo Dependency installation failed. Check your connection and retry.
  pause
  exit /b 1
)
.venv\Scripts\python.exe -c "import jobflow.app, jobflow.telegram_login"
if errorlevel 1 (
  echo Runtime validation failed. Re-run the installer and read the error above.
  pause
  exit /b 1
)
if not exist .env copy .env.example .env >nul
echo Installed. Start-JobFlow.cmd opens the local app. Read docs\windows-guide.md for Telegram setup.
pause
