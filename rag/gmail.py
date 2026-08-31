"""Minimal Gmail search via IMAP + App Password (personal use)."""
from __future__ import annotations

import email
import imaplib
import re
from email.header import decode_header, make_header
from email.message import Message

_TAG_RE = re.compile(r"<[^>]+>")


def _decode(value: str | None) -> str:
    """Decode a possibly RFC 2047-encoded header value."""
    if not value:
        return ""
    return str(make_header(decode_header(value)))


def _payload_text(part: Message) -> str:
    """Return a MIME part's text, decoding bytes when needed."""
    charset = part.get_content_charset() or "utf-8"
    payload = part.get_payload(decode=True)
    if payload is None:
        return ""
    if isinstance(payload, bytes):
        return payload.decode(charset, errors="replace")
    return str(payload)


def _extract_text(msg: Message) -> str:
    """Return the plain-text body of a MIME message, falling back to stripped HTML."""
    plain_parts: list[str] = []
    html_parts: list[str] = []

    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == "text/plain":
                plain_parts.append(_payload_text(part))
            elif part.get_content_type() == "text/html":
                html_parts.append(_payload_text(part))
    else:
        text = _payload_text(msg)
        if msg.get_content_type() == "text/plain":
            plain_parts.append(text)
        elif msg.get_content_type() == "text/html":
            html_parts.append(text)

    if plain_parts:
        return "\n".join(text for text in plain_parts if text).strip()
    if html_parts:
        return _TAG_RE.sub(" ", "\n".join(text for text in html_parts if text)).strip()
    return ""


class GmailSearch:
    """Search a personal Gmail inbox over IMAP using an App Password."""

    def __init__(self, address: str, app_password: str) -> None:
        if not address.strip() or not app_password.strip():
            raise RuntimeError("Gmail address and App Password are both required.")
        self._address = address.strip()
        self._app_password = app_password.strip()

    def search(self, query: str, max_results: int = 5) -> list[dict[str, str]]:
        """Return up to ``max_results`` newest matching emails.

        ``query`` uses Gmail's native search syntax (e.g. ``from:boss is:unread``)
        through the IMAP ``X-GM-RAW`` extension.
        """
        if not query.strip():
            return []

        imap = imaplib.IMAP4_SSL("imap.gmail.com")
        try:
            imap.login(self._address, self._app_password)
            imap.select("INBOX", readonly=True)

            _, data = imap.search(None, "X-GM-RAW", f'"{query}"')
            message_ids = data[0].split()
            if not message_ids:
                return []

            results: list[dict[str, str]] = []
            for message_id in reversed(message_ids[-max_results:]):
                _, fetched = imap.fetch(message_id, "(RFC822)")
                msg = email.message_from_bytes(fetched[0][1])
                results.append(
                    {
                        "from": _decode(msg.get("From")),
                        "subject": _decode(msg.get("Subject")),
                        "date": _decode(msg.get("Date")),
                        "text": _extract_text(msg)[:2000],
                    }
                )
            return results
        finally:
            try:
                imap.logout()
            except Exception:
                pass
