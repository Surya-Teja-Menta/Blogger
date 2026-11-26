"""The one-time YouTube sign-in, on your own PC: opens the browser, you approve, and a new refresh token is written next
to client_secret.json (outside the repository). Then store it as the GitHub secret YT_REFRESH_TOKEN yourself.

    python tools/yt_auth.py C:/Users/<you>/Documents/adyora"""
import base64
import hashlib
import json
import secrets
import sys
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlparse

import requests

SCOPES = ["https://www.googleapis.com/auth/youtube.upload", "https://www.googleapis.com/auth/youtube.force-ssl",
          "https://www.googleapis.com/auth/yt-analytics.readonly"]


def main() -> None:
    folder = Path(sys.argv[1])
    raw = json.loads((folder / "client_secret.json").read_text(encoding="utf-8"))
    app = raw.get("installed") or raw.get("web")
    verifier, state, got = secrets.token_urlsafe(64), secrets.token_urlsafe(16), {}

    class Back(BaseHTTPRequestHandler):
        def do_GET(self):
            q = parse_qs(urlparse(self.path).query)
            if q.get("state") == [state] and "code" in q:
                got["code"] = q["code"][0]
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"Done. You can close this tab.")

        def log_message(self, *a):
            pass

    server = HTTPServer(("127.0.0.1", 0), Back)
    redirect = f"http://127.0.0.1:{server.server_port}"
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip("=")
    url = "https://accounts.google.com/o/oauth2/v2/auth?" + urlencode({
        "client_id": app["client_id"], "redirect_uri": redirect, "response_type": "code", "scope": " ".join(SCOPES),
        "access_type": "offline", "prompt": "consent", "state": state, "code_challenge": challenge,
        "code_challenge_method": "S256"})
    print("Opening the browser. If it does not open, visit:\n" + url)
    webbrowser.open(url)
    while "code" not in got:
        server.handle_request()
    r = requests.post("https://oauth2.googleapis.com/token", data={
        "client_id": app["client_id"], "client_secret": app["client_secret"], "code": got["code"],
        "code_verifier": verifier, "grant_type": "authorization_code", "redirect_uri": redirect}, timeout=30)
    data = r.json()
    if "refresh_token" not in data:
        sys.exit(f"no refresh token came back ({data.get('error', r.status_code)})")
    (folder / "token.json").write_text(json.dumps({"refresh_token": data["refresh_token"], "scope": data.get("scope")}),
                                       encoding="utf-8")
    print(f"Saved to {folder / 'token.json'}. Permissions: {data.get('scope')}")


if __name__ == "__main__":
    main()
