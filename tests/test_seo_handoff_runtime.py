"""Execute the real deep-link bootstrap in source order, including IndexedDB.

String-level link tests missed a const accessed before initialization: every
landing-page upload navigated successfully, then crashed before restoring files.
"""
import json
import shutil
import subprocess
from pathlib import Path

import pytest

NODE = shutil.which("node")
pytestmark = pytest.mark.skipif(NODE is None, reason="node not available")
SCRIPT = Path(__file__).resolve().parents[1] / "static" / "script.js"

HARNESS = r"""
const vm = require('node:vm');
const input = JSON.parse(require('node:fs').readFileSync(0, 'utf8'));
const result = {changes: [], deleted: false, category: null};
const elements = new Map();
const document = {getElementById(id) {
  if (!elements.has(id)) elements.set(id, {
    classList: {add() {}, remove() {}}, scrollIntoView() {}, click() {},
    dispatchEvent(event) {
      result.changes.push({id, event: event.type, names: this.files.map(f => f.name)});
    }
  });
  return elements.get(id);
}};
const indexedDB = {open() {
  const request = {};
  request.result = {
    close() {}, objectStoreNames: {contains: () => true},
    transaction() {
      const tx = {};
      tx.objectStore = () => ({
        delete: () => {result.deleted = true;},
        get() {
          const get = {result: input.record};
          setImmediate(() => {get.onsuccess(); tx.oncomplete();});
          return get;
        }
      });
      return tx;
    }
  };
  setImmediate(() => request.onsuccess());
  return request;
}};
class Transfer {
  constructor() {this.files = []; this.items = {add: f => this.files.push(f)};}
}
const context = {
  document, indexedDB, URLSearchParams, setTimeout,
  DataTransfer: Transfer,
  File: class {constructor(parts, name, options) {this.name = name; this.type = options.type;}},
  Event: class {constructor(type) {this.type = type;}},
  showDrillDown: category => {result.category = category;},
  toggleImageMode() {},
  location: {search: input.search}
};
context.window = context;
vm.runInNewContext(input.source, context);
setTimeout(() => process.stdout.write(JSON.stringify(result)), 30);
"""


def run_bootstrap(search: str, record: dict | None) -> dict:
    source = SCRIPT.read_text(encoding="utf-8")
    source = source[source.index("const DEEP_LINK_OPS ="):source.index("// Theme Toggle & Automatic")]
    proc = subprocess.run(
        [NODE, "-e", HARNESS], input=json.dumps({"source": source, "search": search, "record": record}),
        capture_output=True, text=True, timeout=10,
    )
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout)


@pytest.mark.parametrize("category,op,input_id,count", [
    ("pdf", "compress-pdf", "file-input", 1),
    ("pdf", "merge-pdf", "file-input", 2),
    ("image", "resize-image", "image-file-input", 1),
    ("excel", "excel-to-pdf", "excel-file-input", 1),
    ("ppt", "powerpoint-to-pdf", "ppt-file-input", 1),
    ("word", "word-to-pdf", "word-file-input", 1),
])
def test_landing_upload_restored_without_startup_error(category, op, input_id, count):
    names = [f"sample-{n}.pdf" for n in range(count)]
    record = {"files": [{"blob": {}, "name": name, "type": "application/pdf"} for name in names]}
    result = run_bootstrap(f"?tool={category}&op={op}&handoff=1", record)
    assert result == {"category": category, "deleted": True,
                      "changes": [{"id": input_id, "event": "change", "names": names}]}


def test_missing_handoff_keeps_the_normal_picker_available():
    result = run_bootstrap("?tool=pdf&op=compress-pdf&handoff=1", None)
    assert result["category"] == "pdf" and result["changes"] == []
