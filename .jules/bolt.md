
### PaddleOCR Initialization Performance
- **Date**: 2026-02-10
- **Context**: `pdf_utils.py`
- **Problem**: Repeated calls to `pdf_to_word_paddle` were slow because `PPStructure` was initialized inside the function.
- **Learning**: Initialization takes ~70% of the total time for a single page conversion.
- **Solution**: Moved `PPStructure` initialization to a singleton `get_paddle_engine()` function.
- **Result**: Reduced subsequent execution time from ~3.6s to ~0.8s (approx 4.5x speedup for single page tasks).
