# Python 3.10 remains the gold standard for the OCR/OpenCV stack on Linux
FROM python:3.10

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Install system dependencies for OCR and Image Processing
RUN apt-get update && apt-get install -y \
    build-essential \
    libgl1 \
    libglib2.0-0 \
    libgomp1 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    tesseract-ocr \
    && rm -rf /var/lib/apt/lists/*

# Set work directory
WORKDIR /app

# Upgrade pip and install build dependencies
RUN pip install --no-cache-dir --upgrade pip setuptools wheel

# OCR backend selection (see scripts/ocr_engine.py):
#   rapidocr — default; ONNX Runtime, works on x86_64 AND arm64 (Oracle A1 etc.)
#   paddle   — best layout recovery (tables/columns); x86_64 only
#   none     — no OCR; pair with DISABLE_AI=1 at runtime for a lightweight image
ARG OCR_BACKEND=rapidocr
ENV OCR_BACKEND=${OCR_BACKEND}

# Copy requirements and install packages (includes rapidocr)
COPY requirements.txt requirements-ai-paddle.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Optional Paddle backend (x86_64 only). paddlepaddle comes from the official
# mirror to bypass PyPI resolution issues on some Linux distros.
RUN if [ "$OCR_BACKEND" = "paddle" ]; then \
        pip install --no-cache-dir paddlepaddle==2.6.2 -i https://www.paddlepaddle.org.cn/packages/stable/cpu/ && \
        pip install --no-cache-dir "paddleocr>=2.6,<3.0"; \
    fi

# Copy the rest of the application
COPY . .

# Optional build-time warm-up / smoke test of the configured OCR backend.
# NOTE: this must run *after* `COPY . .`, not right after pip install — the
# paddle backend needs the ONNX models vendored under models/ (det, layout,
# rec, table). It exercises the real production code path, so a broken/missing
# model or engine fails the build instead of the first user request. For
# rapidocr it also caches any model downloads into the image layer. Off by
# default so the no-AI image builds fast. Enable for an AI-enabled image:
#     docker build --build-arg WARMUP_AI=1 .
ARG WARMUP_AI=0
RUN if [ "$WARMUP_AI" = "1" ]; then \
        python -c "from scripts.ocr_engine import get_ocr_engine; e = get_ocr_engine(); print(('%s engine loaded OK' % e.name) if e else 'no OCR backend configured')"; \
    fi

# Ensure directories exist with correct permissions
RUN mkdir -p uploads outputs && chmod 777 uploads outputs

# Command to run the application using the PORT environment variable
# Use shell form to allow environment variable expansion
CMD uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}
