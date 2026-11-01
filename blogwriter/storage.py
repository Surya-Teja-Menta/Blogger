"""Upload a finished run to S3-compatible object storage (Cloudflare R2, Backblaze B2, MinIO, AWS S3)."""
import mimetypes
import os
from typing import Callable, Dict, List

from .config import Settings

SIGNED_LINK_SECONDS = 7 * 24 * 3600      # the longest a SigV4 signed link may live


def _client(settings: Settings):
    import boto3
    from botocore.config import Config
    return boto3.client("s3", endpoint_url=settings.s3_endpoint, region_name=settings.s3_region,
                        aws_access_key_id=settings.s3_access_key, aws_secret_access_key=settings.s3_secret_key,
                        config=Config(signature_version="s3v4", retries={"max_attempts": 3}))


def upload_run(settings: Settings, run_dir: str, files: List[str],
               log: Callable[[str], None] = print) -> Dict[str, str]:
    """Upload `files` (names inside run_dir) under reports/<run folder>/; returns {name: link}.
    Links are public URLs when S3_PUBLIC_URL is set, otherwise 7-day signed links. Never raises - the
    files are already saved locally, so a storage problem must not lose the run."""
    if not settings.storage_configured:
        log("[storage] object storage not configured (set S3_ENDPOINT, S3_BUCKET, S3_ACCESS_KEY_ID, "
            "S3_SECRET_ACCESS_KEY in .env) - skipping upload")
        return {}
    links = {}
    try:
        s3 = _client(settings)
        prefix = f"reports/{os.path.basename(os.path.normpath(run_dir))}"
        for name in files:
            path = os.path.join(run_dir, name)
            if not os.path.exists(path):
                continue
            key = f"{prefix}/{name}"
            mime = "text/markdown; charset=utf-8" if name.endswith(".md") else (
                mimetypes.guess_type(name)[0] or "application/octet-stream")
            if mime in ("text/html", "application/json"):
                mime += "; charset=utf-8"
            s3.upload_file(path, settings.s3_bucket, key, ExtraArgs={"ContentType": mime})
            links[name] = (f"{settings.s3_public_url}/{key}" if settings.s3_public_url else
                           s3.generate_presigned_url("get_object", Params={"Bucket": settings.s3_bucket, "Key": key},
                                                     ExpiresIn=SIGNED_LINK_SECONDS))
        log(f"[storage] uploaded {len(links)} file(s) to {settings.s3_bucket}/{prefix}/")
    except Exception as exc:          # credentials, network, missing bucket, boto3 not installed ...
        log(f"[storage] FAILED: {type(exc).__name__}: {str(exc)[:200]}")
    return links
