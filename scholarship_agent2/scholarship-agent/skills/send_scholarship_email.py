"""
Skill: send_scholarship_email
Description: Send the student a formatted email listing their matched
             scholarships via Gmail SMTP. Requires EMAIL_SENDER and
             EMAIL_PASSWORD environment variables.
"""

import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart


def send_scholarship_email(
    student_name: str,
    student_email: str,
    scholarships: list[dict],
) -> str:
    """
    Email the student their matched scholarships.

    Args:
        student_name:  Student's display name (e.g. "Alex Tan")
        student_email: Recipient email address
        scholarships:  List of dicts with keys: name, amount, eligibility,
                       deadline, link

    Returns:
        Confirmation message string.

    Env vars required:
        EMAIL_SENDER   — your Gmail address
        EMAIL_PASSWORD — your Gmail App Password
                         (get one at https://myaccount.google.com/apppasswords)
    """
    sender = os.environ.get("EMAIL_SENDER")
    password = os.environ.get("EMAIL_PASSWORD")

    if not sender or not password:
        raise EnvironmentError(
            "EMAIL_SENDER and EMAIL_PASSWORD environment variables must be set."
        )

    # Build email body
    lines = [
        f"Hi {student_name},",
        "",
        "Here are your top scholarship matches:",
        "",
    ]
    for i, s in enumerate(scholarships, 1):
        lines += [
            f"{i}. {s.get('name', 'Unknown')} — {s.get('amount', 'N/A')}",
            f"   Eligibility : {s.get('eligibility', 'N/A')}",
            f"   Deadline    : {s.get('deadline', 'N/A')}",
            f"   Apply here  : {s.get('link', 'N/A')}",
            "",
        ]
    lines += ["Good luck with your applications!", "— Scholarship Agent"]
    body = "\n".join(lines)

    # Build and send message
    msg = MIMEMultipart()
    msg["From"] = sender
    msg["To"] = student_email
    msg["Subject"] = "🎓 Your Scholarship Matches"
    msg.attach(MIMEText(body, "plain"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
        smtp.login(sender, password)
        smtp.sendmail(sender, student_email, msg.as_string())

    result = f"Email sent to {student_email} with {len(scholarships)} scholarships."
    print(f"[send_scholarship_email] {result}")
    return result


if __name__ == "__main__":
    # Quick test (requires env vars)
    sample = [
        {
            "name": "Test Scholarship",
            "amount": "$1,000",
            "eligibility": "Malaysian CS students",
            "deadline": "Jan 2026",
            "link": "https://example.com",
        }
    ]
    print(send_scholarship_email("Alex Tan", "alex@example.com", sample))
