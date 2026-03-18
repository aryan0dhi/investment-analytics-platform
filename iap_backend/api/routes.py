"""
API routes for the Investment Analytics Platform.

This module defines FastAPI endpoints for:
- health checks
- asset data retrieval
- running strategy analysis

It acts as the interface between the Streamlit frontend and the backend
analysis engine.
"""

from fastapi import APIRouter, HTTPException
from iap_backend.models.schemas import AnalysisRequest
from iap_backend.services.analysis_service import load_asset_data, run_analysis

router = APIRouter()


@router.get("/health")
def health_check():
    return {"status": "ok"}


@router.get("/asset")
def get_asset(ticker: str, start_date: str, end_date: str):
    try:
        return load_asset_data(ticker, start_date, end_date)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/analyze")
def analyze(request: AnalysisRequest):
    try:
        return run_analysis(request.model_dump())
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))