#!/usr/bin/env python3
"""Send email via SMTP (AgentMail SMTP).

修改版：支持单封邮件发送，标题为"来源名 + 文章标题"
支持显示多段翻译实际使用的所有模型
"""

import re
import smtplib
import os
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
        is_html=False
    )


def build_single_email_body(translated_email: Dict[str, Any]) -> str:
    """
    构建单封邮件的内容。
    
    格式包含：
    - 原文信息（标题、发件人、时间）
    - 翻译内容
    - 字数统计和模型信息（显示所有实际使用的模型）
    """
    lines = []

    original_subject = translated_email.get('original_subject', '无主题')
    cleaned_title = re.sub(r'^[^：:]+[：:]\s*', '', original_subject).strip() or original_subject

    lines.append(f"📌 标题：{cleaned_title}")
    
    original_time = translated_email.get('original_time', '')
    beijing_time = ''
    if original_time:
        beijing_tz = timezone(timedelta(hours=8))
        try:
            dt = datetime.fromisoformat(original_time.replace('Z', '+00:00'))
            beijing_time = dt.astimezone(beijing_tz).strftime('%Y-%m-%d %H:%M 北京时间')
        except:
            beijing_time = original_time
    lines.append(f"🕐 时间：{beijing_time}")
    lines.append("")

    eng_words = translated_email.get('english_word_count', 0)
    ch_chars = translated_email.get('chinese_char_count', 0)
    if eng_words > 0:
        lines.append(f"📊 统计：英文 {eng_words} words → 中文 {ch_chars} chars")
    
    # 显示实际使用的所有模型
    models_used = translated_email.get('models_used', translated_email.get('model_used', 'N/A'))
    if models_used and models_used != 'none':
        # 如果有多个模型，用箭头连接表示先后顺序
        if ',' in models_used:
            model_list = [m.strip() for m in models_used.split(',')]
            models_display = ' → '.join(model_list)
            lines.append(f"🤖 翻译模型：{models_display}")
        else:
            lines.append(f"🤖 翻译模型：{models_used}")
    else:
        lines.append(f"🤖 翻译模型：N/A")
    lines.append("")

    lines.append("📝 翻译内容")
    lines.append("")
    lines.append(translated_email.get("translated_body", "[无内容]"))
    lines.append("")

    if translated_email.get("success"):
        lines.append("✅ 翻译成功")
    else:
        lines.append("⚠️ 翻译失败")

    lines.append("")
    lines.append("─" * 60)
    lines.append("由 Email Digest 自动发送")

    return "\n".join(lines)


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
        is_html=False
    )


def build_digest_body(translated_emails: List[Dict[str, Any]], errors: List[str] = None) -> str:
    """Build the digest email body from translated emails."""
    lines = []
    
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines.append(f"📧 邮件摘要 - {today}")
    lines.append(f"共 {len(translated_emails)} 封邮件")
    lines.append("")
    lines.append("=" * 60)
    lines.append("")
    
    for i, email in enumerate(translated_emails):
        lines.append(f"--- 📧 邮件 {i+1} ---")
        lines.append("")
        
        subject = email.get('original_subject', '无主题')
        eng_words = email.get('english_word_count', 0)
        ch_chars = email.get('chinese_char_count', 0)
        lines.append(f"📌 {subject}")
        if eng_words > 0:
            lines.append(f"   (英文 {eng_words} words → 中文 {ch_chars} chars)")
        lines.append("")
        
        lines.append(f"发件人: {email.get('original_sender', 'Unknown')}")
        lines.append(f"时间: {email.get('original_time', '')}")
        
        # 显示模型信息
        models_used = email.get('models_used', email.get('model_used', 'N/A'))
        if models_used and models_used != 'none':
            if ',' in models_used:
                model_list = [m.strip() for m in models_used.split(',')]
                models_display = ' → '.join(model_list)
                lines.append(f"翻译模型: {models_display}")
            else:
                lines.append(f"翻译模型: {models_used}")
        else:
            lines.append(f"翻译模型: N/A")
        lines.append("")
        
        body = email.get("translated_body", "")
        lines.append("翻译内容:")
        lines.append(body)
        lines.append("")
        
        if email.get("success"):
            lines.append("✅ 翻译成功")
        else:
            lines.append(f"⚠️ 翻译失败: {email.get('error', 'Unknown error')}")
        
        lines.append("")
        lines.append("-" * 40)
        lines.append("")
    
    if errors:
        lines.append("")
        lines.append("⚠️ 处理错误:")
        for error in errors:
            lines.append(f"  - {error}")
        lines.append("")
    
    lines.append("")
    lines.append("=" * 60)
    lines.append("由 Email Digest GitHub Actions 自动发送")
    
    return "\n".join(lines)


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