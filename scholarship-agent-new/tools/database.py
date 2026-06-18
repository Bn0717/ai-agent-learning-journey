from services.db_client import db


def save_to_db(data: dict) -> str:
    try:
        if not isinstance(data, dict):
            return "Error: data must be a dictionary"
        
        if not data:
            return "Error: data cannot be empty"
        
        db.insert_one(data)
        return "Saved to database successfully"
    except Exception as e:
        return f"Error saving to database: {str(e)}"


save_to_db_tool = {
    "name": "save_to_db",
    "description": "Save scholarship results or user data into database",
    "input_schema": {
        "type": "object",
        "properties": {
            "data": {"type": "object"}
        },
        "required": ["data"]
    },
    "function": save_to_db
}