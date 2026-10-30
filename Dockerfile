FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && playwright install --with-deps chromium

COPY . .
RUN useradd --create-home --uid 10001 appuser \
    && mkdir -p /app/data /app/output \
    && chown -R appuser:appuser /app

USER appuser
CMD ["python", "tools/daily_run.py"]
