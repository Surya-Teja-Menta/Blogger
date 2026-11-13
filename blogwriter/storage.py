"""Upload a finished run to S3-compatible object storage (Cloudflare R2, Backblaze B2, MinIO, AWS S3)."""
import mimetypes
import os
import zipfile
from datetime import datetime, timedelta, timezone
from typing import Callable, Dict, List, Tuple

from .config import Settings

SIGNED_LINK_SECONDS = 7 * 24 * 3600      # the longest a SigV4 signed link may live


def _client(settings: Settings):
    import boto3
    from botocore.config import Config
    return boto3.client("s3", endpoint_url=settings.s3_endpoint, region_name=settings.s3_region,
                        aws_access_key_id=settings.s3_access_key, aws_secret_access_key=settings.s3_secret_key,
                        config=Config(signature_version="s3v4", retries={"max_attempts": 3}))


def link_for(settings: Settings, key: str, s3=None) -> str:
    """A download link for one stored file: its public URL when S3_PUBLIC_URL is set, otherwise a 7-day signed link
    ('' when storage is not set up or the link cannot be made)."""
    if not key or not settings.storage_configured:
        return ""
    if settings.s3_public_url:
        return f"{settings.s3_public_url}/{key}"
    try:
        return (s3 or _client(settings)).generate_presigned_url(
            "get_object", Params={"Bucket": settings.s3_bucket, "Key": key}, ExpiresIn=SIGNED_LINK_SECONDS)
    except Exception:
        return ""


def put_text(settings: Settings, key: str, text: str, mime: str = "text/plain; charset=utf-8", s3=None) -> bool:
    """Store a small text file at `key` in the private bucket. Never raises; False when it could not."""
    if not settings.storage_configured:
        return False
    try:
        (s3 or _client(settings)).put_object(Bucket=settings.s3_bucket, Key=key, Body=text.encode("utf-8"),
                                             ContentType=mime)
        return True
    except Exception:
        return False


def get_text(settings: Settings, key: str, s3=None) -> str:
    """A small text file from the private bucket ('' when it is missing or storage fails)."""
    if not settings.storage_configured:
        return ""
    try:
        return (s3 or _client(settings)).get_object(Bucket=settings.s3_bucket, Key=key)["Body"].read().decode("utf-8")
    except Exception:
        return ""


def remove(settings: Settings, key: str, s3=None) -> None:
    if settings.storage_configured:
        try:
            (s3 or _client(settings)).delete_object(Bucket=settings.s3_bucket, Key=key)
        except Exception:
            pass


