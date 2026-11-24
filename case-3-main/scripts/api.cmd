@echo off
setlocal EnableExtensions
cd /d "%~dp0.."

REM Cursor / corporate proxy often breaks Vision (403). Always clear for local desk.
set "HTTP_PROXY="
set "HTTPS_PROXY="
set "http_proxy="
set "https_proxy="
set "ALL_PROXY="
set "all_proxy="
set "NO_PROXY="
set "no_proxy="

if not exist .env if exist .env.example copy /Y .env.example .env >nul
if exist .env for /f "usebackq eol=# tokens=1,* delims==" %%A in (".env") do if not "%%A"=="" set "%%A=%%B"

REM Prefer editable install; fall back to src/ so uvicorn finds case3 after git pull.
set "PYTHONPATH=%CD%\src;%PYTHONPATH%"

set "PY="
where python >nul 2>&1 && python -c "import sys; raise SystemExit(0 if sys.version_info>=(3,9) else 1)" >nul 2>&1 && set "PY=python"
if not defined PY where py >nul 2>&1 && for %%V in (3.13 3.12 3.11 3.10 3.9 3) do if not defined PY (
  py -%%V -c "import sys; raise SystemExit(0 if sys.version_info>=(3,9) else 1)" >nul 2>&1 && set "PY=py -%%V"
)
if not defined PY (echo ERROR: Python 3.9+ not on PATH. Run scripts\setup.cmd & exit /b 1)

%PY% -c "import case3,uvicorn,pptx" >nul 2>&1
if errorlevel 1 (
  echo ERROR: packages missing ^(need python-pptx^). Run: scripts\setup.cmd
  echo        or: %PY% -m pip install -e .
  exit /b 1
)

echo.
echo API  → http://127.0.0.1:8000/docs
echo Health→ http://127.0.0.1:8000/api/health
echo Сайт → вторым окном: scripts\web.cmd  → http://127.0.0.1:5173
echo .env → VISION_API_BASE_URL = Qwen ^(не коммить ключи^)
echo.
REM --reload breaks long BackgroundTasks (Liber progress poll). Opt-in: set CASE3_RELOAD=1
if /I "%CASE3_RELOAD%"=="1" (
  echo reload ON ^(dev only^)
  %PY% -m uvicorn case3.api:app --reload --host 127.0.0.1 --port 8000
) else (
  %PY% -m uvicorn case3.api:app --host 127.0.0.1 --port 8000
)
endlocal
