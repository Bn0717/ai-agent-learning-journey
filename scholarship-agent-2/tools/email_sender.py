import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import markdown as md


def send_email(recipient_email: str, subject: str, body: str) -> dict:
    """Send a scholarship report or essay draft via Gmail SMTP."""
    gmail_user     = os.getenv('GMAIL_USER')
    gmail_password = os.getenv('GMAIL_APP_PASSWORD')

    if not all([gmail_user, gmail_password]):
        return {"sent": False, "reason": "GMAIL_USER or GMAIL_APP_PASSWORD not configured"}

    msg = MIMEMultipart('alternative')
    msg['Subject'] = subject
    msg['From']    = gmail_user
    msg['To']      = recipient_email
    msg.attach(MIMEText(body, 'plain', 'utf-8'))
    msg.attach(MIMEText(md.markdown(body, extensions=['tables', 'fenced_code']), 'html', 'utf-8'))

    try:
        with smtplib.SMTP('smtp.gmail.com', 587, timeout=15) as smtp:
            smtp.ehlo()
            smtp.starttls()
            smtp.ehlo()
            smtp.login(gmail_user, gmail_password)
            smtp.sendmail(gmail_user, recipient_email, msg.as_string())
        return {"sent": True, "recipient": recipient_email}
    except smtplib.SMTPAuthenticationError:
        return {"sent": False, "reason": "Authentication failed — check Gmail App Password"}
    except (TimeoutError, ConnectionRefusedError, OSError) as e:
        return {"sent": False, "reason": f"SMTP connection failed: {e}"}
