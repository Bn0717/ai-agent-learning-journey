"""
Skill: web_search_scholarships
Description: Search the web for real, currently open scholarships matching
             a student profile. Returns a list with name, amount, eligibility,
             deadline, and link for each scholarship found.
"""

import json
import urllib.request
import urllib.parse


def web_search_scholarships(
    field: str,
    nationality: str,
    gpa: str,
    year: str,
    background: str,
) -> list[dict]:
    """
    Search for scholarships matching the student profile.

    Args:
        field:       Field of study (e.g. "Computer Science")
        nationality: Student nationality (e.g. "Malaysian")
        gpa:         GPA string (e.g. "3.7")
        year:        Academic year (e.g. "Undergraduate sophomore")
        background:  Extra context (e.g. "First-generation, financial need")

    Returns:
        List of dicts: [{name, amount, eligibility, deadline, link}, ...]
    """

    # Build search queries
    queries = [
        f"{field} scholarships for {nationality} students {year}",
        f"scholarships {background} {gpa} GPA {field}",
        f"international scholarships {nationality} {field} undergraduate",
    ]

    print(f"[web_search_scholarships] Searching for: {queries[0]}")

    # --- Real implementation would call WebSearch + WebFetch here ---
    # In the Agent SDK, this skill runs INSIDE the agent loop, so the
    # agent itself calls WebSearch and WebFetch tools to execute these
    # queries and extract results. The queries above are passed as
    # instructions the agent follows using its built-in tools.

    # Placeholder return so the skill is importable and testable locally
    return [
        {
            "name": "Example Scholarship (replace with real WebSearch results)",
            "amount": "$5,000",
            "eligibility": f"{nationality} students in {field} with {gpa}+ GPA",
            "deadline": "Dec 31, 2025",
            "link": "https://example.com/scholarship",
        }
    ]


if __name__ == "__main__":
    results = web_search_scholarships(
        field="Computer Science",
        nationality="Malaysian",
        gpa="3.7",
        year="Undergraduate sophomore",
        background="First-generation, financial need",
    )
    print(json.dumps(results, indent=2))
