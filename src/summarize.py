#!/usr/bin/env python3
"""LLM summarization and translation of emails.

Translation logic:
1. Extract article content from email body (ignore ads, footers, etc.)
2. For long articles (>2000 words), split by natural paragraphs
3. Translate each part with fallback model chain
4. Chinese summary length ≈ English word count × 80%
5. Mark model used for each article
"""

import os
import re
import time
import requests
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List, Tuple

from config import (
    NVIDIA_API_URL, NVIDIA_API_KEY,
    OPENROUTER_API_URL, OPENROUTER_API_KEY,
    MODEL_CHAIN, LLM_TIMEOUT, LLM_MAX_TOKENS,
    get_api_url_for_model, get_api_key_for_model
)


# Summary translation prompt (80% compression ratio)
SUMMARY_PROMPT = """你是一个专业的文章摘要翻译助手。

任务：将以下英文文章内容翻译成中文摘要。

翻译原则：
1. 中文摘要的字数应约为英文原文单词数的80%
2. 保留文章的核心观点、关键事实和重要细节
3. 使用流畅、专业的中文表达
4. 保持原文的专业术语准确性

英文文章内容（共 {word_count} 个英文单词）：
{content}

请直接提供中文摘要，不要添加任何解释或说明。"""


def count_words(text: str) -> int:
    """Count words in text (approximate for mixed content)."""
    # Split by whitespace and count
    words = text.split()
    return len(words)


def split_by_paragraphs(text: str, max_words: int = 2000) -> List[str]:
    """
    Split text into parts by natural paragraphs, each part <= max_words.
    
    Args:
        text: The text to split
        max_words: Maximum words per part (default 2000)
        
    Returns:
        List of text parts
    """
    # Split into paragraphs (double newline or single newline)
    paragraphs = re.split(r'\n\s*\n|\n', text.strip())
    paragraphs = [p.strip() for p in paragraphs if p.strip()]
    
    if not paragraphs:
        return [text] if text.strip() else []
    
    parts = []
    current_part = []
    current_words = 0
    
    for para in paragraphs:
        para_words = count_words(para)
        
        # If single paragraph exceeds max_words, we still include it (can't split mid-para)
        if para_words > max_words:
            # Save current part if not empty
            if current_part:
                parts.append('\n\n'.join(current_part))
                current_part = []
                current_words = 0
            # Add this large paragraph as its own part
            parts.append(para)
            continue
        
        # Check if adding this paragraph would exceed limit
        if current_words + para_words > max_words:
            # Save current part and start new one
            if current_part:
                parts.append('\n\n'.join(current_part))
            current_part = [para]
            current_words = para_words
        else:
            # Add to current part
            current_part.append(para)
            current_words += para_words
    
    # Don't forget the last part
    if current_part:
        parts.append('\n\n'.join(current_part))
    
    return parts


def extract_article_content(body: str, subject: str = "") -> str:
    """
    Extract article content from email body.
    Remove ads, footers, signatures, and other non-content.
    
    Args:
        body: Raw email body text
        subject: Email subject (for context)
        
    Returns:
        Cleaned article content
    """
    if not body:
        return ""
    
    # Common patterns to remove
    remove_patterns = [
        # Unsubscribe links
        r'\[Unsubscribe\].*',
        r'Click here to unsubscribe.*',
        r'To unsubscribe.*',
        r'取消订阅.*',
        # View in browser links
        r'\[View in browser\].*',
        r'View this email in your browser.*',
        # Social media links
        r'Follow us on.*',
        r'Connect with us.*',
        # Footer patterns
        r'---+\s*$',
        r'___+\s*$',
        r'\*\*\*+\s*$',
        # Copyright
        r'Copyright ©.*',
        r'© \d{4}.*',
        # Powered by
        r'Powered by.*',
        # Empty lines at end
    ]
    
    text = body
    
    # Remove common noise patterns
    for pattern in remove_patterns:
        text = re.sub(pattern, '', text, flags=re.IGNORECASE | re.MULTILINE)
    
    # Try to detect and extract main content
    lines = text.split('\n')
    
    # Remove lines that look like footers/signatures
    content_lines = []
    footer_started = False
    
    for i, line in enumerate(lines):
        stripped = line.strip()
        
        # Skip empty lines at the very beginning
        if not content_lines and not stripped:
            continue
        
        # Detect footer start
        if any([
            stripped.startswith('--'),
            stripped.startswith('Best,'),
            stripped.startswith('Regards,'),
            stripped.startswith('Thanks,'),
            stripped.startswith('Thank you,'),
            stripped.startswith('Sincerely,'),
            re.match(r'^\w+\s*$', stripped) and i > len(lines) - 5,  # Name signature
        ]):
            footer_started = True
        
        if not footer_started:
            content_lines.append(line)
    
    # Join and clean up
    content = '\n'.join(content_lines)
    
    # Remove excessive whitespace
    content = re.sub(r'\n{3,}', '\n\n', content)
    content = content.strip()
    
    return content


