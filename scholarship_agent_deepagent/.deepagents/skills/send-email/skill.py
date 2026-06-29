"""Send the scholarship report to the student via Gmail SMTP."""
import argparse
import json
import os
import smtplib
import ssl
import sys
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

from dotenv import load_dotenv

# .deepagents/skills/send-email/skill.py → 4 levels up = project root
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
load_dotenv(PROJECT_ROOT / ".env")


def main():
    parser = argparse.ArgumentParser(description="Send scholarship report email")
    parser.add_argument("--to", required=True, help="Recipient email address")
    parser.add_argument("--report-file", required=True, help="Path to the markdown report file")
    args = parser.parse_args()

    sender = os.getenv("EMAIL_SENDER")
    password = os.getenv("EMAIL_PASSWORD")
    if not sender or not password:
        print(json.dumps({"error": "EMAIL_SENDER or EMAIL_PASSWORD not set in .env"}))
        sys.exit(1)

    report_path = Path(args.report_file)
    if not report_path.is_absolute():
        report_path = PROJECT_ROOT / report_path
    if not report_path.exists():
        print(json.dumps({"error": f"Report file not found: {report_path}"}))
        sys.exit(1)

    body = report_path.read_text(encoding="utf-8")

    msg = MIMEMultipart("alternative")
    msg["Subject"] = "Your Personalised Scholarship Report"
    msg["From"] = sender
    msg["To"] = args.to
    msg.attach(MIMEText(body, "plain", "utf-8"))

    context = ssl.create_default_context()
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=context) as server:
            server.login(sender, password)
            server.sendmail(sender, args.to, msg.as_string())
    except Exception as e:
        print(json.dumps({"error": f"Failed to send email: {e}"}))
        sys.exit(1)

    print(json.dumps({
        "status": "sent",
        "recipient": args.to,
        "report_file": str(report_path),
        "subject": msg["Subject"],
    }, indent=2))


if __name__ == "__main__":
    main()
