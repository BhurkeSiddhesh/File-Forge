#!/usr/bin/env bash
# Exit on error
set -o errexit

# Upgrade pip and build tools
python -m pip install --upgrade pip setuptools wheel

# Install dependencies (RapidOCR is the default OCR backend — works on x86_64 and ARM64)
python -m pip install -r requirements.txt

# Optional PaddleOCR backend (x86_64 only). Enable with OCR_BACKEND=paddle.
# paddlepaddle comes from the official mirror to avoid PyPI resolution issues.
if [ "${OCR_BACKEND:-rapidocr}" = "paddle" ]; then
    python -m pip install paddlepaddle==2.6.2 -i https://www.paddlepaddle.org.cn/packages/stable/cpu/ --no-cache-dir
    python -m pip install "paddleocr>=2.6,<3.0"
fi
