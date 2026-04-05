# Dockerfile
# Hugging Face Spaces compatible
# Uses standard Python slim base image

FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Install backend dependencies first (better layer caching)
COPY backend/requirements.txt backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

# Install openenv-core for spec compliance and validation
RUN pip install --no-cache-dir "openenv-core>=0.2.0"

# Copy entire project
COPY . .

# Expose HF Spaces default port
EXPOSE 7860

# Start FastAPI server
CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "7860", "--workers", "1"]