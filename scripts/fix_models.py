import os
import requests
import tarfile
import shutil
from pathlib import Path
import subprocess
import sys

# Disable MKL-DNN/OneDNN to fix compatibility issues on Windows
# Must be set BEFORE importing paddle (which paddle2onnx does)
os.environ['FLAGS_use_mkldnn'] = '0'
os.environ['MKLDNN_VERBOSE'] = '0'
os.environ['PADDLE_DISABLE_MKLDNN'] = '1'
os.environ['FLAGS_enable_mkldnn'] = '0'
# Force CPU-only mode with basic backend
os.environ['CUDA_VISIBLE_DEVICES'] = ''

# Define paths
USER_HOME = Path.home()
PADDLE_DIR = USER_HOME / ".paddleocr" / "whl"
LAYOUT_DIR = PADDLE_DIR / "layout"
TABLE_DIR = PADDLE_DIR / "table"
DET_DIR = PADDLE_DIR / "det" / "en"
REC_DIR = PADDLE_DIR / "rec" / "en"

MODELS = {
    "layout": {
        "url": "https://paddleocr.bj.bcebos.com/ppstructure/models/layout/picodet_lcnet_x1_0_fgd_layout_infer.tar",
        "dir": LAYOUT_DIR,
        "name": "picodet_lcnet_x1_0_fgd_layout_infer"
    },
    "table": {
        # NOTE: the object is published as ..._SLANet_infer.tar (not _inference); the
        # older _inference URL 404s. The tar extracts to a dir named ..._SLANet_infer,
        # so `name` must match that. The app (scripts/pdf_utils.py) expects the model
        # copied into models/table/en_ppstructure_mobile_v2.0_SLANet_inference/, so
        # rename the folder to _inference when copying it into the repo's models/ dir.
        "url": "https://paddleocr.bj.bcebos.com/ppstructure/models/slanet/en_ppstructure_mobile_v2.0_SLANet_infer.tar",
        "dir": TABLE_DIR,
        "name": "en_ppstructure_mobile_v2.0_SLANet_infer"
    },
    "det": {
        "url": "https://paddleocr.bj.bcebos.com/PP-OCRv3/english/en_PP-OCRv3_det_infer.tar",
        "dir": DET_DIR,
        "name": "en_PP-OCRv3_det_infer"
    },
    "rec": {
        "url": "https://paddleocr.bj.bcebos.com/PP-OCRv3/english/en_PP-OCRv3_rec_infer.tar",
        "dir": REC_DIR,
        "name": "en_PP-OCRv3_rec_infer"
    }
}

def _safe_extract(tar, dest_dir):
    """Extract only regular files/dirs that resolve inside dest_dir.

    Guards against CVE-2007-4559: an unfiltered `extractall()` follows a
    member's path verbatim, so a tar containing e.g. "../../.ssh/authorized_keys"
    (or an absolute path) writes outside dest_dir. Symlink/hardlink/device
    members are rejected outright rather than resolved, since their target can
    point anywhere regardless of what their own path says.
    """
    dest_resolved = dest_dir.resolve()
    for member in tar.getmembers():
        if not (member.isfile() or member.isdir()):
            raise ValueError(f"Refusing to extract non-regular member: {member.name}")
        member_path = (dest_dir / member.name).resolve()
        if member_path != dest_resolved and dest_resolved not in member_path.parents:
            raise ValueError(f"Refusing to extract outside destination: {member.name}")
    tar.extractall(path=dest_dir)


def download_and_extract(model_key, info):
    print(f"Processing {model_key} model...")
    dest_dir = info["dir"]
    dest_dir.mkdir(parents=True, exist_ok=True)
    
    model_name = info["name"]
    final_model_dir = dest_dir / model_name
    
    if final_model_dir.exists():
        # Check if it has .pdmodel
        if list(final_model_dir.glob("*.pdmodel")):
            print(f"  {model_name} already exists.")
            return final_model_dir

    url = info["url"]
    tar_path = dest_dir / f"{model_name}.tar"
    
    print(f"  Downloading {url}...")
    try:
        response = requests.get(url, stream=True, timeout=60)
        response.raise_for_status()
        with open(tar_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        print("  Download complete.")

        print("  Extracting...")
        with tarfile.open(tar_path) as tar:
            _safe_extract(tar, dest_dir)
        print("  Extraction complete.")
        
        # Cleanup tar
        tar_path.unlink()
        
    except Exception as e:
        print(f"  Failed to download/extract {model_name}: {e}")
        return None
        
    return final_model_dir

def convert_to_onnx(model_dir):
    if not model_dir:
        return

    # Find .pdmodel file
    model_files = list(model_dir.glob("*.pdmodel"))
    if not model_files:
        print(f"  No .pdmodel found in {model_dir}")
        return

    model_path = model_files[0]
    params_path = model_dir / (model_path.stem + ".pdiparams")
    
    onnx_path = model_dir / "model.onnx"
    if onnx_path.exists():
        print(f"  ONNX model already exists: {onnx_path}")
        return

    print(f"  Converting {model_path.name} to ONNX...")
    
    # Use sys.executable to ensure we use the venv python
    cmd = [
        sys.executable, "-m", "paddle2onnx",
        "--model_dir", str(model_dir),
        "--model_filename", model_path.name,
        "--params_filename", params_path.name,
        "--save_file", str(onnx_path),
        "--opset_version", "11",
        "--enable_onnx_checker", "True"
    ]
    
    # Pass environment with disabled MKLDNN
    env = os.environ.copy()
    
    try:
        # Run with large timeout as conversion can be slow
        result = subprocess.run(cmd, check=True, capture_output=True, env=env, text=True)
        print(f"  Conversion successful: {onnx_path}")
    except subprocess.CalledProcessError as e:
        print(f"  Conversion failed for {model_dir.name}:")
        print(f"  STDOUT: {e.stdout}")
        print(f"  STDERR: {e.stderr}")

if __name__ == "__main__":  # pragma: no cover
    for key, info in MODELS.items():
        model_dir = download_and_extract(key, info)
        convert_to_onnx(model_dir)
    print("\nAll models processed. You can now use use_onnx=True")

