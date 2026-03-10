FROM python:3.11-slim-bookworm
# Install system dependencies
RUN apt-get update && apt-get install -y \
    poppler-utils \
    ghostscript \
    qpdf \
    tesseract-ocr \
    tesseract-ocr-eng \
    tesseract-ocr-fra \
    tesseract-ocr-deu \
    tesseract-ocr-spa \
    wkhtmltopdf \
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender1 \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create temp directories
RUN mkdir -p temp_files/uploads temp_files/processed

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
