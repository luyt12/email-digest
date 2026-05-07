#!/usr/bin/env python3
"""LLM summarization and translation of emails."""

import os
import json
import time
import requests
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List

from config import NVIDIA_API_URL, NVIDIA_API_KEY, MODEL_CHAIN, LLM_TIMEOUT, LLM_MAX_TOKENS


# Translation prompt template
TRANSLATION_PROMPT = """你是一个专业的邮件翻译助手。请将以下英文邮件内容翻译成中文，保持原文的语气、专业术语和格式。

邮件信息：
- 发件人：{sender}
- 主题：{subject}
- 时间：{received_at}

邮件正文：
{body}

请直接提供翻译后的中文内容，不要添加解释。如果正文包含代码或特殊格式，请保持原样。"""


# Fallback prompts for different models
TRANSLATION_PROMPTS = {
    "default": TRANSLATION_PROMPT
}


def translate_email(email_content: Dict[str, Any]) -> Dict[str, Any]:
    """
    Translate email content to Chinese using LLM.
    
    Args:
        email_content: Dict with subject, body, from, received_at
        
    Returns:
        Dict with original and translated content
    """
    # Extract email fields
    sender = email_content.get("from", {})
    if isinstance(sender, dict):
        sender_info = sender.get("name", "") or sender.get("email", "")
    else:
        sender_info = str(sender)
    
    subject = email_content.get("subject", "无主题")
    body = email_content.get("body", "")
    received_at = email_content.get("received_at", "")
    
    # Truncate body if too long (LLM has limits)
    max_body_length = 8000
    if len(body) > max_body_length:
        body = body[:max_body_length] + "\n\n[... 内容已截断 ...]"
    
    # Build prompt
    prompt = TRANSLATION_PROMPT.format(
        sender=sender_info,
        subject=subject,
        received_at=received_at,
        body=body
    )
    
    # Try each model in chain
    last_error = None
    for model in MODEL_CHAIN:
        try:
            translated = translate_with_model(
                prompt,
                model,
                NVIDIA_API_KEY,
                NVIDIA_API_URL
            )
            
            return {
                "id": email_content.get("id"),
                "original_sender": sender_info,
                "original_subject": subject,
                "original_time": received_at,
                "original_body": body[:500],  # Keep first 500 chars
                "translated_subject": subject,  # Keep original subject as-is
                "translated_body": translated,
                "model_used": model,
                "success": True
            }
            
        except Exception as e:
            last_error = str(e)
            print(f"  Model {model} failed: {last_error}")
            continue
    
    # All models failed
    return {
        "id": email_content.get("id"),
        "original_sender": sender_info,
        "original_subject": subject,
        "original_time": received_at,
        "original_body": body[:500],
        "translated_subject": subject,
        "translated_body": f"[翻译失败] {body[:300]}",
        "model_used": "none",
        "success": False,
        "error": last_error
    }


def translate_with_model(prompt: str, model: str, api_key: str, api_url: str) -> str:
    """
    Translate text using a specific model.
    
    Args:
        prompt: The prompt to send
        model: Model name
        api_key: API key
        api_url: API endpoint URL
        
    Returns:
        Translated text
    """
    url = api_url
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    # Use max_tokens from config or default
    max_tokens = LLM_MAX_TOKENS
    
    payload = {
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": prompt
            }
        ],
        "max_tokens": max_tokens,
        "temperature": 0.3  # Lower temperature for translation
    }
    
    response = requests.post(
        url,
        headers=headers,
        json=payload,
        timeout=LLM_TIMEOUT
    )
    
    if response.status_code != 200:
        raise Exception(f"API error {response.status_code}: {response.text[:200]}")
    
    data = response.json()
    
    # Handle different response formats
    if "choices" in data:
        choices = data["choices"]
        if choices and len(choices) > 0:
            return choices[0].get("message", {}).get("content", "")
    
    # Try alternative format
    if "output" in data:
        return data["output"]
    
    raise Exception(f"Unexpected response format: {list(data.keys())}")


def translate_emails_batch(emails: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Translate multiple emails in batch.
    Due to API rate limits, process one at a time with delay.
    
    Args:
        emails: List of email content dicts
        
    Returns:
        List of translated email dicts
    """
    results = []
    
    for i, email in enumerate(emails):
        print(f"  Translating email {i+1}/{len(emails)}...")
        
        result = translate_email(email)
        results.append(result)
        
        # Delay between requests to respect rate limits
        if i < len(emails) - 1:
            time.sleep(2)
    
    return results