FROM python:3.11-slim

# Install system dependencies for audio/voice features if needed
RUN apt-get update && apt-get install -y ffmpeg && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ /app/
COPY agent/ /agent/
COPY scripts/ /app/scripts/

# Expose backend port
EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
