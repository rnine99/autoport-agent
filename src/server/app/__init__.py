"""
FastAPI application entry point with router registration.
"""
import asyncio
import sys

if sys.platform.startswith("win"):
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from src.server.app.setup import app

__all__ = ["app"]
