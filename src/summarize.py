#!/usr/bin/env python3
"""LLM summarization and translation of emails.

Translation logic:
1. Translate the email subject (title)
2. Extract article content from email body (ignore ads, footers, etc.)
3. For long articles (>2000 words), split by natural paragraphs
4. Translate each part with fallback model chain
5. Validate translation result (Chinese char count vs English word count)
6. Track all models used across segments (for accurate model attribution)
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


# Title translation prompt
TITLE_PROMPT = """你是一个专业的标题翻译助手。

任务：将以下英文邮件标题翻译成中文。

翻译原则：
1. 保持简洁，准确传达原标题的核心含义
2. 如果标题中包含专有名词（人名、地名、机构名、书名等），在翻译后用括号标注原文
3. 常见公众人物（如 Biden, Trump, Xi 等）和常见地名（如 US, China, New York 等）无需标注原文
4. 如果原标题本身包含中文字符，保留原样

英文标题：
{title}

请直接提供中文翻译，不要添加任何解释或说明。"""


# Summary translation prompt (80% compression ratio)
SUMMARY_PROMPT = """你是一个专业的文章摘要翻译助手。

任务：将以下英文文章内容翻译成中文摘要。

翻译原则：
1. 中文摘要的字数应约为英文原文单词数的80%
2. 保留文章的核心观点、关键事实和重要细节
3. 使用流畅、专业的中文表达
4. 保持原文的专业术语准确性
5. **专有名词标注**：如果正文中出现了引用的书名、并非日常出现在新闻报道中的非公众人物人名、地名等专有名词，在翻译后用括号标出原文，例如："《人类简史》（Sapiens: A Brief History of Humankind）"、"作家约翰·史密斯（John Smith）"、"柏林（Berlin）"等。常见公众人物（如拜登、特朗普、习近平等）和常见地名（如美国、中国、纽约等）无需标注原文。

英文文章内容（共 {word_count} 个英文单词）：
{content}

