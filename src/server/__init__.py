"""
The FastAPI application is located in app.py.
Import it directly: from src.server.app import app
"""

import asyncio
import sys

if sys.platform.startswith("win"):
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

