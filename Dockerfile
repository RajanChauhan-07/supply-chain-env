# Dockerfile
# Hugging Face Spaces compatible — optimized for fast builds (<600s)

FROM python:3.10-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV PIP_NO_CACHE_DIR=1

# Single pip install — all dependencies in one layer, pinned versions
COPY backend/requirements.txt backend/requirements.txt
RUN pip install -r backend/requirements.txt openenv-core==0.1.0

# Copy project
COPY . .

EXPOSE 7860

CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "7860", "--workers", "1"]