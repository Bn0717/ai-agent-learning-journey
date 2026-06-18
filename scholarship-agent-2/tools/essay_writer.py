import os
from anthropic import AnthropicVertex

PROJECT_ID = os.getenv('GCP_PROJECT_ID', 'brain-433706')
REGION     = os.getenv('GCP_REGION', 'asia-southeast1')
MODEL      = 'claude-3-5-sonnet@20240620'


def write_essay(scholarship_name: str, student_profile: dict, essay_prompt: str = None) -> dict:
    """Draft a personalised scholarship application essay for the student."""
    client = AnthropicVertex(project_id=PROJECT_ID, region=REGION)

    prompt = f"""Write a compelling 300-word scholarship application essay in first person.

Scholarship: {scholarship_name}
Student name: {student_profile.get('name', 'the applicant')}
Field of study: {student_profile.get('field_of_study', 'N/A')}
CGPA: {student_profile.get('cgpa', 'N/A')}
Nationality: {student_profile.get('nationality', 'N/A')}
Essay prompt: {essay_prompt or 'Why do you deserve this scholarship and how will it help you achieve your goals?'}

Be specific, genuine, and persuasive. Do not use generic filler phrases."""

    response = client.messages.create(
        model=MODEL,
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    )
    return {
        "scholarship": scholarship_name,
        "student": student_profile.get('name'),
        "essay": response.content[0].text,
    }
