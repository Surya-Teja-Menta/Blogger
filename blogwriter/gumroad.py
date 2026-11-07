"""List a finished run on Gumroad: create the product, attach the report file, optionally publish it."""
import math
import os
import re
from typing import Callable, Dict

import markdown
import requests

from .config import Settings

API = "https://api.gumroad.com/v2"
TIMEOUT = 60


class GumroadError(RuntimeError):
    pass


def _json(resp: requests.Response) -> dict:
    try:
        data = resp.json()
    except ValueError:
        raise GumroadError(f"HTTP {resp.status_code}: {resp.text[:150]}")
    if resp.status_code >= 400 or data.get("success") is False or data.get("error"):
        raise GumroadError(f"HTTP {resp.status_code}: {str(data.get('message') or data.get('error'))[:200]}")
    return data


def _upload(token: str, path: str) -> str:
    """Presign -> upload the parts to S3 -> complete. Returns the file_url to attach to a product."""
    size = os.path.getsize(path)
    pre = _json(requests.post(f"{API}/files/presign", timeout=TIMEOUT, data={
        "access_token": token, "filename": os.path.basename(path), "file_size": size}))
    n = len(pre["parts"])
    chunk = math.ceil(size / n)
    parts = []
    with open(path, "rb") as f:
        for p in pre["parts"]:
            r = requests.put(p["presigned_url"], data=f.read(chunk), timeout=TIMEOUT * 3)
            r.raise_for_status()
            parts.append({"part_number": p["part_number"], "etag": r.headers["ETag"]})
    done = _json(requests.post(f"{API}/files/complete", timeout=TIMEOUT, json={
        "access_token": token, "upload_id": pre["upload_id"], "key": pre["key"], "parts": parts}))
    return done.get("file_url") or pre["file_url"]


def parse_price(text: str) -> tuple:
    """ "99 INR" -> (99.0, "inr"); "3.90 usd" -> (3.9, "usd"); a bare number is in rupees."""
    m = re.match(r"\s*([\d.]+)\s*([A-Za-z]{3})?\s*$", str(text or ""))
    if not m:
        return 99.0, "inr"
    return float(m.group(1)), (m.group(2) or "inr").lower()


def convert(amount: float, frm: str, to: str) -> float:
    """amount in currency `frm` expressed in `to`, at today's reference rate (free ECB rates, no key)."""
    r = requests.get("https://api.frankfurter.app/latest", params={"amount": amount, "from": frm.upper(),
                                                                    "to": to.upper()}, timeout=TIMEOUT)
    r.raise_for_status()
    return float(r.json()["rates"][to.upper()])


def list_product(settings: Settings, title: str, description_md: str, file_path: str,
                 log: Callable[[str], None] = print) -> Dict[str, object]:
    """Returns {"url", "id", "published"}, or {} when not configured or on failure. Never raises - the files are
    already saved and emailed, so a Gumroad problem must not lose the run.
    The API publishes a new product at once, so it is disabled again straight away; it only goes live again when
    GUMROAD_PUBLISH is set. Otherwise it stays a draft for you to review in the Gumroad dashboard."""
    if not settings.gumroad_token:
        log("[gumroad] GUMROAD_ACCESS_TOKEN not set - skipping")
        return {}
    token, product_id = settings.gumroad_token, ""
    amount, currency = parse_price(settings.gumroad_price)
    try:
        made = _json(requests.post(f"{API}/products", timeout=TIMEOUT, data={
            "access_token": token, "name": title[:120], "price": round(amount * 100),
            "price_currency_type": currency}))["product"]
        product_id = made["id"]
        url = f"{API}/products/{requests.utils.quote(product_id, safe='')}"
        _json(requests.put(f"{url}/disable", timeout=TIMEOUT, data={"access_token": token}))
        # the price is checked as Gumroad stored it: a product made in the account's own currency instead gets the
        # same price converted at today's rate, so "99 INR" can never become 99 dollars
        got = str(made.get("currency") or currency).lower()
        if got != currency:
            cents = round(convert(amount, currency, got) * 100)
            _json(requests.put(url, timeout=TIMEOUT, data={"access_token": token, "price": cents}))
            log(f"[gumroad] the account sells in {got.upper()}: {amount:g} {currency.upper()} set as "
                f"{cents / 100:.2f} {got.upper()}")
        _json(requests.put(url, timeout=TIMEOUT, json={
            "access_token": token, "description": markdown.markdown(description_md),
            "files": [{"url": _upload(token, file_path)}]}))
        if settings.gumroad_publish:
            _json(requests.put(f"{url}/enable", timeout=TIMEOUT, data={"access_token": token}))
        log(f"[gumroad] {'published' if settings.gumroad_publish else 'draft created'}: {made['short_url']}")
        return {"url": made["short_url"], "id": product_id, "published": settings.gumroad_publish}
    except Exception as exc:          # network, bad token, rejected file ...
        log(f"[gumroad] FAILED: {type(exc).__name__}: {str(exc)[:200]}")
        if product_id:                # do not leave a half-made product behind
            try:
                requests.delete(f"{API}/products/{requests.utils.quote(product_id, safe='')}", timeout=TIMEOUT,
                                data={"access_token": token})
            except requests.RequestException:
                pass
        return {}
