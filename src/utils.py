#!/usr/bin/env python3
"""Utility functions for email digest.

修改版：添加时间窗口相关函数
"""

import json
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Set, Optional

from config import PROCESSED_IDS_FILE


def load_processed_ids() -> Set[str]:
    """Load processed email IDs from file."""
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
    """Save processed email IDs to file."""
    PROCESSED_IDS_FILE.parent.mkdir(parents=True, exist_ok=True)
    
    existing = {}
    if PROCESSED_IDS_FILE.exists():
        try:
            with open(PROCESSED_IDS_FILE, "r", encoding="utf-8") as f:
                existing = json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
    
    existing["processed_ids"] = list(ids)
    existing["last_updated"] = datetime.now(timezone.utc).isoformat()
    
    with open(PROCESSED_IDS_FILE, "w", encoding="utf-8") as f:
        json.dump(existing, f, ensure_ascii=False, indent=2)


def load_last_run_time() -> Optional[datetime]:
    """
    加载上次运行时间。
    
    Returns:
        上次运行的 UTC 时间，如果没有则返回 None
    """
    if not PROCESSED_IDS_FILE.exists():
        return None
    
    try:
        with open(PROCESSED_IDS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            last_run = data.get("last_run_time")
            if last_run:
                return datetime.fromisoformat(last_run.replace("Z", "+00:00"))
    except (json.JSONDecodeError, IOError, ValueError):
        pass
    
    return None


def save_last_run_time(dt: datetime = None):
    """
    保存当前运行时间。
    
    Args:
        dt: 要保存的时间，默认为当前 UTC 时间
    """
    if dt is None:
        dt = datetime.now(timezone.utc)
    
    PROCESSED_IDS_FILE.parent.mkdir(parents=True, exist_ok=True)
    
    existing = {}
    if PROCESSED_IDS_FILE.exists():
        try:
            with open(PROCESSED_IDS_FILE, "r", encoding="utf-8") as f:
                existing = json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
    
    existing["last_run_time"] = dt.isoformat()
    
    with open(PROCESSED_IDS_FILE, "w", encoding="utf-8") as f:
        json.dump(existing, f, ensure_ascii=False, indent=2)


def is_today(date_str: str) -> bool:
    """Check if a date string is from today."""
    if not date_str:
        return False
    
    try:
        date_str = date_str.replace("+00:00", "Z").replace("+0000", "Z")
        
        if date_str.endswith("Z"):
            dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        else:
            dt = datetime.fromisoformat(date_str)
        
        now = datetime.now(timezone.utc)
        today = now.date()
        msg_date = dt.date()
        
        return msg_date == today
        
    except (ValueError, AttributeError) as e:
        print(f"Warning: Could not parse date '{date_str}': {e}")
        return False


def is_recent(date_str: str, hours: int = 24) -> bool:
    """Check if a date string is within the last N hours."""
    if not date_str:
        return False
    
    try:
        date_str = date_str.replace("+00:00", "Z").replace("+0000", "Z")
        
        if date_str.endswith("Z"):
            dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        else:
            dt = datetime.fromisoformat(date_str)
        
        now = datetime.now(timezone.utc)
        threshold = now - timedelta(hours=hours)
        
        return dt >= threshold
        
    except (ValueError, AttributeError):
        return False


def format_date_local(date_str: str, tz: str = "Asia/Shanghai") -> str:
    """Format a date string in local timezone."""
    if not date_str:
        return ""
    
    try:
        date_str = date_str.replace("+00:00", "Z").replace("+0000", "Z")
        
        if date_str.endswith("Z"):
            dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        else:
            dt = datetime.fromisoformat(date_str)
        
        return dt.strftime("%Y-%m-%d %H:%M")
        
    except (ValueError, AttributeError):
        return date_str


def truncate_text(text: str, max_length: int = 200) -> str:
    """Truncate text to a maximum length."""
    if len(text) <= max_length:
        return text
    
    return text[:max_length - 3] + "..."


def clean_text(text: str) -> str:
    """Clean text by removing extra whitespace and control characters."""
    if not text:
        return ""
    
    import re
    cleaned = "".join(char for char in text if char.isprintable() or char in "\n\t")
    cleaned = re.sub(r"\n\n+", "\n\n", cleaned)
    cleaned = re.sub(r" +", " ", cleaned)
    
    return cleaned.strip()
