"""One-shot helper: extract missing coverage lines from coverage_public.json
into missing_lines.txt (the JSON is a single huge line, awkward to inspect)."""
import json
from pathlib import Path


def run(ctx):
    base = Path(r"C:\Users\siddh\Desktop\Projects\file-forge-private\public")
    d = json.loads((base / "coverage_public.json").read_text())
    lines = []
    for f, v in d["files"].items():
        ml = v.get("missing_lines") or []
        if ml:
            lines.append(f + " :: " + ",".join(map(str, ml)))
    out = "\n".join(lines)
    (base / "missing_lines.txt").write_text(out)
    return {"note": f"{len(lines)} files with missing lines"}
