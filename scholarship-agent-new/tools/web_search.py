import requests
import os
from dotenv import load_dotenv

load_dotenv()


def web_search(query: str) -> str:
    try:
        if not query or not isinstance(query, str):
            return "Error: query must be a non-empty string"
        
        # TODO: Replace with real API (SerpAPI / Tavily / etc.)
        # For now, return mock results
        # Example with real API:
        # api_key = os.getenv("SEARCH_API_KEY")
        # response = requests.get(f"https://api.serpapi.com/search?q={query}&api_key={api_key}")
        # return response.json()
        
        return f"Mock search results for: {query}"
    except Exception as e:
        return f"Error during search: {str(e)}"


web_search_tool = {
    "name": "web_search",
    "description": "Search scholarships and web information",
    "input_schema": {
        "type": "object",
        "properties": {
            "query": {"type": "string"}
        },
        "required": ["query"]
    },
    "function": web_search
}