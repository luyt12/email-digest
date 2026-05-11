#!/usr/bin/env python3
"""Send email via SMTP (AgentMail SMTP).

修改版：支持单封邮件发送，标题为"来源名 + 文章标题"
支持显示多段翻译实际使用的所有模型
支持嵌入 Media files 图片
"""

import re
import smtplib
import os
import urllib.parse
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any

from config import SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD


def send_single_email(
    target_email: str,
    translated_email: Dict[str, Any],
    subject: str = None
):
    """
    发送单封翻译后的邮件。
    """
    body = build_single_email_body(translated_email)
    
    if subject is None:
        sender = translated_email.get("original_sender", "Unknown")
        article_title = translated_email.get("original_subject", "无主题")
        subject = f"{sender} - {article_title}"
    
    inbox_email = os.environ.get("AGENTMAIL_INBOX_EMAIL", "excitedsilver931@agentmail.to")
    from_email = os.environ.get("AGENTMAIL_FROM_EMAIL", inbox_email)
    
    send_email_smtp(
        from_email=from_email,
        to_email=target_email,
        subject=subject,
        body=body,
        is_html=True  # Use HTML to support images
    )


def _escape_html(text: str) -> str:
    """Escape HTML special characters."""
    text = text.replace('&', '&amp;')
    text = text.replace('<', '&lt;')
    text = text.replace('>', '&gt;')
    text = text.replace('"', '&quot;')
    return text


def build_single_email_body(translated_email: Dict[str, Any]) -> str:
    """
    构建单封邮件的 HTML 内容。
    
    格式：
    - 标题
    - 图片（Media files，如果有）
    - 正文（翻译内容）
    - 统计信息和模型标注
    """
    original_subject = translated_email.get('original_subject', '无标题')
    cleaned_title = re.sub(r'^[^：:]+[：:]\s*', '', original_subject).strip() or original_subject

    # Start HTML document
    html_parts = []
    html_parts.append('<!DOCTYPE html>')
    html_parts.append('<html><head><meta charset="UTF-8">')
    html_parts.append('<style>')
    html_parts.append('  body { font-family: -apple-system, "Microsoft YaHei", Arial, sans-serif; margin: 0; padding: 16px; background: #f5f5f5; }')
    html_parts.append('  .container { max-width: 680px; margin: 0 auto; background: white; border-radius: 8px; overflow: hidden; box-shadow: 0 1px 4px rgba(0,0,0,0.08); }')
    html_parts.append('  .header { background: #1a237e; color: white; padding: 16px 20px; }')
    html_parts.append('  .header h1 { margin: 0 0 4px 0; font-size: 18px; }')
    html_parts.append('  .meta { font-size: 12px; opacity: 0.85; }')
    html_parts.append('  .media-section { padding: 0 20px; }')
    html_parts.append('  .media-section img { max-width: 100%; height: auto; border-radius: 4px; margin-bottom: 8px; display: block; }')
    html_parts.append('  .content { padding: 20px; font-size: 15px; line-height: 1.8; color: #333; }')
    html_parts.append('  .content p { margin: 0 0 12px 0; }')
    html_parts.append('  .footer { padding: 12px 20px; background: #fafafa; font-size: 11px; color: #999; text-align: center; border-top: 1px solid #eee; }')
    html_parts.append('  .stats { font-size: 12px; color: #888; }')
    html_parts.append('  .model-tag { color: #1565c0; }')
    html_parts.append('  .fail-tag { color: #c0392b; font-style: italic; }')
    html_parts.append('</style>')
    html_parts.append('</head><body>')
    html_parts.append('<div class="container">')
    
    # Header - Title
    html_parts.append('<div class="header">')
    html_parts.append(f'  <h1>{_escape_html(cleaned_title)}</h1>')
    
    # Meta info
    meta_items = []
    
    original_time = translated_email.get('original_time', '')
    beijing_time = ''
    if original_time:
        beijing_tz = timezone(timedelta(hours=8))
        try:
            dt = datetime.fromisoformat(original_time.replace('Z', '+00:00'))
            beijing_time = dt.astimezone(beijing_tz).strftime('%Y-%m-%d %H:%M 北京时间')
        except:
            beijing_time = original_time
    if beijing_time:
        meta_items.append(f'🕐 {_escape_html(beijing_time)}')
    
    eng_words = translated_email.get('english_word_count', 0)
    ch_chars = translated_email.get('chinese_char_count', 0)
    if eng_words > 0:
        meta_items.append(f'📊 英文 {eng_words} words → 中文 {ch_chars} chars')
    
    # Model info
    models_used = translated_email.get('models_used', translated_email.get('model_used', 'N/A'))
    if models_used and models_used != 'none':
        if ',' in models_used:
            model_list = [m.strip() for m in models_used.split(',')]
            models_display = ' → '.join(model_list)
        else:
            models_display = models_used
        meta_items.append(f'🤖 <span class="model-tag">{_escape_html(models_display)}</span>')
    
    html_parts.append(f'  <div class="meta">{" &nbsp;|&nbsp; ".join(meta_items)}</div>')
    html_parts.append('</div>')  # close header
    
    # Media files section - BEFORE content (图片在正文正上方)
    media_urls = translated_email.get('media_urls', [])
    if media_urls:
        html_parts.append('<div class="media-section" style="padding-top: 16px;">')
        for url in media_urls:
            html_parts.append(f'<img src="{_escape_html(url)}" alt="Media" loading="lazy" />')
        html_parts.append('</div>')
    
    # Content (translated body) - 正文在图片下方
    html_parts.append('<div class="content">')
    translated_body = translated_email.get("translated_body", "[无内容]")
    paragraphs = translated_body.split('\n\n')
    for para in paragraphs:
        para = para.strip()
        if para:
            para = para.replace('\n', '<br>')
            html_parts.append(f'<p>{para}</p>')
    html_parts.append('</div>')  # close content
    
    # Footer
    html_parts.append('<div class="footer">')
    if translated_email.get("success"):
        html_parts.append('✅ 翻译成功 &nbsp;|&nbsp; ')
    else:
        html_parts.append('<span class="fail-tag">⚠️ 翻译失败</span> &nbsp;|&nbsp; ')
    html_parts.append('由 Email Digest 自动发送')
    html_parts.append('</div>')
    
    html_parts.append('</div>')  # close container
    html_parts.append('</body></html>')
    
    return '\n'.join(html_parts)


