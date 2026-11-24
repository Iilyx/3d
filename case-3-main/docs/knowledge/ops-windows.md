# Ops — Windows desk

Финальный прогон (3 запроса + readiness): [`windows-final-run.md`](windows-final-run.md).

## First install

1. Docker Desktop running  
2. `git pull origin main`  
3. `scripts\setup.cmd`  
4. Edit `.env`: `VISION_*`, `IMAGE_API_BASE_URL`, optional `CASE3_MAX_CHARTS`  
5. `cd web && npm install`  
6. `scripts\api.cmd` + `scripts\web.cmd`  
7. Check `http://127.0.0.1:8000/api/health` → `ok` / vision / image flags  

## After every pull

```cmd
git pull origin main
cd web && npm install
```

Restart api + web. If charts blank: `python -m playwright install chromium`.

`scripts\*.cmd` are CRLF. API refuses to start without `python-pptx` (`scripts\setup.cmd`). Health must show `vision_configured` + `docker_ok` + `playwright_ok` before Liber runs.

## Common fixes

| Symptom | Fix |
|---------|-----|
| `No module named 'pptx'` / api crash on import | `scripts\setup.cmd` or `python -m pip install -e .` (needs `python-pptx`) |
| Empty model / no documentclass | `VISION_REASONING=off`, restart api |
| Truncated TeX | raise `VISION_MAX_TOKENS`, lower max_charts |
| Charts `Timeout 15000ms` / all `cht_*` fail | `.env`: `CASE3_CHART_TIMEOUT_S=45` (or delete line), restart `api.cmd`; code default is 45s |
| `UnicodeDecodeError` cp1251 in `_readerthread` / UI «Остановлено» mid-PDF | Pull fix (`procutil.run_captured`); restart `api.cmd` — was Docker TeX UTF-8 vs Win locale |
| No Docker image | `setup.cmd` / build image |
| Port busy | kill old api/web |
| Proxy breaks Vision | unset HTTP(S)_PROXY for api session |

## Do not ship to git

`.env`, `runs/*` artifacts, local PDF/DOCX outputs.

## push-debug (agent handoff)

Default bundle is **slim** (~few MB): `*.tex`, `*.log`, `*.json`, `*.txt` — no PNG, `slides/`, `docx_media/`, deck.  
If push fails with **remote rejected … Internal Server Error** and ~100+ MB in git output → old script copied all PNG; `git pull` and re-run `scripts\push-debug.cmd`.  
Optional: `set KEEP_MEDIA=1` (heavy), `set KEEP_PDF=1`, `set KEEP_WORK=1`.
