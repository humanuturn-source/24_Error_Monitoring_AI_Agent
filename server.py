"""
server.py
OpenAI-compatible FastAPI server on port 8000 connecting Open WebUI
to the LocalErrorCheckMultiAgent workflow.
"""

import logging
import sys
from typing import Any, Dict, List

from fastapi import FastAPI
from pydantic import BaseModel

from agents import LocalErrorCheckMultiAgent
from database import ErrorCheckDatabase

logging.basicConfig(level=logging.INFO, format="%(message)s", stream=sys.stdout)
logger = logging.getLogger("ErrorAgentServer")

app = FastAPI(title="Local UI Error Check Agent Server")

db = ErrorCheckDatabase()
agent_system = LocalErrorCheckMultiAgent(db=db, headless=False)


class ChatMessage(BaseModel):
    role: str
    content: Any


class ChatCompletionRequest(BaseModel):
    model: str
    messages: List[ChatMessage]


@app.get("/v1/models")
def list_models() -> dict:
    return {
        "object": "list",
        "data": [
            {
                "id": "local-error-check-agent",
                "object": "model",
                "owned_by": "local-machine",
            }
        ],
    }


@app.get("/runs/recent")
def recent_runs() -> dict:
    return {"recent_error_check_runs": db.get_recent_runs(limit=10)}


@app.post("/v1/chat/completions")
def chat_completions(request: ChatCompletionRequest) -> dict:
    normalized: List[Dict[str, str]] = []
    for m in request.messages:
        if isinstance(m.content, str):
            txt = m.content
        elif isinstance(m.content, list):
            txt = "".join(p.get("text", "") for p in m.content if isinstance(p, dict))
        else:
            txt = str(m.content)
        normalized.append({"role": m.role, "content": txt})

    user_query = next(
        (m["content"] for m in reversed(normalized) if m["role"] == "user"), ""
    )

    # Handle Open WebUI background title/tag prompts cleanly
    if "### Task:" in user_query and (
        "Generate a concise" in user_query or "Suggest 3-5 relevant" in user_query
    ):
        return {
            "id": "chatcmpl-meta",
            "object": "chat.completion",
            "model": request.model,
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": "UI Error Check Session"},
                    "finish_reason": "stop",
                }
            ],
        }

    reply = agent_system.run(user_query)
    return {
        "id": "chatcmpl-error-agent",
        "object": "chat.completion",
        "model": request.model,
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": reply},
                "finish_reason": "stop",
            }
        ],
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
