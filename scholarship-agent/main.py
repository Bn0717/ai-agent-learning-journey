import os
import pathlib
import smtplib
import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from dotenv import load_dotenv
from google import genai
from google.genai import types
import markdown
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import uvicorn

load_dotenv()

REPORTS_DIR = pathlib.Path('reports')
CLAUDE_MD = pathlib.Path('CLAUDE.md')

app = FastAPI(title='Scholarship Agent')


class ResearchRequest(BaseModel):
    query: str


@app.get('/health')
def health():
    return {'status': 'ok'}


@app.post('/research')
def research(req: ResearchRequest):
    query = req.query.strip()
    if not query:
        raise HTTPException(status_code=400, detail='query must not be empty')

    report = run_agent(query)
    if not report:
        raise HTTPException(status_code=500, detail='Agent returned no report')

    REPORTS_DIR.mkdir(exist_ok=True)
    (REPORTS_DIR / 'report.md').write_text(report, encoding='utf-8')

    email_status = send_email(report, query)

    return {'status': email_status, 'report': report}


def run_agent(query: str) -> str | None:
    api_key = os.getenv('GEMINI_API_KEY')
    if not api_key:
        raise HTTPException(status_code=500, detail='GEMINI_API_KEY not set')

    client = genai.Client(api_key=api_key)
    system_instruction = CLAUDE_MD.read_text(encoding='utf-8')

    chat = client.chats.create(
        model='gemini-2.5-flash-lite',
        config=types.GenerateContentConfig(
            system_instruction=system_instruction,
            tools=[types.Tool(google_search=types.GoogleSearch())],
        ),
    )

    message = query
    while True:
        response = chat.send_message(message)
        text = response.text
        candidate = response.candidates[0] if response.candidates else None
        finish_reason = (
            getattr(candidate.finish_reason, 'name', str(candidate.finish_reason))
            if candidate else 'UNKNOWN'
        )

        if text and finish_reason == 'STOP':
            return text
        elif text and finish_reason == 'MAX_TOKENS':
            message = 'Continue from where you stopped.'
        elif text:
            return text
        else:
            return None


def send_email(report: str, query: str) -> str:
    gmail_user = os.getenv('GMAIL_USER')
    gmail_password = os.getenv('GMAIL_APP_PASSWORD')
    recipient = os.getenv('RECIPIENT_EMAIL')

    if not all([gmail_user, gmail_password, recipient]):
        return 'email_skipped'

    date_str = datetime.date.today().strftime('%Y-%m-%d')
    subject = f'Scholarship Report — {query} — {date_str}'
    html_body = markdown.markdown(report, extensions=['tables', 'fenced_code'])

    msg = MIMEMultipart('alternative')
    msg['Subject'] = subject
    msg['From'] = gmail_user
    msg['To'] = recipient
    msg.attach(MIMEText(report, 'plain', 'utf-8'))
    msg.attach(MIMEText(html_body, 'html', 'utf-8'))

    try:
        with smtplib.SMTP('smtp.gmail.com', 587, timeout=15) as smtp:
            smtp.ehlo()
            smtp.starttls()
            smtp.ehlo()
            smtp.login(gmail_user, gmail_password)
            smtp.sendmail(gmail_user, recipient, msg.as_string())
        return 'sent'
    except smtplib.SMTPAuthenticationError:
        return 'email_auth_failed'
    except (TimeoutError, ConnectionRefusedError, OSError):
        return 'email_connection_failed'


if __name__ == '__main__':
    uvicorn.run('main:app', host='0.0.0.0', port=8080, reload=True)
