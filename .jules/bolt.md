# Performance Learnings & Optimizations

## 2026-02-10: Iterative Image Resizing
- **Optimization**: Switched from repeated disk I/O to `io.BytesIO` buffers for iterative `target_size` resizing.
- **Impact**: Reduced disk writes (N writes -> 1 write per operation).
- **Observation**: Performance gain may be masked by CPU-bound JPEG compression or fast filesystems, but efficiency is improved by reducing syscalls and disk wear.
- **Lesson**: Use `cat <<'EOF'` in bash to safely write python scripts with backticks.
