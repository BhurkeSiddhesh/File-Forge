#!/usr/bin/env bash
# Exit on error
set -o errexit

# Upgrade pip and build tools
python -m pip install --upgrade pip setuptools wheel

# Install paddlepaddle from the official mirror FIRST to ensure success on Render
# This is explicitly for Python 3.9 (production target)
python -m pip install paddlepaddle==2.6.2 -i https://www.paddlepaddle.org.cn/packages/stable/cpu/ --no-cache-dir

# Install the rest of the dependencies from requirements.txt
python -m pip install -r requirements.txt
