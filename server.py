# this is the code from bitdeer VM  dir: ~/Team Apex AI Tender Assistant$ more server.py
from fastapi import FastAPI
from pydantic import BaseModel
import requests
import json
import os

API_KEY = os.getenv("BITDEER_API_KEY", "YOUR_API_KEY_HERE")
URL = "https://api-inference.bitdeer.ai/v1/chat/completions"

app = FastAPI()

class ChatRequest(BaseModel):
    message: str

@app.post("/chat")
def chat(req: ChatRequest):
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
    }

    data = {
        "model": "openai/gpt-oss-120b",
        "messages": [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": req.message},
        ],
        "max_tokens": 512,
        "temperature": 0.7,
        "stream": False,
    }

    resp = requests.post(URL, headers=headers, data=json.dumps(data))
    resp.raise_for_status()
    result = resp.json()
    # assumes OpenAI-like structure
    content = result["choices"][0]["message"]["content"]
    return {"reply": content}