#!/usr/bin/env python3
"""Utility functions for email digest.

修改版：添加时间窗口相关函数
"""

import json
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Set, Optional

from config import PROCESSED_IDS_FILE


# 时间窗口过期阈值：保留最近 30 天（720 小时）
# 之前是 24 小时，导致超过 24 小时的邮件 ID 被清除后可能重复处理
PROCESSED_IDS_TTL_HOURS = 720

def _is_expired(timestamp_str: str) -> bool:
    """检查时间戳是否已过期（超过 TTL）。"""
    if not timestamp_str:
        return True
    try:
        ts = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        elapsed = now - ts.astimezone(timezone.utc)
        return elapsed > timedelta(hours=PROCESSED_IDS_TTL_HOURS)
    except (ValueError, AttributeError):
        return True  # 无法解析视为过期


def load_processed_ids() -> Set[str]:
    """Load processed email IDs from file, filtering out expired entries."""
    if not PROCESSED_IDS_FILE.exists():
        return set()

    try:
        with open(PROCESSED_IDS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)

        # Support both old format (list) and new format (dict)
        raw = data.get("processed_ids", {})
        if isinstance(raw, list):
            # Old format: just IDs, no timestamps — treat all as expired (clear it)
            print(f"  [dedup] 发现旧格式 processed_ids，共 {len(raw)} 条，已清除")
            return set()
        elif isinstance(raw, dict):
            # New format: {id: timestamp}
            expired = [mid for mid, ts in raw.items() if _is_expired(ts)]
            valid = {mid: ts for mid, ts in raw.items() if not _is_expired(ts)}
            if expired:
                print(f"  [dedup] 过滤掉 {len(expired)} 条过期记录，保留 {len(valid)} 条有效记录")
            return set(valid.keys())
        return set()
    except (json.JSONDecodeError, IOError) as e:
        print(f"Warning: Could not load processed IDs: {e}")
        return set()


def save_processed_ids(ids: Set[str]):
    """Save processed email IDs to file with timestamps (auto-expires after TTL)."""
    PROCESSED_IDS_FILE.parent.mkdir(parents=True, exist_ok=True)

    now_utc = datetime.now(timezone.utc)
    new_timestamp = now_utc.isoformat()

    # Load existing (may contain unexpired entries from previous runs)
    existing_ids: dict = {}
    if PROCESSED_IDS_FILE.exists():
        try:
            with open(PROCESSED_IDS_FILE, "r", encoding="utf-8") as f:
                raw = json.load(f).get("processed_ids", {})
            if isinstance(raw, dict):
                # Filter out expired entries before merging
                existing_ids = {mid: ts for mid, ts in raw.items() if not _is_expired(ts)}
        except (json.JSONDecodeError, IOError):
            pass

    # Merge: keep existing unexpired + new ids with current timestamp
    for mid in ids:
        existing_ids[mid] = new_timestamp

    existing = {}
    if PROCESSED_IDS_FILE.exists():
        try:
            with open(PROCESSED_IDS_FILE, "r", encoding="utf-8") as f:
                existing = json.load(f)
        except (json.JSONDecodeError, IOError):
            pass

    existing["processed_ids"] = existing_ids
    existing["last_updated"] = now_utc.isoformat()

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