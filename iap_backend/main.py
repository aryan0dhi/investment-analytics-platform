"""
FastAPI application entry point.

Initializes the API and registers routes.
"""

from fastapi import FastAPI
from iap_backend.api.routes import router

app = FastAPI(title="Investment Analytics Platform API")
app.include_router(router)