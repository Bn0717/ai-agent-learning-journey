import json
import smtplib
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import Any
from claude_agent_sdk import tool
from config import settings, REPORTS_DIR


def _build_content(student_name: str, scholarships: list[dict]) -> tuple[str, str]:
    """Return (plain_text, html) built entirely from structured data — no LLM prose."""
    date_str = datetime.now().strftime("%Y-%m-%d")

    plain_lines = [
        f"Dear {student_name},",
        "",
        "Here are your top scholarship matches:",
        "",
    ]
    for s in scholarships:
        plain_lines += [
            f"#{s['rank']} {s['name']}",
            f"  Provider : {s.get('provider', '')}",
            f"  Award    : ${s.get('amount_usd', 0):,}",
            f"  Deadline : {s.get('deadline', 'N/A')}",
            f"  • {s.get('justification', '')}",
            "",
        ]
    plain_lines += ["Good luck with your applications!", "", "— Scholarship AI Agent"]
    plain = "\n".join(plain_lines)

    cards = ""
    for s in scholarships:
        cards += f"""
<div style="border-left:4px solid #1a73e8;padding:12px 16px;margin:16px 0;background:#f8f9fa;border-radius:0 6px 6px 0">
  <strong style="font-size:15px">#{s['rank']} {s['name']}</strong><br>
  <span style="color:#555">{s.get('provider','')}</span><br>
  <span>💰 <b>${s.get('amount_usd',0):,}</b> &nbsp;|&nbsp; 📅 Deadline: <b>{s.get('deadline','N/A')}</b></span>
  <p style="margin:8px 0 0;color:#333">• {s.get('justification','')}</p>
</div>"""

    html = f"""<!DOCTYPE html>
<html><body style="font-family:Arial,sans-serif;max-width:660px;margin:auto;padding:24px;color:#222">
<h2 style="color:#1a73e8;margin-bottom:4px">🎓 Your Scholarship Matches</h2>
<p style="color:#888;margin-top:0;font-size:13px">{date_str}</p>
<p>Dear <strong>{student_name}</strong>,</p>
<p>Here are your top scholarship matches based on your academic profile:</p>
{cards}
<p style="margin-top:24px">Good luck with your applications!</p>
<hr style="border:none;border-top:1px solid #eee;margin:24px 0"/>
<p style="color:#aaa;font-size:12px">Sent by Scholarship AI Agent</p>
</body></html>"""

    return plain, html


def _smtp_send(to_email: str, subject: str, plain: str, html: str) -> None:
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = settings.email_from or settings.smtp_user
    msg["To"] = to_email
    msg.attach(MIMEText(plain, "plain"))
    msg.attach(MIMEText(html, "html"))
    with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as srv:
        srv.starttls()
        srv.login(settings.smtp_user, settings.smtp_password)
        srv.send_message(msg)


def _log_mock(to_email: str, subject: str, plain: str) -> str:
    log_path = REPORTS_DIR / "email_log.txt"
    with log_path.open("a", encoding="utf-8") as f:
        f.write(f"\n{'='*60}\n[MOCK {datetime.now().isoformat()}]\nTo: {to_email}\nSubject: {subject}\n\n{plain}\n")
    return str(log_path)


@tool(
    "send_email",
    "Send the scholarship report to the student. Pass the report_file path returned by save_report.",
    {
        "type": "object",
        "properties": {
            "to_email":     {"type": "string", "description": "Student's email address."},
            "student_name": {"type": "string", "description": "Student's full name."},
            "report_file":  {"type": "string", "description": "Absolute path to the JSON report from save_report."},
        },
        "required": ["to_email", "student_name", "report_file"],
    },
)
async def send_email(args: dict[str, Any]) -> dict[str, Any]:
    to_email     = args["to_email"]
    student_name = args.get("student_name", "Student")
    report_file  = args.get("report_file", "")

    # Load scholarships from the saved report — no LLM-generated body needed
    try:
        report = json.loads(Path(report_file).read_text(encoding="utf-8"))
        scholarships = report.get("ranked_scholarships", [])
    except Exception as exc:
        return {"content": [{"type": "text", "text": json.dumps({"success": False, "error": f"Could not load report: {exc}"})}]}

    subject = f"Your Scholarship Recommendations — {datetime.now().strftime('%Y-%m-%d')}"
    plain, html = _build_content(student_name, scholarships)

    if settings.smtp_configured:
        try:
            _smtp_send(to_email, subject, plain, html)
            return {"content": [{"type": "text", "text": json.dumps({"success": True, "mode": "smtp", "sent_to": to_email})}]}
        except Exception as exc:
            log = _log_mock(to_email, subject, plain)
            return {"content": [{"type": "text", "text": json.dumps({"success": False, "mode": "mock_fallback", "error": str(exc), "logged_to": log})}]}

    log = _log_mock(to_email, subject, plain)
    return {"content": [{"type": "text", "text": json.dumps({"success": True, "mode": "mock", "logged_to": log, "sent_to": to_email})}]}
