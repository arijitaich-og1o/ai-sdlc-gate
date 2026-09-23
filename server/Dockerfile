# AI SDLC Gate review endpoint. Deploy to Cloud Run in an EU region; run as a service account with
# roles/aiplatform.user (no key file). See README.md.
FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY *.py ./
# Cloud Run sets $PORT. One worker per instance; scale with instances.
CMD ["sh", "-c", "uvicorn app:app --host 0.0.0.0 --port ${PORT:-8080}"]
