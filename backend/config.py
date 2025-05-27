import os
from pathlib import Path

# Get the directory where this config file is located
BASE_DIR = Path(__file__).parent.absolute()

# Tools directory relative to project root
TOOLS_DIR = BASE_DIR / "tools"

# Alternative: Use environment variable with fallback
TOOLS_DIR_ENV = os.getenv("TOOLS_DIRECTORY", str(TOOLS_DIR))

# Server configuration
SERVER_HOST = os.getenv("SERVER_HOST", "0.0.0.0")
SERVER_PORT = int(os.getenv("SERVER_PORT", 8000))
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

# CORS configuration for frontend
CORS_ORIGINS = [
    "http://localhost:3000",  # React default
    "http://localhost:5173",  # Vite default
    "http://localhost:8080",  # Vue CLI default
    "http://127.0.0.1:3000",
    "http://127.0.0.1:5173",
    "http://127.0.0.1:8080",
]

# Add custom origins from environment
custom_origins = os.getenv("CORS_ORIGINS")
if custom_origins:
    CORS_ORIGINS.extend(custom_origins.split(","))

# WebSocket configuration
WS_HEARTBEAT_INTERVAL = int(os.getenv("WS_HEARTBEAT_INTERVAL", 30))

# Tool execution timeout (seconds)
TOOL_EXECUTION_TIMEOUT = int(os.getenv("TOOL_EXECUTION_TIMEOUT", 60))

# Development settings
DEBUG = os.getenv("DEBUG", "False").lower() == "true"
RELOAD = os.getenv("RELOAD", "True").lower() == "true"