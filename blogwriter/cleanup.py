"""Weekly storage clean-up (python -m blogwriter.cleanup): keep the newest CLEANUP_KEEP (default 3) video folders in
object storage with all their files, empty every older one except its PDFs. CLEANUP_DRY_RUN=true only reports."""
import os
import sys

from .config import Settings
from .storage import keep_latest_runs


def main() -> int:
    try:
        keep = max(1, int(os.environ.get("CLEANUP_KEEP") or 3))
    except ValueError:
        keep = 3
    dry = (os.environ.get("CLEANUP_DRY_RUN") or "").strip().lower() in ("1", "true", "yes")
    result = keep_latest_runs(Settings.from_env(), keep=keep, dry_run=dry)
    print(f"[cleanup] done ({'dry run' if dry else 'for real'}): {result['deleted_files']} file(s), "
          f"{result['deleted_bytes'] / 1e9:.2f} GB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
