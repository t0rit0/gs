"""
Backend Service Startup Script

Run with:
    python -m backend.main
Or:
    uvicorn backend.api.server:app --reload --host 0.0.0.0 --port 8000
"""
import sys
import os

# Add project root to Python path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

# Set environment variables (optional)
os.environ.setdefault("ENVIRONMENT", "development")
os.environ.setdefault("DB_DIR", os.path.join(project_root, "data"))

if __name__ == "__main__":
    import uvicorn
    from drhyper.utils.logging import get_logger

    logger = get_logger("BackendMain")

    logger.info("=" * 60)
    logger.info("Starting Medical Assistant Backend API Service")
    logger.info("=" * 60)
    logger.info(f"Project root: {project_root}")
    logger.info(f"Environment: {os.environ.get('ENVIRONMENT', 'development')}")
    logger.info(f"Database directory: {os.environ.get('DB_DIR', 'data')}")
    logger.info("=" * 60)

    # Start server
    uvicorn.run(
        "backend.api.server:app",
        host="0.0.0.0",
        port=8000,
        reload=True,  # Enable hot reload in development mode
        log_level="info"
    )
