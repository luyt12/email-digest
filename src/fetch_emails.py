#!/usr/bin/env python3
"""Fetch emails from AgentMail API."""

import requests
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional

from config import AGENTMAIL_BASE_URL


def fetch_recent_emails(api_key: str, inbox_id: str, limit: int = 50) -> List[Dict[str, Any]]:
    """
    Fetch recent messages from AgentMail inbox.
    
    Args:
        api_key: AgentMail API key
        inbox_id: The inbox email or ID (e.g., 'user@agentmail.to' or 'am_us_inbox_xxx')
        limit: Maximum number of messages to fetch
        
    Returns:
        List of message objects
    """
    # Support both email format and inbox ID format
    # Email: user@agentmail.to, ID: am_us_inbox_xxx
    url = f"{AGENTMAIL_BASE_URL}/inboxes/{inbox_id}/messages"
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Accept": "application/json"
    }
    
    params = {
        "limit": limit,
        "ascending": False  # Newest first
    }
    
    response = requests.get(url, headers=headers, params=params, timeout=30)
    response.raise_for_status()
    
    data = response.json()
    
    # Handle both direct list and wrapped response
    if isinstance(data, dict):
        return data.get("messages", data.get("data", []))
    return data


def get_message_content(api_key: str, inbox_id: str, message_id: str) -> Dict[str, Any]:
    """
    Fetch full content of a specific message.
    
    Args:
        api_key: AgentMail API key
        inbox_id: The inbox ID
        message_id: The message ID
        
    Returns:
        Message object with full content
    """
    url = f"{AGENTMAIL_BASE_URL}/inboxes/{inbox_id}/messages/{message_id}"
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Accept": "application/json"
    }
    
    response = requests.get(url, headers=headers, timeout=30)
    response.raise_for_status()
    
    data = response.json()
    
    # DEBUG: Print available keys in response to understand structure
    print(f"    API response keys: {list(data.keys())}")
    
    # Print body-related fields for debugging
    body_fields = [k for k in data.keys() if 'body' in k.lower() or 'content' in k.lower() or 'text' in k.lower() or 'html' in k.lower()]
    if body_fields:
        print(f"    Body-related fields: {body_fields}")
        for field in body_fields[:3]:  # Print first 3 body fields sample
            val = data.get(field)
            if isinstance(val, str):
                print(f"      {field}: {val[:100]}...")
            elif isinstance(val, dict):
                print(f"      {field}: dict with keys {list(val.keys())}")
            elif isinstance(val, list):
                print(f"      {field}: list with {len(val)} items")
            else:
                print(f"      {field}: {type(val).__name__}")
    
    # Extract body text from message
    body_text = extract_body_text(data)
    print(f"    Extracted body length: {len(body_text)} chars")
    if body_text:
        print(f"    Body preview: {body_text[:200]}...")
    else:
        print(f"    WARNING: No body text extracted!")
    
    return {
        "id": data.get("id"),
        "subject": data.get("subject", "No subject"),
        "from": data.get("from", {}),
        "to": data.get("to", []),
        "received_at": data.get("received_at") or data.get("timestamp") or data.get("created_at"),
        "body": body_text,
        "raw": data
    }


def extract_body_text(message: Dict[str, Any]) -> str:
    """
    Extract plain text body from a message object.
    Handles various body formats from AgentMail API.
    """
    # Try different body fields in order of preference
    # AgentMail API may return body in various formats
    
    # 1. Try 'body' field (most common)
    body = message.get("body")
    if body:
        if isinstance(body, str) and body.strip():
            return body.strip()
        
        if isinstance(body, dict):
            # Could be {text: "...", html: "..."} or similar
            text = body.get("text") or body.get("content") or body.get("plain")
            if text and isinstance(text, str) and text.strip():
                return text.strip()
            
            html = body.get("html") or body.get("html_content")
            if html and isinstance(html, str) and html.strip():
                # Strip HTML tags for plain text
                return strip_html(html)
        
        
        if isinstance(body, list):
            # Multiple parts - prefer text over html
            for part in body:
                if isinstance(part, dict):
                    content_type = part.get("type", "") or part.get("mime_type", "") or part.get("content_type", "")
                    content = part.get("content", "") or part.get("text", "") or part.get("body", "")
                    
                    if "plain" in content_type.lower() or "text" in content_type.lower():
                        if content and isinstance(content, str) and content.strip():
                            return content.strip()
            
            # Fall back to first part with content
            for part in body:
                if isinstance(part, dict):
                    content = part.get("content", "") or part.get("text", "") or part.get("body", "")
                    if content and isinstance(content, str) and content.strip():
                        return content.strip()
    
    # 2. Try 'content' field
    content = message.get("content")
    if content and isinstance(content, str) and content.strip():
        return content.strip()
    
    # 3. Try 'text' field
    text = message.get("text")
    if text and isinstance(text, str) and text.strip():
        return text.strip()
    
    # 4. Try 'html' field (strip tags)
    html = message.get("html") or message.get("html_body")
    if html and isinstance(html, str) and html.strip():
        return strip_html(html)
    
    # 5. Try 'payload' field (some APIs use this)
    payload = message.get("payload")
    if payload:
        if isinstance(payload, str) and payload.strip():
            return payload.strip()
        if isinstance(payload, dict):
            return extract_body_text(payload)  # Recursive
    
    # 6. Try 'parts' field
    parts = message.get("parts")
    if parts and isinstance(parts, list):
        for part in parts:
            result = extract_body_text(part)
            if result:
                return result
    
    # 7. Try 'data' field (base64 encoded in some APIs)
    data = message.get("data")
    if data and isinstance(data, str) and data.strip():
        try:
            import base64
            decoded = base64.b64decode(data).decode('utf-8')
            return decoded.strip()
        except:
            pass
    
    return ""


def strip_html(html: str) -> str:
    """Strip HTML tags and decode entities."""
    import re
    from html import unescape
    
    # Remove HTML tags
    text = re.sub(r'<[^>]+>', ' ', html)
    
    # Decode HTML entities
    text = unescape(text)
    
    # Remove extra whitespace
    text = re.sub(r'\s+', ' ', text)
    
    return text.strip()


def get_message_raw(api_key: str, inbox_id: str, message_id: str) -> str:
    """
    Fetch raw RFC822 email content.
    
    Args:
        api_key: AgentMail API key
        inbox_id: The inbox ID
        message_id: The message ID
        
    Returns:
        Raw email content as string
    """
    url = f"{AGENTMAIL_BASE_URL}/inboxes/{inbox_id}/messages/{message_id}/raw"
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Accept": "message/rfc822"
    }
    
    response = requests.get(url, headers=headers, timeout=30)
    response.raise_for_status()
    
    return response.text