def zip_run(run_dir: str, files: List[str]) -> str:
    """Bundle `files` (names inside run_dir) into <run folder>.zip inside run_dir; returns the zip's name."""
    name = os.path.basename(os.path.normpath(run_dir)) + ".zip"
    with zipfile.ZipFile(os.path.join(run_dir, name), "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for f in files:
            if os.path.exists(os.path.join(run_dir, f)):
                z.write(os.path.join(run_dir, f), arcname=f)
    return name


def upload_run(settings: Settings, run_dir: str, files: List[str],
               log: Callable[[str], None] = print, prefix: str = "") -> Dict[str, str]:
    """Upload `files` (names inside run_dir) under `prefix` (default reports/<run folder>/); returns {name: link}.
    Links are public URLs when S3_PUBLIC_URL is set, otherwise 7-day signed links. Never raises - the
    files are already saved locally, so a storage problem must not lose the run."""
    if not settings.storage_configured:
        log("[storage] object storage not configured (set S3_ENDPOINT, S3_BUCKET, S3_ACCESS_KEY_ID, "
            "S3_SECRET_ACCESS_KEY in .env) - skipping upload")
        return {}
    links = {}
    try:
        s3 = _client(settings)
        prefix = prefix or f"reports/{os.path.basename(os.path.normpath(run_dir))}"
        for name in files:
            path = os.path.join(run_dir, name)
            if not os.path.exists(path):
                continue
            key = f"{prefix}/{name}"
            mime = ("text/markdown; charset=utf-8" if name.endswith(".md") else "text/plain; charset=utf-8"
                    if name.endswith((".txt", ".srt")) else "application/zip"
                    if name.endswith(".zip") else mimetypes.guess_type(name)[0] or "application/octet-stream")
            if mime in ("text/html", "application/json"):
                mime += "; charset=utf-8"
            s3.upload_file(path, settings.s3_bucket, key, ExtraArgs={"ContentType": mime})
            links[name] = link_for(settings, key, s3)
        log(f"[storage] uploaded {len(links)} file(s) to {settings.s3_bucket}/{prefix}/")
    except Exception as exc:          # credentials, network, missing bucket, boto3 not installed ...
        log(f"[storage] FAILED: {type(exc).__name__}: {str(exc)[:200]}")
    return links


def prune_prefix(settings: Settings, prefix: str, days: int, log: Callable[[str], None] = print) -> None:
    """Delete objects under `prefix` older than `days` days (big video files would fill the free tier). Done by
    the run itself, because a storage token usually may not change the bucket's own clean-up rules. Never raises."""
    if not settings.storage_configured:
        return
    try:
        s3 = _client(settings)
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        old = [o["Key"] for page in s3.get_paginator("list_objects_v2").paginate(Bucket=settings.s3_bucket, Prefix=prefix)
               for o in page.get("Contents", []) if o["LastModified"] < cutoff]
        for i in range(0, len(old), 1000):
            s3.delete_objects(Bucket=settings.s3_bucket, Delete={"Objects": [{"Key": k} for k in old[i:i + 1000]]})
        if old:
            log(f"[storage] deleted {len(old)} file(s) older than {days} days under {prefix}")
    except Exception as exc:
        log(f"[storage] could not clean up {prefix}: {type(exc).__name__}: {str(exc)[:120]}")


def keep_latest_runs(settings: Settings, keep: int = 3, prefix: str = "videos/", keep_ext: Tuple[str, ...] = (".pdf",),
                     dry_run: bool = False, min_age_hours: float = 24.0, log: Callable[[str], None] = print) -> dict:
    """Weekly clean-up of the video folders (videos/<run>/...): the `keep` newest folders stay with everything in
    them, every older folder is emptied except its PDFs (the study notes are for sale and must stay). Nothing outside
    `prefix` is ever touched (reports/, voices/ and voice-farm/ are not this function's business), a folder newer than
    `min_age_hours` is never deleted (a run may still be uploading it), and a listing that fails or comes back empty
    deletes nothing. The newest folders are judged by the newest file in them. Returns what was (or, with dry_run,
    would be) kept and deleted."""
    result = {"kept": [], "emptied": [], "deleted_files": 0, "deleted_bytes": 0, "kept_pdfs": 0, "dry_run": dry_run}
    if not settings.storage_configured or not prefix.startswith("videos/") or keep < 1:
        log("[cleanup] storage not configured (or refused prefix/keep): nothing done")
        return result
    try:
        s3 = _client(settings)
        folders: Dict[str, list] = {}
        for page in s3.get_paginator("list_objects_v2").paginate(Bucket=settings.s3_bucket, Prefix=prefix):
            for o in page.get("Contents", []):
                parts = o["Key"][len(prefix):].split("/", 1)
                if len(parts) == 2 and parts[0] and parts[1]:        # videos/<run>/<file>; loose files are left alone
                    folders.setdefault(parts[0], []).append(o)
        if not folders:
            log("[cleanup] no video folders found: nothing done")
            return result
        newest = lambda name: max(o["LastModified"] for o in folders[name])          # noqa: E731
        order = sorted(folders, key=newest, reverse=True)
        result["kept"] = order[:keep]
        now = datetime.now(timezone.utc)
        doomed = []
        for name in order[keep:]:
            if (now - newest(name)).total_seconds() < min_age_hours * 3600:
                result["kept"].append(name)                            # too fresh to be sure it is finished
                continue
            files = folders[name]
            gone = [o for o in files if not o["Key"].lower().endswith(keep_ext)]
            result["kept_pdfs"] += len(files) - len(gone)
            if gone:
                result["emptied"].append(name)
            doomed += gone
        result["deleted_files"] = len(doomed)
        result["deleted_bytes"] = sum(o["Size"] for o in doomed)
        if not dry_run:
            for i in range(0, len(doomed), 1000):
                s3.delete_objects(Bucket=settings.s3_bucket,
                                  Delete={"Objects": [{"Key": o["Key"]} for o in doomed[i:i + 1000]], "Quiet": True})
        verb = "would delete" if dry_run else "deleted"
        log(f"[cleanup] kept the newest {len(result['kept'])} video folder(s) whole: {', '.join(result['kept'])}")
        log(f"[cleanup] {verb} {len(doomed)} file(s), {result['deleted_bytes'] / 1e9:.2f} GB, from {len(result['emptied'])} "
            f"older folder(s); {result['kept_pdfs']} PDF(s) kept")
    except Exception as exc:                      # never delete on a doubt
        log(f"[cleanup] FAILED, nothing more done: {type(exc).__name__}: {str(exc)[:200]}")
    return result
