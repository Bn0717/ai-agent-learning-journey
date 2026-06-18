from fastapi import FastAPI
from pydantic import BaseModel
from agent.runner import run_agent

app = FastAPI()

class QueryRequest(BaseModel):
    message: str


@app.post("/query")
async def query(req: QueryRequest):
    result = await run_agent(req.message)
    return {"response": result}