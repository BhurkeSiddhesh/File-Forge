$ErrorActionPreference = "Stop"

# Setup
Write-Host "Setting up benchmark data..."
python tests/benchmark_setup.py

Write-Host "Running Baseline (Shell Loop)..."
# Use python to measure time to avoid 'date' precision issues and 'bc' dependency
python -c "
import sys
import time
import subprocess
import glob

files = glob.glob('benchmark_data/*.pdf')
start = time.time()
for f in files:
    subprocess.run([sys.executable, 'pdf_password_remover.py', f, 'benchmark'], stdout=subprocess.DEVNULL)
end = time.time()
print(f'Baseline Duration: {end - start:.4f} seconds')
"

# Cleanup output from baseline
Remove-Item benchmark_data/*_unlocked.pdf -ErrorAction SilentlyContinue

Write-Host "Running Optimized (Batch Mode)..."
python -c "
import sys
import time
import subprocess

start = time.time()
subprocess.run([sys.executable, 'pdf_password_remover.py', 'benchmark_data', 'benchmark'], stdout=subprocess.DEVNULL)
end = time.time()
print(f'Optimized Duration: {end - start:.4f} seconds')
"

# Cleanup
Remove-Item benchmark_data -Recurse -Force
Write-Host "Done."
