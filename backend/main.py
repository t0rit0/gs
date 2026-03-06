"""
Backend Service Startup Script

Run with:
    python -m backend.main
Or:
    uvicorn backend.api.server:app --reload --host 0.0.0.0 --port 8000
"""
import sys
import os
import logging

# Add project root to Python path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

# Set environment variables (optional)
os.environ.setdefault("ENVIRONMENT", "development")
os.environ.setdefault("DB_DIR", os.path.join(project_root, "data"))

if __name__ == "__main__":
    import uvicorn
    from drhyper.utils.logging import get_logger, configure_logging
    from backend.config.config_manager import get_config

    # Load configuration and apply logging settings
    config = get_config()
    
    # Map config log levels to logging module constants
    log_levels = {
        "DEBUG": logging.DEBUG,
        "INFO": logging.INFO,
        "WARNING": logging.WARNING,
        "ERROR": logging.ERROR,
        "CRITICAL": logging.CRITICAL,
    }
    
    console_level = log_levels.get(config.get("logging.console_level", "INFO"), logging.INFO)
    file_level = log_levels.get(config.get("logging.file_level", "DEBUG"), logging.DEBUG)
    
    configure_logging(
        level=console_level,
        file_level=file_level,
        log_dir=config.get("logging.log_dir", "logs"),
        max_bytes=config.get("logging.max_file_size", 10 * 1024 * 1024),
        backup_count=config.get("logging.backup_count", 5),
        enable_structured=config.get("logging.enable_structured", False)
    )

    logger = get_logger("BackendMain")

    logger.info("=" * 60)
    logger.info("Starting Medical Assistant Backend API Service")
    logger.info("=" * 60)
    logger.info(f"Project root: {project_root}")
    logger.info(f"Environment: {os.environ.get('ENVIRONMENT', 'development')}")
    logger.info(f"Database directory: {os.environ.get('DB_DIR', 'data')}")
    logger.info(f"Console log level: {logging.getLevelName(console_level)}")
    logger.info(f"File log level: {logging.getLevelName(file_level)}")
    logger.info("=" * 60)

    # Start server
    uvicorn.run(
        "backend.api.server:app",
        host="0.0.0.0",
        port=8000,
        reload=True,  # Enable hot reload in development mode
        log_level="info"
    )
