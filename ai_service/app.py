#!/usr/bin/env python3

from fastapi import FastAPI, HTTPException
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
    try:
        answer = await ask_agent(q.question)
        return {"answer": answer}

    except Exception as e:
        error_message = str(e)

        if "429" in error_message or "quota" in error_message.lower():
            raise HTTPException(
                status_code=429,
                detail="Le quota Gemini est temporairement dépassé. "
                       "Veuillez réessayer dans quelques instants."
            )

        raise HTTPException(
            status_code=500,
            detail="Une erreur est survenue dans le service IA."
        )


@app.get("/health")
def health():
    return {"status": "ok"}
