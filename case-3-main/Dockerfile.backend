# case-3 backend — FastAPI + Playwright Chromium + XeLaTeX + Pandoc + LibreOffice
FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    CASE3_ROOT=/app \
    CASE3_TEX_LOCAL=1 \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

RUN apt-get update && \
    apt-get install --no-install-recommends -y \
      ca-certificates \
      curl \
      libatomic1 \
      latexmk \
      lmodern \
      texlive-xetex \
      texlive-lang-cyrillic \
      texlive-latex-recommended \
      texlive-latex-extra \
      texlive-fonts-recommended \
      fonts-dejavu \
      fonts-liberation \
      pandoc \
      libreoffice-impress \
      libreoffice-writer \
    && apt-get --purge remove -y '.*-doc$' \
    && apt-get clean -y

WORKDIR /app

COPY pyproject.toml ./
COPY src ./src
COPY prompt ./prompt
COPY assets ./assets

RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir . && \
    python -m playwright install --with-deps chromium && \
    apt-get clean -y && \
    rm -rf /var/lib/apt/lists/*

RUN mkdir -p /app/runs/out /app/runs/work /app/runs/uploads /app/runs/logs /app/local

EXPOSE 8000

CMD ["uvicorn", "case3.api:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
