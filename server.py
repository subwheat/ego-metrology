from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from ego_metrology import __version__, EgoProfiler, SECTOR_CONFIGS

app = FastAPI(
    title="EGO Metrology API",
    version=__version__,
)

class ProfileRequest(BaseModel):
    model_name: str = Field(..., json_schema_extra={"example": "deepseek-14b"})
    prompt_tokens: int = Field(..., ge=1, json_schema_extra={"example": 12000})

@app.get("/health")
async def health():
    return {
        "status": "EGO Core Online",
        "version": __version__,
    }

@app.get("/models")
async def models():
    return sorted(SECTOR_CONFIGS.keys())

@app.post("/profile")
async def profile(req: ProfileRequest):
    if req.model_name not in SECTOR_CONFIGS:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown model '{req.model_name}'. Available: {sorted(SECTOR_CONFIGS.keys())}",
        )

    profiler = EgoProfiler(req.model_name)
    result = profiler.profile(prompt_tokens=req.prompt_tokens)

    if hasattr(result, "model_dump"):
        return result.model_dump()
    if hasattr(result, "dict"):
        return result.dict()

    return result
