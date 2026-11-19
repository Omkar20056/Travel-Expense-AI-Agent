from pydantic import BaseModel
from typing import List, Optional, Dict, Any

class ChatMessage(BaseModel):
    role: str  # "user" or "assistant"
    content: str

class ChatRequest(BaseModel):
    message: str
    trip_id: Optional[int] = None
    history: Optional[List[ChatMessage]] = []

class ToolExecutionResult(BaseModel):
    tool: str
    arguments: Dict[str, Any]
    result: Dict[str, Any]

class ChatResponse(BaseModel):
    response: str
    clarification_needed: bool = False
    tools_called: List[ToolExecutionResult] = []
    active_trip_id: Optional[int] = None
