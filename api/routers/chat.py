"""
Chat router for Ollama agent proxy.
Web UI → API → Agent → Ollama
"""
import os
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import httpx

router = APIRouter(prefix="/api/chat", tags=["chat"])


class ChatQueryRequest(BaseModel):
    text: str
    context: dict | None = None


@router.post("/query")
async def chat_query(req: ChatQueryRequest):
    """
    Proxy chat queries to the agent service.
    Web UI → API → Agent → Ollama
    """
    agent_url = os.getenv("AGENT_URL", "http://agent:8081")
    
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{agent_url}/v1/agent/query",
                json={
                    "text": req.text,
                    "context": req.context or {}
                }
            )
            response.raise_for_status()
            return response.json()
    except httpx.HTTPStatusError as e:
        raise HTTPException(
            status_code=e.response.status_code,
            detail=f"Agent error: {e.response.text}"
        )
    except httpx.RequestError as e:
        raise HTTPException(
            status_code=503,
            detail=f"Agent unavailable: {str(e)}"
        )
