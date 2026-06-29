---
name: summarise-scholarship
description: Summarise a raw scholarship page into a compact structured format
---

# Skill: summarise-scholarship

Convert raw scholarship page content into a compact structured summary.

## Fields to Extract

| Field        | Description                              |
|--------------|------------------------------------------|
| Name         | Full scholarship name                    |
| Provider     | Organisation offering the scholarship    |
| Amount       | Monetary value or coverage               |
| Deadline     | Application closing date                 |
| Level        | SPM / Diploma / Degree / Postgraduate    |
| Location     | Study location (local / overseas)        |
| Type         | Full / Partial / Loan / Bond             |
| Courses      | Eligible fields of study                 |
| Requirements | GPA, nationality, age, other criteria    |
| Bond         | Bond period and conditions if any        |
| Link         | Source URL                               |

## Rules

- Keep each field under 30 words.
- Only include fields that are explicitly stated on the page.
- Do not infer or assume values that are not present.

## Output

Return one structured summary block per scholarship, ready for the assess-fit skill.
