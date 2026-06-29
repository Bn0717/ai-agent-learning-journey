---
name: assess-fit
description: Score a student's fit for a scholarship and identify strengths, gaps, and improvements
---

# Skill: assess-fit

Compare a student profile against a scholarship summary and produce a fit assessment.

## Steps

### 1 — Eligibility check (hard rules)

Check each requirement strictly. If the student fails any hard requirement (GPA minimum,
nationality, education level, field of study), set `fit_score = 0` and stop.

### 2 — Fit score (1–10)

Score based on:
- GPA / CGPA match to the scholarship's minimum and ideal range
- Field of study alignment
- Relevant skills, projects, or experience
- Award amount relative to student's need / ambition

### 3 — Strengths (max 2 bullets, 10 words each)

What makes the student a strong candidate.

### 4 — Gaps (max 2 bullets, 10 words each)

Where the student falls short of the scholarship's ideal.

### 5 — Improvements (max 2 bullets, 10 words each)

Actionable steps the student can take before applying.

## Output per Scholarship

```
scholarship: <name>
fit_score: <0–10>
strengths:
  - ...
gaps:
  - ...
improvements:
  - ...
```
