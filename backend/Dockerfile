FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PORT=8080

RUN apt-get update \
 && apt-get install -y --no-install-recommends ffmpeg \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY src ./src

RUN useradd --create-home kettu
USER kettu

# One worker on purpose: the job queue and the Gnani gate live in this process.
CMD ["sh", "-c", "uvicorn kettu.main:app --app-dir src --host 0.0.0.0 --port ${PORT} --workers 1 --proxy-headers"]
