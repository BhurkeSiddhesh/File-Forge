#!/usr/bin/env bash
# Exit on error
set -o errexit

# Upgrade pip and build tools
python -m pip install --upgrade pip setuptools wheel

# Install paddlepaddle from the official mirror to ensure Linux wheel resolution
# We use Python 3.9 (required to be set in Render Env Vars) for best compatibility
python -m pip install paddlepaddle==2.6.2 -i https://www.paddlepaddle.org.cn/packages/stable/cpu/

# Install the rest of the dependencies
python -m pip install -r requirements.txt
