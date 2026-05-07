#!/usr/bin/env python3
"""Utility functions for email digest."""

import json
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Set, Optional

from config import PROCESSED_IDS_FILE


def load_processed_ids() -> Set[str]:
    """
    Load processed email IDs from file.
    
    Returns:
        Set of processed message IDs
    """
    if not PROCESSED_IDS_FILE.exists():
        return set()
    
    try:
        with open(PROCESSED_IDS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return set(data.get("processed_ids", []))
    except (json.JSONDecodeError, IOError) as e:
        print(f"Warning: Could not load processed IDs: {e}")
        return set()


def save_processed_ids(ids: Set[str]):
    """
    Save processed email IDs to file.
    
    Args:
        ids: Set of message IDs to save
    """
    # Ensure directory exists
    PROCESSED_IDS_FILE.parent.mkdir(parents=True, exist_ok=True)
    
    # Load existing to preserve data
    existing = {}
    if PROCESSED_IDS_FILE.exists():
        try:
            with open(PROCESSED_IDS_FILE, "r", encoding="utf-8") as f:
                existing = json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
    
    # Update and save
    existing["processed_ids"] = list(ids)
    existing["last_updated"] = datetime.now(timezone.utc).isoformat()
    
    with open(PROCESSED_IDS_FILE, "w", encoding="utf-8") as f:
        json.dump(existing, f, ensure_ascii=False, indent=2)


def is_today(date_str: str) -> bool:
    """
    Check if a date string is from today.
    
    Args:
        date_str: ISO format date string (e.g., "2026-05-07T08:00:00Z")
        
    Returns:
        True if the date is today
    """
    if not date_str:
        return False
    
    try:
        # Parse the date
        # Handle various formats
        date_str = date_str.replace("+00:00", "Z").replace("+0000", "Z")
        
        if date_str.endswith("Z"):
            dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        else:
            dt = datetime.fromisoformat(date_str)
        
        # Get today's date in UTC
        now = datetime.now(timezone.utc)
        today = now.date()
        msg_date = dt.date()
        
        return msg_date == today
        
    except (ValueError, AttributeError) as e:
        # If we can't parse, assume it's not today
        print(f"Warning: Could not parse date '{date_str}': {e}")
        return False


def is_recent(date_str: str, hours: int = 24) -> bool:
    """
    Check if a date string is within the last N hours.
    
    Args:
        date_str: ISO format date string
        hours: Number of hours to check
        
    Returns:
        True if the date is within the last N hours
    """
    if not date_str:
        return False
    
    try:
        # Parse the date
        date_str = date_str.replace("+00:00", "Z").replace("+0000", "Z")
        
        if date_str.endswith("Z"):
            dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        else:
            dt = datetime.fromisoformat(date_str)
        
        # Get current time and threshold
        now = datetime.now(timezone.utc)
        threshold = now - timedelta(hours=hours)
        
        return dt >= threshold
        
    except (ValueError, AttributeError):
        return False


def format_date_local(date_str: str, tz: str = "Asia/Shanghai") -> str:
    """
    Format a date string in local timezone.
    
    Args:
        date_str: ISO format date string
        tz: Timezone name
        
    Returns:
        Formatted date string
    """
    if not date_str:
        return ""
    
    try:
        # Parse
        date_str = date_str.replace("+00:00", "Z").replace("+0000", "Z")
        
        if date_str.endswith("Z"):
            dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        else:
            dt = datetime.fromisoformat(date_str)
        
        # Format in local time
        return dt.strftime("%Y-%m-%d %H:%M")
        
    except (ValueError, AttributeError):
        return date_str


def truncate_text(text: str, max_length: int = 200) -> str:
    """
    Truncate text to a maximum length.
    
    Args:
        text: Text to truncate
        max_length: Maximum length
        
    Returns:
        Truncated text with ellipsis if needed
    """
    if len(text) <= max_length:
        return text
    
    return text[:max_length - 3] + "..."


def clean_text(text: str) -> str:
    """
    Clean text by removing extra whitespace and control characters.
    
    Args:
        text: Text to clean
        
    Returns:
        Cleaned text
    """
    if not text:
        return ""
    
    # Remove control characters except newlines and tabs
    cleaned = "".join(char for char in text if char.isprintable() or char in "\n\t")
    
    # Normalize whitespace
    import re
    cleaned = re.sub(r"\n\n+", "\n\n", cleaned)
    cleaned = re.sub(r" +", " ", cleaned)
    
    return cleaned.strip()