---
name: send-email
description: Email the scholarship report to the student via Gmail SMTP
---

# Skill: send-email

Send the generated scholarship report to the student's email address.

## How to Use

Run the send-email script via `bash`:
```bash
python .deepagents/skills/send-email/skill.py --to <recipient_email> --report-file scholarship_report.md
```

## Prerequisites

- `EMAIL_SENDER` and `EMAIL_PASSWORD` must be set in `.env`
- `scholarship_report.md` must exist (run generate-report first)
- Gmail account must have an App Password configured (not the account password)

## Output

Returns JSON on success:
```json
{"status": "sent", "recipient": "...", "report_file": "...", "subject": "..."}
```

Returns JSON with `"error"` key on failure — check the error message before retrying.
