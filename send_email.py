#!/usr/bin/env python3
"""Email output/streams.json via SMTP. Credentials come from environment variables."""
import json, os, smtplib, sys
from email.message import EmailMessage
from pathlib import Path


def build_body(episodes):
    if not episodes:
        return "No matching WWOZ episodes were found in the last 7 days.\n"
    lines = [f"{len(episodes)} WWOZ episodes from the last 7 days:\n"]
    for e in episodes:
        lines.append(f"{e['aired']}  {e['show']}\n{e['url']}\n")
    return "\n".join(lines)


def main():
    episodes = json.loads(Path("output/streams.json").read_text())
    body = build_body(episodes)

    required = ["SMTP_SERVER", "SMTP_USERNAME", "SMTP_PASSWORD", "MAIL_TO"]
    missing = [k for k in required if not os.environ.get(k)]
    if missing:
        print(f"Missing secrets: {', '.join(missing)}. Printing instead of sending:\n")
        print(body)
        sys.exit(1)

    msg = EmailMessage()
    msg["Subject"] = f"WWOZ archive: {len(episodes)} episodes this week"
    msg["From"] = os.environ["SMTP_USERNAME"]
    msg["To"] = os.environ["MAIL_TO"]
    msg.set_content(body)

    port = int(os.environ.get("SMTP_PORT", "465"))
    with smtplib.SMTP_SSL(os.environ["SMTP_SERVER"], port, timeout=30) as smtp:
        smtp.login(os.environ["SMTP_USERNAME"], os.environ["SMTP_PASSWORD"])
        smtp.send_message(msg)
    print(f"Sent {len(episodes)} episodes to {msg['To']}.")


if __name__ == "__main__":
    main()
