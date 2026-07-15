import time
import requests
import threading
from multiprocessing import Process
import uvicorn
import os
import shutil
from pathlib import Path
from main import app, UPLOAD_DIR, OUTPUT_DIR
import pillow_heif
from PIL import Image

# Ensure directories exist
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

def run_server():
    # Use a different port to avoid conflicts
    uvicorn.run(app, host="127.0.0.1", port=8002, log_level="error")

def create_heic_file():
    # create a large HEIC file
    print("Generating large HEIC file...")
    img = Image.new('RGB', (3000, 3000), color='red')
    # Add some noise/detail so it's not trivial to compress
    from random import randint
    pixels = img.load()
    for i in range(0, 3000, 10):
        for j in range(0, 3000, 10):
            pixels[i, j] = (randint(0, 255), randint(0, 255), randint(0, 255))

    pillow_heif.register_heif_opener()
    img.save("benchmark_test.heic", format="HEIF", quality=50)
    print("HEIC file generated.")

def benchmark():
    if not os.path.exists("benchmark_test.heic"):
        create_heic_file()

    print("Starting server...")
    proc = Process(target=run_server)
    proc.start()

    # Wait for server to start
    time.sleep(3)

    try:
        results = {}

        def heavy_request():
            try:
                with open("benchmark_test.heic", "rb") as f:
                    start = time.time()
                    resp = requests.post("http://127.0.0.1:8002/api/image/heic-to-jpeg", files={"file": f})
                    end = time.time()
                    print(f"Heavy request status: {resp.status_code}, time: {end - start:.4f}s")
            except Exception as e:
                print(f"Heavy request failed: {e}")

        # Start heavy request in background
        t = threading.Thread(target=heavy_request)
        t.start()

        # Give it a moment to hit the server and start processing
        time.sleep(0.5)

        # Start light request
        print("Sending light request...")
        start = time.time()
        try:
            # Requesting root which serves a static file
            requests.get("http://127.0.0.1:8002/", timeout=5)
        except requests.exceptions.ReadTimeout:
            print("Light request timed out!")
        except Exception as e:
            print(f"Light request failed: {e}")

        end = time.time()
        duration = end - start
        print(f"Light request took: {duration:.4f}s")

        t.join(timeout=10)

    finally:
        print("Stopping server...")
        proc.terminate()
        proc.join()

        # Cleanup
        if os.path.exists("benchmark_test.heic"):
            os.remove("benchmark_test.heic")

if __name__ == "__main__":
    benchmark()
