from fastapi import APIRouter
from pydantic import BaseModel
from app.engine.risk_predictor import predict_risk
from app.utils.response_wrapper import success_response

router = APIRouter(prefix="/risk", tags=["risk"])

class RiskInput(BaseModel):
    answers: dict

@router.post("/predict")
async def predict(payload: RiskInput):
    score = predict_risk(payload.answers)
    return success_response({"risk_score": score})