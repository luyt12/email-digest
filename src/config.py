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

# Model chain (in order of preference) - NVIDIA API
MODEL_CHAIN = [
    "minimaxai/minimax-m2.7",                  # Primary
    "qwen/qwen3-coder-480b-a35b-instruct",    # Fallback 1
    "stepfun-ai/step-3.5-flash",              # Fallback 2
    "google/gemma-3n-e2b-it",                 # Fallback 3
    "mistralai/mistral-nemotron",             # Fallback 4
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