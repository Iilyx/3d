@echo off
REM Upload runs\ artifacts to a NEW branch debug/upload-STAMP (no PDF/DOCX).
REM Non-interactive: no pause / no more / no pager.
setlocal EnableExtensions
cd /d "%~dp0.."
if not exist .git (echo Not a git repo. & exit /b 1)

set "GIT_PAGER="
set "PAGER="

for /f %%I in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMddTHHmmss"') do set STAMP=%%I
set "DEST=debug-bundle\%STAMP%"
set "BRANCH=debug/upload-%STAMP%"

mkdir "%DEST%\out" 2>nul
mkdir "%DEST%\logs" 2>nul
mkdir "%DEST%\work" 2>nul
mkdir "%DEST%\uploads" 2>nul

echo [1/4] Copy runs\out logs work uploads → %DEST%
if exist runs\out xcopy /E /I /Y /Q "runs\out\*" "%DEST%\out\" >nul
if exist runs\logs xcopy /E /I /Y /Q "runs\logs\*" "%DEST%\logs\" >nul
if exist runs\work xcopy /E /I /Y /Q "runs\work\*" "%DEST%\work\" >nul
if exist runs\uploads xcopy /E /I /Y /Q "runs\uploads\*" "%DEST%\uploads\" >nul

REM Drop heavy binaries by default (keep tex/logs/raw/json for agent).
REM KEEP_PDF=1 → leave PDF (and DOCX) for print-quality review.
REM KEEP_MEDIA=1 → leave PNG/slides/deck/html (often 100+ MB → GitHub push 500).
REM KEEP_WORK=1 → include runs\work (duplicate tex; usually not needed).
if /I "%KEEP_PDF%"=="1" (
  echo       KEEP_PDF=1 — leaving PDF/DOCX in bundle
) else (
  del /s /q "%DEST%\*.pdf" 2>nul
  del /s /q "%DEST%\*.docx" 2>nul
)

if /I "%KEEP_MEDIA%"=="1" (
  echo       KEEP_MEDIA=1 — keeping PNG/slides/deck assets
) else (
  echo [1b/4] Slim: drop PNG/slides/docx_media/deck/html/js/fonts...
  del /s /q "%DEST%\*.png" 2>nul
  del /s /q "%DEST%\*.jpg" 2>nul
  del /s /q "%DEST%\*.jpeg" 2>nul
  del /s /q "%DEST%\*.js" 2>nul
  del /s /q "%DEST%\*.woff2" 2>nul
  del /s /q "%DEST%\*.html" 2>nul
  del /s /q "%DEST%\*.pptx" 2>nul
  for /d /r "%DEST%" %%D in (slides docx_media chart_work .undo) do (
    if exist "%%D\" rd /s /q "%%D" 2>nul
  )
)

if /I not "%KEEP_WORK%"=="1" (
  if exist "%DEST%\work" rd /s /q "%DEST%\work" 2>nul
)

for /f %%S in ('powershell -NoProfile -Command "$s=(Get-ChildItem -LiteralPath '%DEST%' -Recurse -File -ErrorAction SilentlyContinue ^| Measure-Object -Property Length -Sum).Sum; if($s){[math]::Round($s/1MB,1)}else{0}"') do set "BUNDLE_MB=%%S"
echo       bundle ~%BUNDLE_MB% MB ^(slim default; set KEEP_MEDIA=1 only if agent needs PNG^)
if %BUNDLE_MB% GEQ 90 (
  echo WARNING: bundle still ^>= 90 MB — push may fail with GitHub Internal Server Error.
  echo          Trim runs\out or omit huge source.raw_model.txt before push.
)

dir /s /b "%DEST%\*.json" "%DEST%\*.tex" "%DEST%\*.txt" "%DEST%\*.log" 2>nul | findstr /r "." >nul
if errorlevel 1 (
  echo FAIL: runs\ пустой. Сначала сделай генерацию в UI, потом снова этот скрипт.
  exit /b 1
)
echo       files ready.

for /f %%I in ('git rev-parse --abbrev-ref HEAD') do set "CURBRANCH=%%I"
echo [2/4] Branch %BRANCH% from %CURBRANCH%
git --no-pager checkout -B "%BRANCH%"
if errorlevel 1 (echo FAIL: git checkout & exit /b 1)

echo [3/4] Commit
git --no-pager add -f "%DEST%"
git --no-pager status --short "%DEST%"
git --no-pager commit -m "debug: %STAMP% (slim tex+logs+raw)"
if errorlevel 1 (
  echo FAIL: nothing to commit
  git --no-pager checkout "%CURBRANCH%"
  exit /b 1
)

echo [4/4] Push origin %BRANCH%
git --no-pager push -u origin "%BRANCH%"
if errorlevel 1 (
  echo FAIL: git push — GitHub rejected the pack ^(often Internal Server Error when bundle ^>~100 MB^).
  echo        Retry without KEEP_MEDIA; trim runs\out old folders; or push again in a few minutes.
  echo        Auth: gh auth login / git credential
  git --no-pager checkout "%CURBRANCH%"
  exit /b 1
)

git --no-pager checkout "%CURBRANCH%"
echo.
echo OK. Скажи агенту ветку: %BRANCH%
echo https://github.com/Borisserz/case-3/tree/%BRANCH%
endlocal
