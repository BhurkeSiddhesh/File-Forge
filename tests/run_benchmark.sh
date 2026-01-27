#!/bin/bash
# @jules: We should probably provide a .ps1 or .bat version of this for Windows users.
set -e

# Setup
echo "Setting up benchmark data..."
python3 tests/benchmark_setup.py

echo "Running Baseline (Shell Loop)..."
# Use python to measure time to avoid 'date' precision issues and 'bc' dependency
python3 -c "
import time
import subprocess
import glob

files = glob.glob('benchmark_data/*.pdf')
start = time.time()
for f in files:
    subprocess.run(['python3', 'pdf_password_remover.py', f, 'benchmark'], stdout=subprocess.DEVNULL)
end = time.time()
print(f'Baseline Duration: {end - start:.4f} seconds')
"

# Cleanup output from baseline
rm benchmark_data/*_unlocked.pdf

echo "Running Optimized (Batch Mode)..."
python3 -c "
import time
import subprocess

start = time.time()
subprocess.run(['python3', 'pdf_password_remover.py', 'benchmark_data', 'benchmark'], stdout=subprocess.DEVNULL)
end = time.time()
print(f'Optimized Duration: {end - start:.4f} seconds')
"

# Cleanup
rm -rf benchmark_data
echo "Done."
