# Frontend Configuration

import os
from pathlib import Path

# Project paths
BASE_DIR = Path(__file__).parent.parent
FRONTEND_DIR = BASE_DIR / "frontend"
STORAGE_DIR = BASE_DIR / "storage"
IMAGES_DIR = STORAGE_DIR / "images"
TEMP_DIR = STORAGE_DIR / "temp"

# DrHyper API Configuration
DRHYPER_API_KEY = os.getenv("DRHYPER_API_KEY", "your-api-key-here")
DRHYPER_API_BASE = os.getenv("DRHYPER_API_BASE", "http://localhost:8000")

# Streamlit Configuration
PAGE_TITLE = "医疗助手系统 - Medical Assistant"
PAGE_LAYOUT = "wide"
PAGE_ICON = "🏥"

# UI Configuration
MAX_IMAGE_SIZE_MB = 10
SUPPORTED_IMAGE_TYPES = ["png", "jpg", "jpeg", "gif", "bmp"]

# Chat Configuration
MAX_MESSAGE_HISTORY = 100
DEFAULT_TEMPERATURE = 0.7