请直接提供中文摘要，不要添加任何解释或说明。"""


def count_words(text: str) -> int:
    """Count words in text (approximate for mixed content)."""
    words = text.split()
    return len(words)


def extract_author(body: str) -> str:
    """
    Extract article author from email body text.
    Looks for common author attribution patterns at the beginning of the article.
    
    Supported patterns:
    - "By John Smith" (NYT, New Yorker, most outlets)
    - "By J. Smith" (initials)
    - "By John Smith and Jane Doe" (multiple authors)
    - "— FirstName LastName" (The Atlantic style)
    - "Author: FirstName LastName"
    - "Text by FirstName LastName"
    - "Reported by FirstName LastName"
    - "Written by FirstName LastName"
    
    Returns author name string or empty string if not found.
    """
    if not body:
        return ""
    
    # Get first 800 chars to look for author
    first_part = body[:800]
    
    # Pattern 1: "By Name" - most common
    by_match = re.search(r'^\s*By\s+([A-Z][A-Za-z\s\.\-\']{2,60}),?\s*(?:and|,|$)', first_part, re.MULTILINE)
    if by_match:
        return by_match.group(1).strip()
    
    # Pattern 2: "— Name" or "– Name" or "- Name"
    dash_match = re.search(r'^\s*[—–-]\s*([A-Z][A-Za-z\s\.\-\']{2,60}),?\s*(?:and|,|$)', first_part, re.MULTILINE)
    if dash_match:
        return dash_match.group(1).strip()
    
    # Pattern 3: "Author: Name"
    author_match = re.search(r'^\s*Author:\s*([A-Z][A-Za-z\s\.\-\']{2,60})', first_part, re.MULTILINE | re.IGNORECASE)
    if author_match:
        return author_match.group(1).strip()
    
    # Pattern 4: "Text by Name" / "Written by Name" / "Reported by Name"
    text_by_match = re.search(r'^(?:Text|Written|Reported)\s+by\s+([A-Z][A-Za-z\s\.\-\']{2,60})', first_part, re.MULTILINE | re.IGNORECASE)
    if text_by_match:
        return text_by_match.group(1).strip()
    
    return ""


def translate_title(title: str) -> Tuple[str, bool]:
    """
    Translate email subject/title to Chinese.
    
    Returns:
        Tuple of (translated_title, success)
    """
    if not title or not title.strip():
        return title, False
    
    # Check if title already contains significant Chinese
    chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', title))
    if chinese_chars > len(title) * 0.3:
        # Already mostly Chinese, return as-is
        return title, True
    
    prompt = TITLE_PROMPT.format(title=title)
    
    for model in MODEL_CHAIN:
        try:
            api_url = get_api_url_for_model(model)
            api_key = get_api_key_for_model(model)
            
            if not api_key:
                continue
            
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            }
            
            if "openrouter" in api_url:
                headers["HTTP-Referer"] = "https://github.com/luyt12/email-digest"
                headers["X-Title"] = "Email Digest"
            
            payload = {
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 200,
                "temperature": 0.3
            }
            
            response = requests.post(
                api_url,
                headers=headers,
                json=payload,
                timeout=30
            )
            
            if response.status_code != 200:
                continue
            
            data = response.json()
            result = None
            
            if "choices" in data and data["choices"]:
                result = data["choices"][0].get("message", {}).get("content", "")
            elif "output" in data:
                result = data["output"]
            
            if result and result.strip():
                translated = result.strip()
                # Basic validation: should have some Chinese characters
                if len(re.findall(r'[\u4e00-\u9fff]', translated)) > 0:
                    print(f"    Title translated with {model}")
                    return translated, True
        except Exception as e:
            print(f"    Title translation failed with {model}: {str(e)[:50]}")
            continue
    
    # All models failed, return original
    print(f"    Title translation failed, using original")
    return title, False


def split_by_paragraphs(text: str, max_words: int = 2000) -> List[str]:
    """
    Split text into parts by natural paragraphs, each part <= max_words.
    """
    paragraphs = re.split(r'\n\s*\n|\n', text.strip())
    paragraphs = [p.strip() for p in paragraphs if p.strip()]
    
    if not paragraphs:
        return [text] if text.strip() else []
    
    parts = []
    current_part = []
    current_words = 0
    
    for para in paragraphs:
        para_words = count_words(para)
        
        if para_words > max_words:
            if current_part:
                parts.append('\n\n'.join(current_part))
                current_part = []
                current_words = 0
            parts.append(para)
            continue
        
        if current_words + para_words > max_words:
            if current_part:
                parts.append('\n\n'.join(current_part))
            current_part = [para]
            current_words = para_words
        else:
            current_part.append(para)
            current_words += para_words
    
    if current_part:
        parts.append('\n\n'.join(current_part))
    
    return parts


def extract_article_content(body: str, subject: str = "") -> str:
    """
    Extract article content from email body.
    Remove ads, footers, signatures, and other non-content.
    """
    if not body:
        return ""
    
    remove_patterns = [
        r'\[Unsubscribe\].*',
        r'Click here to unsubscribe.*',
        r'To unsubscribe.*',
        r'取消订阅.*',
        r'\[View in browser\].*',
        r'View this email in your browser.*',
        r'Follow us on.*',
        r'Connect with us.*',
        r'---+\s*$',
        r'___+\s*$',
        r'\*\*\*+\s*$',
        r'Copyright ©.*',
        r'© \d{4}.*',
        r'Powered by.*',
    ]
    
    text = body
    
    for pattern in remove_patterns:
        text = re.sub(pattern, '', text, flags=re.IGNORECASE | re.MULTILINE)
    
    lines = text.split('\n')
    content_lines = []
    footer_started = False
    
    for i, line in enumerate(lines):
        stripped = line.strip()
        
        if not content_lines and not stripped:
            continue
        
        if any([
            stripped.startswith('--'),
            stripped.startswith('Best,'),
            stripped.startswith('Regards,'),
            stripped.startswith('Thanks,'),
            stripped.startswith('Thank you,'),
            stripped.startswith('Sincerely,'),
            re.match(r'^\w+\s*$', stripped) and i > len(lines) - 5,
        ]):
            footer_started = True
        
        if not footer_started:
            content_lines.append(line)
    
    content = '\n'.join(content_lines)
    content = re.sub(r'\n{3,}', '\n\n', content)
    content = content.strip()
    
    return content


def validate_translation(original_word_count: int, translated_text: str) -> bool:
    """
    Validate translation result quality.
    
    Checks if the Chinese character count is reasonable compared to the original
    English word count. If the ratio is too low, the translation likely failed
    (e.g., model returned empty content, garbage, or only a partial translation).
    
    Threshold: translated chars should be at least 30% of original word count.
    This is a conservative threshold to catch extreme failures like:
        1889 English words → 58 Chinese characters (ratio ~0.03)
    
    Returns:
        True if translation seems valid, False otherwise.
    """
    if not translated_text or not translated_text.strip():
        print(f"      ⚠ Validation failed: empty translation")
        return False
    
    # Count Chinese characters (CJK Unified Ideographs)
    chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', translated_text))
    
    # Also count all non-space characters as fallback (for mixed content)
    non_space_chars = len(re.sub(r'\s', '', translated_text))
    
    # Use the larger of chinese_chars and non_space_chars for validation
    char_count = max(chinese_chars, non_space_chars)
    
    # Threshold: translated chars should be at least 30% of original word count
    min_chars = original_word_count * 0.3
    
    if char_count < min_chars:
        print(f"      ⚠ Translation validation failed: {char_count} chars < {min_chars:.0f} min (ratio {char_count/original_word_count:.2f})")
        return False
    
    print(f"      ✓ Translation validation passed: {char_count} chars / {original_word_count} words (ratio {char_count/original_word_count:.2f})")
    return True


def translate_part_with_model(
    content: str, 
    model: str, 
    word_count: int
) -> str:
    """
    Translate a single part with a specific model.
    Automatically selects the correct API endpoint based on model provider.
    """
    prompt = SUMMARY_PROMPT.format(
        word_count=word_count,
        content=content
    )
    
    api_url = get_api_url_for_model(model)
    api_key = get_api_key_for_model(model)
    
    if not api_key:
        raise Exception(f"No API key configured for model {model}")
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    if "openrouter" in api_url:
        headers["HTTP-Referer"] = "https://github.com/luyt12/email-digest"
        headers["X-Title"] = "Email Digest"
    
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
    
    result = None
    if "choices" in data:
        choices = data["choices"]
        if choices and len(choices) > 0:
            result = choices[0].get("message", {}).get("content", "")
    
    if not result and "output" in data:
        result = data["output"]
    
    if not result or not result.strip():
        raise Exception(f"API returned empty content for model {model}")
    
    return result


def translate_article(content: str) -> Tuple[str, str, bool]:
    """
    Translate an article with paragraph splitting and model fallback.
    
    Returns:
        Tuple of (translated_text, models_used_summary, success)
    
    models_used_summary: comma-separated list of models actually used,
                        e.g. "minimaxai/minimax-m2.7" (single) or
                        "minimaxai/minimax-m2.7, openrouter/free" (multiple)
    """
    if not content or not content.strip():
        return "", "none", False
    
    word_count = count_words(content)
    print(f"    Article word count: {word_count}")
    
    parts = split_by_paragraphs(content, max_words=2000)
    print(f"    Split into {len(parts)} part(s)")
    
    translated_parts = []
    models_used = []      # Track all models actually used (preserving order)
    successful_model = None
    
    for i, part in enumerate(parts):
        part_words = count_words(part)
        print(f"    Part {i+1}/{len(parts)}: {part_words} words")
        
        translated = None
        last_error = None
        
        # Build model priority list:
        # - First segment: try MODEL_CHAIN in order
        # - Subsequent segments: sticky model first, then MODEL_CHAIN as fallback
        if not successful_model:
            models_to_try = MODEL_CHAIN
        else:
            models_to_try = [successful_model] + [m for m in MODEL_CHAIN if m != successful_model]
        
        for model in models_to_try:
            try:
                translated = translate_part_with_model(part, model, part_words)
                
                # Validate translation result
                if not validate_translation(part_words, translated):
                    raise Exception(f"Translation validation failed for model {model}")
                
                if not successful_model:
                    successful_model = model
                # Always track model usage (deduplicated later for display)
                if model not in models_used:
                    models_used.append(model)
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
            models_summary = ", ".join(models_used) if models_used else "none"
            return '\n\n'.join(translated_parts), models_summary, False
    
    final_translation = '\n\n'.join(translated_parts)
    models_summary = ", ".join(models_used) if models_used else "none"
    return final_translation, models_summary, True


def translate_email(email_content: Dict[str, Any]) -> Dict[str, Any]:
    """
    Translate email content to Chinese summary.
    """
    sender = email_content.get("from", {})
    if isinstance(sender, dict):
        sender_info = sender.get("name", "") or sender.get("email", "")
    else:
        sender_info = str(sender)
    
    subject = email_content.get("subject", "无主题")
    body = email_content.get("body", "")
    received_at = email_content.get("received_at", "")
    
    # Translate title first
    print(f"  Translating title: {subject[:50]}...")
    translated_subject, title_success = translate_title(subject)
    
    # Extract author from body before article content extraction
    author = extract_author(body)
    if author:
        print(f"    Found author: {author}")
    
    article_content = extract_article_content(body, subject)
    english_word_count = count_words(article_content) if article_content else 0
    
    if not article_content:
        return {
            "id": email_content.get("id"),
            "original_sender": sender_info,
            "original_subject": subject,
            "original_time": received_at,
            "original_body": body[:500],
            "translated_subject": translated_subject,
            "translated_body": "[无正文内容]",
            "author": author,
            "models_used": "none",
            "success": False,
            "english_word_count": 0,
            "chinese_char_count": 0,
            "media_urls": email_content.get("media_urls", [])
        }
    
    translated, models_used, success = translate_article(article_content)
    chinese_char_count = len(translated.replace('\n', '').replace(' ', '')) if translated else 0
    
    return {
        "id": email_content.get("id"),
        "original_sender": sender_info,
        "original_subject": subject,
        "original_time": received_at,
        "original_body": body[:500],
        "translated_subject": translated_subject,
        "translated_body": translated,
        "models_used": models_used,
        "success": success,
        "english_word_count": english_word_count,
        "chinese_char_count": chinese_char_count,
        "author": author,
        "media_urls": email_content.get("media_urls", [])
    }


def translate_emails_batch(emails: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Translate multiple emails in batch.
    """
    results = []
    
    for i, email in enumerate(emails):
        print(f"  Translating email {i+1}/{len(emails)}...")
        
        result = translate_email(email)
        results.append(result)
        
        if i < len(emails) - 1:
            time.sleep(2)
    
    return results
