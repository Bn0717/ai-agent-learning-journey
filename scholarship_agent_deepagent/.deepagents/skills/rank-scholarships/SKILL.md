---
name: rank-scholarships
description: Rank assessed scholarships by fit score and return the top 5
---

# Skill: rank-scholarships

Produce a final ranked shortlist from the assessed scholarships.

## Steps

1. **Remove ineligible** — discard all scholarships where `fit_score = 0`.

2. **Sort descending** — order remaining scholarships by `fit_score` (highest first).

3. **Keep top 5** — retain only the top 5 results.

4. **Tiebreaker** — for equal `fit_score`:
   - Prefer the closer deadline first.
   - Then prefer the higher award amount.

## Output

```
rank | name | fit_score | deadline | amount | reason
```

One line per scholarship. `reason` is a single sentence explaining why it ranked here.
