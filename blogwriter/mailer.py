"""Step 5: email the finished documentary report, article and blog over SMTP."""
import mimetypes
import os
import smtplib
import ssl
from email.message import EmailMessage
from typing import Callable, List

from .config import Settings


def build_message(settings: Settings, subject: str, body: str, attachments: List[str]) -> EmailMessage:
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = settings.mail_from or settings.smtp_user
    msg["To"] = ", ".join(settings.mail_to)
    msg.set_content(body)
    for path in attachments:
        if not os.path.exists(path):
            continue
        mime, _ = mimetypes.guess_type(path)
        maintype, subtype = (mime or "application/octet-stream").split("/", 1)
        if path.endswith(".md"):
            maintype, subtype = "text", "markdown"
        with open(path, "rb") as f:
            msg.add_attachment(f.read(), maintype=maintype, subtype=subtype, filename=os.path.basename(path))
    return msg


def send_email(settings: Settings, subject: str, body: str, attachments: List[str],
               log: Callable[[str], None] = print) -> bool:
    """Send the message; returns True on success. Never raises - the files are already saved on disk,
    so a mail problem must not throw the finished work away."""
    if not settings.email_configured:
        log("[mail] SMTP not configured (set SMTP_HOST, MAIL_TO, SMTP_USER/SMTP_PASSWORD in .env) - skipping email")
        return False
    try:
        msg = build_message(settings, subject, body, attachments)
        ctx = ssl.create_default_context()
        if settings.smtp_port == 465:
            server = smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port, timeout=60, context=ctx)
        else:
            server = smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=60)
        with server:
            server.ehlo()
            if settings.smtp_port != 465 and server.has_extn("starttls"):    # encrypt whenever the server offers it
                server.starttls(context=ctx)
                server.ehlo()
            if settings.smtp_user and settings.smtp_password:
                server.login(settings.smtp_user, settings.smtp_password)
            server.send_message(msg)
        # the count, not the addresses: the Actions logs of a public repository are public
        log(f"[mail] sent to {len(settings.mail_to)} recipient(s) with {len(list(msg.iter_attachments()))} attachment(s)")
        return True
    except Exception as exc:      # auth errors, network, bad address ...
        log(f"[mail] FAILED: {type(exc).__name__}: {str(exc)[:200]}")
        return False