def send_digest_email(
    target_email: str,
    translated_emails: List[Dict[str, Any]],
    errors: List[str] = None,
    from_email: str = None
):
    """
    Send a digest email with translated content.
    """
    if errors is None:
        errors = []
    
    body = build_digest_body(translated_emails, errors)
    
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    subject = f"[邮件摘要] {today} - {len(translated_emails)} 封邮件"
    
    if from_email is None:
        inbox_email = os.environ.get("AGENTMAIL_INBOX_EMAIL", "excitedsilver931@agentmail.to")
        from_email = os.environ.get("AGENTMAIL_FROM_EMAIL", inbox_email)
    
    send_email_smtp(
        from_email=from_email,
        to_email=target_email,
        subject=subject,
        body=body,
        is_html=True
    )


def build_digest_body(translated_emails: List[Dict[str, Any]], errors: List[str] = None) -> str:
    """Build the digest email HTML body from translated emails."""
    html_parts = []
    
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    html_parts.append('<!DOCTYPE html>')
    html_parts.append('<html><head><meta charset="UTF-8">')
    html_parts.append('<style>')
    html_parts.append('  body { font-family: -apple-system, "Microsoft YaHei", Arial, sans-serif; margin: 0; padding: 16px; background: #f5f5f5; }')
    html_parts.append('  .container { max-width: 680px; margin: 0 auto; background: white; border-radius: 8px; overflow: hidden; box-shadow: 0 1px 4px rgba(0,0,0,0.08); }')
    html_parts.append('  .header { background: #1a237e; color: white; padding: 16px 20px; text-align: center; }')
    html_parts.append('  .header h1 { margin: 0 0 4px 0; font-size: 20px; }')
    html_parts.append('  .article { padding: 16px 20px; border-bottom: 1px solid #f0f0f0; }')
    html_parts.append('  .article:last-of-type { border-bottom: none; }')
    html_parts.append('  .article h2 { font-size: 16px; color: #1a1a1a; margin: 0 0 8px 0; }')
    html_parts.append('  .article .meta { font-size: 12px; color: #888; margin-bottom: 8px; }')
    html_parts.append('  .article .media img { max-width: 100%; height: auto; border-radius: 4px; margin: 8px 0; display: block; }')
    html_parts.append('  .article .content { font-size: 14px; line-height: 1.7; color: #333; }')
    html_parts.append('  .article .content p { margin: 0 0 8px 0; }')
    html_parts.append('  .footer { padding: 12px 20px; background: #fafafa; font-size: 11px; color: #999; text-align: center; border-top: 1px solid #eee; }')
    html_parts.append('</style>')
    html_parts.append('</head><body>')
    html_parts.append('<div class="container">')
    
    html_parts.append('<div class="header">')
    html_parts.append(f'<h1>📧 邮件摘要</h1>')
    html_parts.append(f'<div style="font-size:13px;opacity:0.85">{today} &nbsp;|&nbsp; {len(translated_emails)} 封邮件</div>')
    html_parts.append('</div>')
    
    for i, email in enumerate(translated_emails):
        html_parts.append('<div class="article">')
        
        subject = email.get('original_subject', '无主题')
        html_parts.append(f'<h2>{_escape_html(subject)}</h2>')
        
        # Meta
        meta_items = []
        eng_words = email.get('english_word_count', 0)
        ch_chars = email.get('chinese_char_count', 0)
        if eng_words > 0:
            meta_items.append(f'英文 {eng_words} words → 中文 {ch_chars} chars')
        
        models_used = email.get('models_used', email.get('model_used', 'N/A'))
        if models_used and models_used != 'none':
            if ',' in models_used:
                model_list = [m.strip() for m in models_used.split(',')]
                models_display = ' → '.join(model_list)
            else:
                models_display = models_used
            meta_items.append(f'模型: {_escape_html(models_display)}')
        
        sender = email.get('original_sender', 'Unknown')
        html_parts.append(f'<div class="meta">发件人: {_escape_html(sender)} | {" | ".join(meta_items)}</div>')
        
        # Media files (before content in digest too)
        media_urls = email.get('media_urls', [])
        if media_urls:
            html_parts.append('<div class="media">')
            for url in media_urls:
                html_parts.append(f'<img src="{_escape_html(url)}" alt="Media" loading="lazy" />')
            html_parts.append('</div>')
        
        # Content
        body = email.get("translated_body", "")
        html_parts.append('<div class="content">')
        paragraphs = body.split('\n\n')
        for para in paragraphs:
            para = para.strip()
            if para:
                para = para.replace('\n', '<br>')
                html_parts.append(f'<p>{para}</p>')
        html_parts.append('</div>')
        
        html_parts.append('</div>')  # close article
    
    if errors:
        html_parts.append('<div class="article">')
        html_parts.append('<h2>⚠️ 处理错误</h2>')
        for error in errors:
            html_parts.append(f'<p>{_escape_html(error)}</p>')
        html_parts.append('</div>')
    
    html_parts.append('<div class="footer">由 Email Digest GitHub Actions 自动发送</div>')
    html_parts.append('</div>')  # close container
    html_parts.append('</body></html>')
    
    return '\n'.join(html_parts)


def send_email_smtp(
    from_email: str,
    to_email: str,
    subject: str,
    body: str,
    is_html: bool = False,
    smtp_host: str = None,
    smtp_port: int = None,
    smtp_user: str = None,
    smtp_password: str = None
):
    """Send an email via SMTP."""
    smtp_host = smtp_host or SMTP_HOST
    smtp_port = smtp_port or SMTP_PORT
    smtp_user = smtp_user or SMTP_USER
    smtp_password = smtp_password or SMTP_PASSWORD
    
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = from_email
    msg["To"] = to_email
    
    if is_html:
        part = MIMEText(body, "html", "utf-8")
    else:
        part = MIMEText(body, "plain", "utf-8")
    
    msg.attach(part)
    
    with smtplib.SMTP_SSL(smtp_host, smtp_port) as server:
        server.login(smtp_user, smtp_password)
        server.send_message(msg)


def send_simple_email(
    to_email: str,
    subject: str,
    body: str,
    from_email: str = None
):
    """Send a simple text email."""
    if from_email is None:
        from_email = os.environ.get("AGENTMAIL_INBOX_EMAIL", "excitedsilver931@agentmail.to")
    
    send_email_smtp(from_email, to_email, subject, body)
