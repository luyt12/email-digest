#!/usr/bin/env python3
"""Configuration and environment variables for email digest."""

import os
from pathlib import Path


# Project paths
PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "data"
PROCESSED_IDS_FILE = DATA_DIR / "processed_emails.json"

# AgentMail API
AGENTMAIL_BASE_URL = "https://api.agentmail.to/v0"
AGENTMAIL_INBOX_EMAIL = "excitedsilver931@agentmail.to"  # 邮箱地址格式
AGENTMAIL_INBOX_ID = os.environ.get("AGENTMAIL_INBOX_ID", "")  # 旧格式兼容
AGENTMAIL_API_KEY = os.environ.get("AGENTMAIL_API_KEY", "")

# Target email
TARGET_EMAIL = os.environ.get("TARGET_EMAIL", "")

# LLM API (NVIDIA)
NVIDIA_API_URL = "https://integrate.api.nvidia.com/v1/chat/completions"
NVIDIA_API_KEY = os.environ.get("NVIDIA_API_KEY", "")

# LLM API (OpenRouter)
OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")

# Model chain (in order of preference)
# Format: "provider/model-name" or just "model-name" for NVIDIA
MODEL_CHAIN = [
    "minimaxai/minimax-m2.7",                  # Primary (NVIDIA)
    "qwen/qwen3-coder-480b-a35b-instruct",    # Fallback 1 (NVIDIA)
    "stepfun-ai/step-3.5-flash",              # Fallback 2 (NVIDIA)
    "google/gemma-3n-e2b-it",                 # Fallback 3 (NVIDIA)
    "mistralai/mistral-nemotron",             # Fallback 4 (NVIDIA)
    "openrouter/free",                        # OpenRouter free tier (备选)
]

# SMTP settings for sending (AgentMail SMTP)
SMTP_HOST = "smtp.agentmail.to"
SMTP_PORT = 465
SMTP_USER = "agentmail"
SMTP_PASSWORD = os.environ.get("AGENTMAIL_SMTP_PASSWORD", "")

# Fallback SMTP password from stored credential
if not SMTP_PASSWORD:
    # The AgentMail API key is used as SMTP password
    SMTP_PASSWORD = AGENTMAIL_API_KEY

# LLM settings
LLM_TIMEOUT = 120  # seconds
LLM_MAX_TOKENS = 2048


def get_model_provider(model_name: str) -> str:
    """
    Determine the API provider for a given model.
    
    Args:
        model_name: Model identifier (e.g., "minimaxai/minimax-m2.7" or "openrouter/auto")
        
    Returns:
        "nvidia" or "openrouter"
    """
    if model_name.startswith("openrouter/") or "/" not in model_name:
        # Check if it's a known OpenRouter model prefix
        openrouter_prefixes = ["openrouter/", "openai/", "anthropic/", "google/", "meta-llama/", "deepseek/", "mistral/"]
        for prefix in openrouter_prefixes:
            if model_name.startswith(prefix):
                return "openrouter"
        # If no known prefix but has slash, check if it's not a known NVIDIA model
        nvidia_models = ["minimaxai/", "qwen/", "stepfun-ai/", "google/", "mistralai/"]
        for prefix in nvidia_models:
            if model_name.startswith(prefix):
                return "nvidia"
        # Unknown provider with slash, default to openrouter
        return "openrouter"
    return "nvidia"


def get_api_url_for_model(model_name: str) -> str:
    """Get the API URL for a model."""
    provider = get_model_provider(model_name)
    if provider == "openrouter":
        return OPENROUTER_API_URL
    return NVIDIA_API_URL


def get_api_key_for_model(model_name: str) -> str:
    """Get the API key for a model."""
    provider = get_model_provider(model_name)
    if provider == "openrouter":
        return OPENROUTER_API_KEY
    return NVIDIA_API_KEY
