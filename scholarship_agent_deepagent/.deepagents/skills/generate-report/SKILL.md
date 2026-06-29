---
name: generate-report
description: Write a personalised scholarship report as a markdown file on disk
---

# Skill: generate-report

Write the final scholarship report to `scholarship_report.md`.

## Report Structure (4 sections)

### 1 — Your Profile Summary (50 words max)
Summarise the student's key strengths relevant to scholarship applications:
GPA, field, standout skills, awards, and any notable experience.

### 2 — Top Scholarship Matches
For each of the top 5 ranked scholarships include:
- Award amount and deadline
- Source link
- Why it fits the student (1–2 sentences)
- Gaps to address before applying
- Recommended improvements

### 3 — Application Strategy
- Suggested application order (easiest win first)
- Shared requirements across multiple scholarships (e.g. common essay themes)
- Estimated total effort (low / medium / high)

### 4 — Next Steps
Numbered action list with deadlines. Be specific and actionable.

## Tone

Encouraging, specific, and actionable. Avoid generic advice.

## How to Write the File

Use the `bash` tool to write the report:
```bash
cat > scholarship_report.md << 'EOF'
<report content here>
EOF
```
