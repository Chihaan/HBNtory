#!/usr/bin/env python3
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from agent import ask_agent
from dotenv import load_dotenv

load_dotenv()

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

class Question(BaseModel):
    question: str

@app.post("/ask")
async def ask(q: Question):
    answer = await ask_agent(q.question)
    return {"answer": answer}

@app.get("/health")
def health():
    return {"status": "ok"}
