# Engine (FastAPI) production image.
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Install deps first for layer caching.
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

EXPOSE 8000

# uvicorn binds 0.0.0.0 so the container is reachable. No --reload in production.
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
