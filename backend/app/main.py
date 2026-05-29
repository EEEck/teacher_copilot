import os

from agents import set_default_openai_key
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.errors import install_error_handlers
from app.api.routes import router
from app.config import get_settings

settings = get_settings()

# Agents SDK reads OPENAI_API_KEY from the process environment, not pydantic-settings.
_openai_key = settings.openai_api_key.get_secret_value()
if _openai_key:
    os.environ.setdefault("OPENAI_API_KEY", _openai_key)
    set_default_openai_key(_openai_key)

app = FastAPI(title="KlassenPilot API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

install_error_handlers(app)

app.include_router(router)
