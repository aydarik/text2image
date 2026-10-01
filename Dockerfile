FROM mcr.microsoft.com/playwright/python:v1.63.0-resolute

WORKDIR /app

COPY requirements.txt .

# syntax=docker/dockerfile:1
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt/lists,sharing=locked \
    apt-get update && \
    apt-get install -y --no-install-recommends fonts-roboto

RUN pip install --no-cache-dir -r requirements.txt
RUN playwright install chromium

COPY main.py .
COPY cache_manager.py .
COPY templates/ ./templates/

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]
