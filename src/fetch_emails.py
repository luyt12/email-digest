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
        inbox_id: The inbox ID to fetch from
        limit: Maximum number of messages to fetch
        
    Returns:
        List of message objects
    """
    url = f"{AGENTMAIL_BASE_URL}/inboxes/{inbox_id}/messages"
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Accept": "application/json"
    }
    
    params = {
        "limit": limit,
        "ascending": True  # Oldest first
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
    
    # Extract body text from message
    body_text = extract_body_text(data)
    
    return {
        "id": data.get("id"),
        "subject": data.get("subject", "No subject"),
        "from": data.get("from", {}),
        "to": data.get("to", []),
        "received_at": data.get("received_at"),
        "body": body_text,
        "raw": data
    }


def extract_body_text(message: Dict[str, Any]) -> str:
    """
    Extract plain text body from a message object.
    Handles various body formats.
    """
    # Try different body fields
    body = message.get("body", "")
    
    if isinstance(body, str):
        return body
    
    if isinstance(body, dict):
        # AgentMail may return body as {text: "...", html: "..."}
        return body.get("text", body.get("content", ""))
    
    if isinstance(body, list):
        # Multiple parts - prefer text over html
        for part in body:
            if isinstance(part, dict):
                if part.get("type") == "text" or part.get("mime_type", "").startswith("text/plain"):
                    return part.get("content", "")
        # Fall back to first part
        if body and isinstance(body[0], dict):
            return body[0].get("content", "")
    
    return str(body)


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