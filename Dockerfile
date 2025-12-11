FROM mcr.microsoft.com/playwright/python:v1.57.0-noble

WORKDIR /app

COPY requirements.txt .

RUN apt-get update && apt-get install -y fonts-roboto; rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir -r requirements.txt
RUN playwright install chromium

COPY main.py .

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
