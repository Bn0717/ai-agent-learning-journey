import smtplib
import os
from email.mime.text import MIMEText
from dotenv import load_dotenv

load_dotenv()

def send_email(to: str, subject: str, content: str) -> str:
    try:
        sender_email = os.getenv("SENDER_EMAIL", "your_email@gmail.com")
        sender_password = os.getenv("SENDER_PASSWORD")
        
        if not sender_password:
            return "Error: SENDER_PASSWORD not configured in environment (.env file)"
        
        msg = MIMEText(content)
        msg["Subject"] = subject
        msg["From"] = sender_email
        msg["To"] = to
        
        # Actually send the email
        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls()
            server.login(sender_email, sender_password)
            server.send_message(msg)
        
        return f"Email sent to {to}"
    except smtplib.SMTPAuthenticationError:
        return "Error: Invalid email credentials in .env file"
    except smtplib.SMTPException as e:
        return f"Error sending email: {str(e)}"
    except Exception as e:
        return f"Failed to send email: {str(e)}"


send_email_tool = {
    "name": "send_email",
    "description": "Send email to user with scholarship summary",
    "input_schema": {
        "type": "object",
        "properties": {
            "to": {"type": "string"},
            "subject": {"type": "string"},
            "content": {"type": "string"}
        },
        "required": ["to", "subject", "content"]
    },
    "function": send_email
}