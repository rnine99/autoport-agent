"""
Server script
"""
import asyncio
import sys
import argparse
import logging
import uvicorn

logger = logging.getLogger(__name__)

if __name__ == "__main__":
    if sys.platform.startswith("win"):
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Run the server")
    parser.add_argument(
        "--reload",
        action="store_true",
        help="Enable auto-reload (default: True except on Windows)",
    )
    parser.add_argument(
        "--host",
        type=str,
        default="localhost",
        help="Host to bind the server to (default: localhost)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Port to bind the server to (default: 8000)",
    )
    parser.add_argument(
        "--log-level",
        type=str,
        default="info",
        choices=["debug", "info", "warning", "error", "critical"],
        help="Log level (default: info)",
    )

    args = parser.parse_args()

    # Configure SSE event logger independently
    # This allows viewing ONLY SSE events by setting SSE_EVENT_LOG_LEVEL=info
    # and server --log-level=error
    import os
    sse_event_log_level = os.getenv("SSE_EVENT_LOG_LEVEL", "info").upper()
    sse_logger = logging.getLogger("sse_events")
    sse_logger.setLevel(getattr(logging, sse_event_log_level))
    # Add dedicated handler so SSE logs output independently of root logger level
    sse_handler = logging.StreamHandler()
    sse_handler.setLevel(getattr(logging, sse_event_log_level))
    sse_handler.setFormatter(logging.Formatter("%(message)s"))
    sse_logger.addHandler(sse_handler)
    # Prevent duplicate logs by not propagating to root logger
    sse_logger.propagate = False


    # Determine reload setting
    reload = False
    if args.reload:
        reload = True

    try:
        if sys.platform.startswith("win"):
            import uvicorn.loops.asyncio as _uvicorn_asyncio
            _orig = _uvicorn_asyncio.asyncio_loop_factory

            def _win_selector_factory(use_subprocess: bool = False):
                if use_subprocess:
                    return _orig(use_subprocess=True)
                return asyncio.SelectorEventLoop

            _uvicorn_asyncio.asyncio_loop_factory = _win_selector_factory

        logger.info(f"Starting server on {args.host}:{args.port}")
        uvicorn.run(
            "src.server.app:app",
            host=args.host,
            port=args.port,
            reload=reload,
            log_level=args.log_level,
            timeout_keep_alive=300,  # 5 minutes - for long-running workflows
            timeout_graceful_shutdown=60,  # 60 seconds for graceful shutdown
        )
    except Exception as e:
        logger.error(f"Failed to start server: {str(e)}")
        exit(1)
