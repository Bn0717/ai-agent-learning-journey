import os
from google import genai
from google.genai import types

_SYSTEM = """You are a scholarship research assistant. Search for real, currently open scholarships.
For each scholarship extract: Name, Provider, Coverage, Eligibility, Deadline, Application Link.
Return max 5 scholarships. Omit any field that is unknown. Be factual and concise."""


def search_web_scholarships(query: str) -> str:
    """Search the web for scholarships matching the query using Gemini + Google Search grounding."""
    client = genai.Client(api_key=os.getenv('GEMINI_API_KEY'))
    chat = client.chats.create(
        model='gemini-2.5-flash-lite',
        config=types.GenerateContentConfig(
            system_instruction=_SYSTEM,
            tools=[types.Tool(google_search=types.GoogleSearch())],
        ),
    )
    response = chat.send_message(query)
    return response.text or "No results found."
