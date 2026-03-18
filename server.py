from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from ego_metrology import EgoProfiler, SECTOR_CONFIGS

app = FastAPI(
    title="EGO Metrology API",
    description="Heuristic Context Saturation Profiler for LLMs — EGO V12.2",
    version="0.3.0",
)

class ProfileRequest(BaseModel):
    model_name:    str = Field(..., example="deepseek-14b")
    prompt_tokens: int = Field(..., ge=1, example=12000)

class ProfileResponse(BaseModel):
    model_used:                   str
    prompt_tokens:                int
    max_context_tokens:           int
    eta:                          float
    spectatorization_ratio:       float
    geometric_saturation:         dict
    estimated_safe_output_tokens: int
    dynamic_cost:                 float
    calibration_status:           str

@app.get("/health")
async def health():
    return {"status": "EGO Core Online", "version": "0.3.0"}

@app.get("/models")
async def models():
    return {"available_models": list(SECTOR_CONFIGS.keys())}

@app.post("/profile", response_model=ProfileResponse)
async def profile(req: ProfileRequest):
    key = req.model_name.lower()
    if key not in SECTOR_CONFIGS:
        raise HTTPException(
            status_code=404,
            detail=f"Model '{req.model_name}' not found. Available: {list(SECTOR_CONFIGS.keys())}"
        )
    try:
        profiler = EgoProfiler(key)
        result   = profiler.profile(req.prompt_tokens)
        geom     = profiler.get_geometric_saturation(req.prompt_tokens)
    except (ValueError, TypeError) as e:
        raise HTTPException(status_code=422, detail=str(e))

    return ProfileResponse(
        model_used=result.model,
        prompt_tokens=result.prompt_tokens,
        max_context_tokens=result.max_context_tokens,
        eta=result.eta,
        spectatorization_ratio=result.alpha_s,
        geometric_saturation=geom,
        estimated_safe_output_tokens=result.tau,
        dynamic_cost=result.c_dyn,
        calibration_status=result.calibration_status,
    )
