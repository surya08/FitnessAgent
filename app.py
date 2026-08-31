from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI()

class Query(BaseModel):
    user_message: str

@app.get("/")
def home():
    return {"status": "Fitness Agent is online"}

@app.post("/chat")
def chat_with_agent(data: Query):
    response = f"Agent received: {data.user_message}" 
    return {"response": response}
