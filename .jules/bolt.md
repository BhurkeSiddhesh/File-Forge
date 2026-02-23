## 2026-02-04 - Caching Heavy AI Models
**Learning:** Re-initializing heavy deep learning models (like PaddleOCR's PPStructure) inside request handlers destroys performance (seconds vs milliseconds).
**Action:** Always wrap heavy model initialization in a Singleton pattern or global cache, and warm it up during application startup.
