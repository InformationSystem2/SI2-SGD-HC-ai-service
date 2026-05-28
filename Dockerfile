FROM python:3.11-slim

WORKDIR /app

# Dependencias del sistema
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    poppler-utils \
    libgl1 \
    libglib2.0-0 \
    tesseract-ocr \
    && rm -rf /var/lib/apt/lists/*

# OCR español
RUN mkdir -p /usr/share/tesseract-ocr/4.00/tessdata && \
    curl -sL https://github.com/tesseract-ocr/tessdata/raw/main/spa.traineddata \
    -o /usr/share/tesseract-ocr/4.00/tessdata/spa.traineddata || true

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Cloud Run usa PORT
EXPOSE 8080

ENV PYTHONUNBUFFERED=1

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8080}"]
