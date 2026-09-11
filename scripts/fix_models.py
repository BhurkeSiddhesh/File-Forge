import argparse
import logging
import os
import shutil
import subprocess
import tarfile
from pathlib import Path

import requests

logger = logging.getLogger(__name__)

# Disable MKL-DNN/OneDNN to fix compatibility issues on Windows
# Must be set BEFORE importing paddle (which paddle2onnx does)
os.environ['FLAGS_use_mkldnn'] = '0'
os.environ['MKLDNN_VERBOSE'] = '0'
os.environ['PADDLE_DISABLE_MKLDNN'] = '1'
os.environ['FLAGS_enable_mkldnn'] = '0'
# Force CPU-only mode with basic backend
os.environ['CUDA_VISIBLE_DEVICES'] = ''

# The runtime resolves this exact directory (public/models in the private tree,
# models in the public subtree). Keeping provisioning beside runtime lookup
# makes clean clones and container builds independent of a developer's home.
DEFAULT_OUTPUT_DIR = Path(__file__).resolve().parent.parent / "models"

MODELS = {
    "layout": {
        "url": "https://paddleocr.bj.bcebos.com/ppstructure/models/layout/picodet_lcnet_x1_0_fgd_layout_infer.tar",
        "relative_dir": Path("layout"),
        "name": "picodet_lcnet_x1_0_fgd_layout_infer",
        "target_name": "picodet_lcnet_x1_0_fgd_layout_infer",
    },
    "table": {
        # NOTE: the object is published as ..._SLANet_infer.tar (not _inference); the
        # older _inference URL 404s. The tar extracts to a dir named ..._SLANet_infer,
        # so `name` must match that. The app (scripts/pdf_utils.py) expects the model
        # copied into models/table/en_ppstructure_mobile_v2.0_SLANet_inference/, so
        # rename the folder to _inference when copying it into the repo's models/ dir.
        "url": "https://paddleocr.bj.bcebos.com/ppstructure/models/slanet/en_ppstructure_mobile_v2.0_SLANet_infer.tar",
        "relative_dir": Path("table"),
        "name": "en_ppstructure_mobile_v2.0_SLANet_infer",
        "target_name": "en_ppstructure_mobile_v2.0_SLANet_inference",
    },
    "det": {
        "url": "https://paddleocr.bj.bcebos.com/PP-OCRv3/english/en_PP-OCRv3_det_infer.tar",
        "relative_dir": Path("det/en"),
        "name": "en_PP-OCRv3_det_infer",
        "target_name": "en_PP-OCRv3_det_infer",
    },
    "rec": {
        "url": "https://paddleocr.bj.bcebos.com/PP-OCRv3/english/en_PP-OCRv3_rec_infer.tar",
        "relative_dir": Path("rec/en"),
        "name": "en_PP-OCRv3_rec_infer",
        "target_name": "en_PP-OCRv3_rec_infer",
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
    members = tar.getmembers()
    for member in members:
        if not (member.isfile() or member.isdir()):
            raise ValueError(f"Refusing to extract non-regular member: {member.name}")
        member_path = (dest_dir / member.name).resolve()
        if member_path != dest_resolved and dest_resolved not in member_path.parents:
            raise ValueError(f"Refusing to extract outside destination: {member.name}")
    # Extract validated regular entries ourselves so Python 3.10 builds get the
    # same safe behavior as newer tarfile data filters without relying on an API
    # that did not exist yet in 3.10.
    for member in members:
        target = dest_dir / member.name
        if member.isdir():
            target.mkdir(parents=True, exist_ok=True)
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        source = tar.extractfile(member)
        if source is None:
            raise ValueError(f"Could not read archive member: {member.name}")
        with source, target.open("wb") as destination:
            shutil.copyfileobj(source, destination)


def download_and_extract(model_key, info):
    logger.info("Processing %s model", model_key)
    dest_dir = info["dir"]
    dest_dir.mkdir(parents=True, exist_ok=True)
    
    model_name = info["name"]
    final_model_dir = dest_dir / model_name
    
    if final_model_dir.exists():
        # Check if it has .pdmodel
        if list(final_model_dir.glob("*.pdmodel")):
            logger.info("%s already exists", model_name)
            return final_model_dir

    url = info["url"]
    tar_path = dest_dir / f"{model_name}.tar"
    
    logger.info("Downloading %s", url)
    try:
        response = requests.get(url, stream=True, timeout=60)
        response.raise_for_status()
        with open(tar_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        logger.info("Download complete")

        logger.info("Extracting %s", model_name)
        with tarfile.open(tar_path) as tar:
            _safe_extract(tar, dest_dir)
        logger.info("Extraction complete")
        
        # Cleanup tar
        tar_path.unlink()
        
    except Exception:
        logger.exception("Failed to download/extract %s", model_name)
        tar_path.unlink(missing_ok=True)
        return None
        
    return final_model_dir

def convert_to_onnx(model_dir):
    if not model_dir:
        return

    # Find .pdmodel file
    model_files = list(model_dir.glob("*.pdmodel"))
    if not model_files:
        logger.error("No .pdmodel found in %s", model_dir)
        return

    model_path = model_files[0]
    params_path = model_dir / (model_path.stem + ".pdiparams")
    
    onnx_path = model_dir / "model.onnx"
    if onnx_path.exists():
        logger.info("ONNX model already exists: %s", onnx_path)
        return

    logger.info("Converting %s to ONNX", model_path.name)
    
    # Paddle2ONNX exposes a console executable (the package has no __main__).
    cmd = [
        "paddle2onnx",
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
        logger.info("Conversion successful: %s", onnx_path)
    except subprocess.CalledProcessError as e:
        logger.error(
            "Conversion failed for %s (stdout=%s, stderr=%s)",
            model_dir.name,
            e.stdout,
            e.stderr,
        )


def provision_models(output_dir=DEFAULT_OUTPUT_DIR):
    """Download, convert, and validate the four runtime Paddle ONNX models."""
    output_dir = Path(output_dir).resolve()
    missing = []
    for key, spec in MODELS.items():
        parent = output_dir / spec["relative_dir"]
        target = parent / spec["target_name"]
        target_onnx = target / "model.onnx"
        if target_onnx.is_file():
            logger.info("%s model already provisioned at %s", key, target_onnx)
            continue

        info = {"url": spec["url"], "dir": parent, "name": spec["name"]}
        source = download_and_extract(key, info)
        convert_to_onnx(source)
        if source is not None and source != target and (source / "model.onnx").is_file():
            if target.exists():
                raise RuntimeError(f"Refusing to replace existing model directory: {target}")
            source.rename(target)
        if not target_onnx.is_file():
            missing.append(str(target_onnx))

    if missing:
        raise RuntimeError("Paddle model provisioning incomplete: " + ", ".join(missing))
    return output_dir

if __name__ == "__main__":  # pragma: no cover
    parser = argparse.ArgumentParser(description="Provision Paddle ONNX models")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args()
    logging.basicConfig(
        level=getattr(logging, os.environ.get("LOG_LEVEL", "INFO").upper(), logging.INFO)
    )
    provision_models(args.output_dir)
    logger.info("All Paddle ONNX models are ready in %s", args.output_dir)

