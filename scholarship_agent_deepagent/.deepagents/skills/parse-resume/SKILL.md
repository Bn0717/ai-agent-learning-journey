---
name: parse-resume
description: Extract raw text and structured profile from a student's PDF resume
---

# Skill: parse-resume

Extract text and a structured student profile from a PDF resume.

## Steps

1. Run the parser script via `bash`:
   ```bash
   python .deepagents/skills/parse-resume/skill.py --file <resume_path>
   ```
   Returns JSON: `{"text": "...", "pages": N, "char_count": N, "file": "..."}`

2. From the extracted text identify:
   - **Name** — full name
   - **Education level** — SPM / undergraduate / postgraduate
   - **GPA / CGPA** — numeric value
   - **Field of study** — e.g. Computer Science, Engineering, Business
   - **Technical skills** — programming languages, tools, frameworks
   - **Projects** — title and one-line description
   - **Experience** — internships, jobs, volunteer work
   - **Awards & achievements**
   - **Nationality** — if stated

## Output

Return the structured student profile in plain text, ready for the assess-fit skill.
