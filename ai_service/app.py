"""AI Query Service - endpoint REST /ask pour le Client Web.

REST choisi plutot que WebSocket : chaque question est independante,
pas d'historique a maintenir. WebSocket ne se justifierait que pour du
streaming ou une session de chat avec memoire.

CORS ouvert (allow_origins=["*"]) car le Client Web est servi separement
(port 8080, nginx) et appelle cette API depuis le navigateur.
"""

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
    result = await ask_agent(q.question)
    return {"answer": result["answer"], "tool_calls": result["tool_calls"]}


@app.get("/health")
def health():
    return {"status": "ok"}