def translate_part_with_model(
    content: str, 
    model: str, 
    word_count: int
) -> str:
    """
    Translate a single part with a specific model.
    Automatically selects the correct API endpoint based on model provider.
    
    Args:
        content: Text content to translate
        model: Model name (e.g., "nvidia/minimaxai/minimax-m2.7" or "openrouter/auto")
        word_count: Word count for prompt
        
    Returns:
        Translated text
    """
    prompt = SUMMARY_PROMPT.format(
        word_count=word_count,
        content=content
    )
    
    # Get the correct API URL and key based on model provider
    api_url = get_api_url_for_model(model)
    api_key = get_api_key_for_model(model)
    
    if not api_key:
        raise Exception(f"No API key configured for model {model}")
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    # OpenRouter requires HTTP-Referer header
    if "openrouter" in api_url:
        headers["HTTP-Referer"] = "https://github.com/luyt12/email-digest"
        headers["X-Title"] = "Email Digest"
    
    # Estimate max_tokens: Chinese chars ≈ English words × 80%
    # But we need more tokens for the response
    max_tokens = max(LLM_MAX_TOKENS, int(word_count * 1.2))
    
    payload = {
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": prompt
            }
        ],
        "max_tokens": max_tokens,
        "temperature": 0.3
    }
    
    response = requests.post(
        api_url,
        headers=headers,
        json=payload,
        timeout=LLM_TIMEOUT
    )
    
    if response.status_code != 200:
        raise Exception(f"API error {response.status_code}: {response.text[:200]}")
    
    data = response.json()
    
    # Extract response
    if "choices" in data:
        choices = data["choices"]
        if choices and len(choices) > 0:
            return choices[0].get("message", {}).get("content", "")
    
    if "output" in data:
        return data["output"]
    
    raise Exception(f"Unexpected response format: {list(data.keys())}")


def translate_article(content: str) -> Tuple[str, str, bool]:
    """
    Translate an article with paragraph splitting and model fallback.
    
    Args:
        content: Article content to translate
        
    Returns:
        Tuple of (translated_text, model_used, success)
    """
    if not content or not content.strip():
        return "", "none", False
    
    word_count = count_words(content)
    print(f"    Article word count: {word_count}")
    
    # Split into parts if needed
    parts = split_by_paragraphs(content, max_words=2000)
    print(f"    Split into {len(parts)} part(s)")
    
    translated_parts = []
    successful_model = None
    
    for i, part in enumerate(parts):
        part_words = count_words(part)
        print(f"    Part {i+1}/{len(parts)}: {part_words} words")
        
        translated = None
        last_error = None
        
        # Try models in order
        models_to_try = MODEL_CHAIN if not successful_model else [successful_model] + [m for m in MODEL_CHAIN if m != successful_model]
        
        for model in models_to_try:
            try:
                translated = translate_part_with_model(part, model, part_words)
                if not successful_model:
                    successful_model = model
                print(f"      ✓ Model {model} succeeded")
                break
            except Exception as e:
                last_error = str(e)
                print(f"      ✗ Model {model} failed: {last_error[:100]}")
                continue
        
        if translated:
            translated_parts.append(translated)
        else:
            # All models failed for this part - use original
            print(f"      ⚠ All models failed, using original text")
            translated_parts.append(f"[翻译失败]\n\n{part}")
            return '\n\n'.join(translated_parts), "none", False
    
    # Combine all parts
    final_translation = '\n\n'.join(translated_parts)
    return final_translation, successful_model or "none", True


def translate_email(email_content: Dict[str, Any]) -> Dict[str, Any]:
    """
    Translate email content to Chinese summary.
    
    Args:
        email_content: Dict with subject, body, from, received_at
        
    Returns:
        Dict with original and translated content, including word/char counts
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
    
    # Extract article content from body
    article_content = extract_article_content(body, subject)
    
    # Count English words in original
    english_word_count = count_words(article_content) if article_content else 0
    
    if not article_content:
        # No content to translate
        return {
            "id": email_content.get("id"),
            "original_sender": sender_info,
            "original_subject": subject,
            "original_time": received_at,
            "original_body": body[:500],
            "translated_subject": subject,
            "translated_body": "[无正文内容]",
            "model_used": "none",
            "success": False,
            "english_word_count": 0,
            "chinese_char_count": 0
        }
    
    # Translate the article
    translated, model_used, success = translate_article(article_content)
    
    # Count Chinese characters in translation
    chinese_char_count = len(translated.replace('\n', '').replace(' ', '')) if translated else 0
    
    return {
        "id": email_content.get("id"),
        "original_sender": sender_info,
        "original_subject": subject,
        "original_time": received_at,
        "original_body": body[:500],
        "translated_subject": subject,
        "translated_body": translated,
        "model_used": model_used,
        "success": success,
        "english_word_count": english_word_count,
        "chinese_char_count": chinese_char_count
    }


def translate_emails_batch(emails: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Translate multiple emails in batch.
    Process one at a time with delay for rate limits.
    
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
        
        # Delay between requests
        if i < len(emails) - 1:
            time.sleep(2)
    
    return results
