from pydantic import BaseModel
from typing import Optional, Any

class ProcessRequest(BaseModel):
    confidence: Optional[float] = None
    every_n_frames: Optional[int] = None
    detect_faces: bool = True
    save_snapshots: bool = True

class HealthResponse(BaseModel):
    status: str
    app: str
