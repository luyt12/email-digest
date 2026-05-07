#!/usr/bin/env python3
"""Send email via SMTP (AgentMail SMTP)."""

import smtplib
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from datetime import datetime, timezone
from typing import List, Dict, Any

from config import SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD


def send_digest_email(
    target_email: str,
    translated_emails: List[Dict[str, Any]],
    errors: List[str] = None,
    from_email: str = None
):
    """
    Send a digest email with translated content.
    
    Args:
        target_email: Recipient email address
        translated_emails: List of translated email dicts
        errors: Optional list of error messages to include
        from_email: Sender email (optional, uses inbox email if not provided)
    """
    if errors is None:
        errors = []
    
    # Build email body
    body = build_digest_body(translated_emails, errors)
    
    # Subject
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    subject = f"[邮件摘要] {today} - {len(translated_emails)} 封邮件"
    
    # From address - should be inbox email (from INBOX_ID or env)
    if from_email is None:
        inbox_id = os.environ.get("AGENTMAIL_INBOX_ID", "")
        # INBOX_ID format: am_us_inbox_xxx -> extract email or construct
        from_email = os.environ.get("AGENTMAIL_FROM_EMAIL", "excitedsilver931@agentmail.to")
    
    # Send via SMTP
    send_email_smtp(
        from_email=from_email,
        to_email=target_email,
        subject=subject,
        body=body,
        is_html=False
    )


def build_digest_body(translated_emails: List[Dict[str, Any]], errors: List[str] = None) -> str:
    """
    Build the digest email body from translated emails.
    
    Args:
        translated_emails: List of translated email dicts
        errors: Optional list of errors
        
    Returns:
        Plain text body
    """
    lines = []
    
    # Header
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines.append(f"📧 邮件摘要 - {today}")
    lines.append(f"共 {len(translated_emails)} 封邮件")
    lines.append("")
    lines.append("=" * 60)
    lines.append("")
    
    # Each email
    for i, email in enumerate(translated_emails):
        lines.append(f"--- 📧 邮件 {i+1} ---")
        lines.append("")
        
        # Original info
        lines.append(f"发件人: {email.get('original_sender', 'Unknown')}")
        lines.append(f"主题: {email.get('original_subject', '无主题')}")
        lines.append(f"时间: {email.get('original_time', '')}")
        lines.append(f"使用模型: {email.get('model_used', 'N/A')}")
        lines.append("")
        
        # Body
        body = email.get("translated_body", "")
        lines.append("翻译内容:")
        lines.append(body)
        lines.append("")
        
        # Status indicator
        if email.get("success"):
            lines.append("✅ 翻译成功")
        else:
            lines.append(f"⚠️ 翻译失败: {email.get('error', 'Unknown error')}")
        
        lines.append("")
        lines.append("-" * 40)
        lines.append("")
    
    # Errors section
    if errors:
        lines.append("")
        lines.append("⚠️ 处理错误:")
        for error in errors:
            lines.append(f"  - {error}")
        lines.append("")
    
    # Footer
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
    """
    Send an email via SMTP.
    
    Args:
        from_email: Sender email address
        to_email: Recipient email address
        subject: Email subject
        body: Email body
        is_html: Whether body is HTML
        smtp_host: SMTP server host
        smtp_port: SMTP server port
        smtp_user: SMTP username
        smtp_password: SMTP password
    """
    # Use config defaults if not provided
    smtp_host = smtp_host or SMTP_HOST
    smtp_port = smtp_port or SMTP_PORT
    smtp_user = smtp_user or SMTP_USER
    smtp_password = smtp_password or SMTP_PASSWORD
    
    # Create message
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = from_email
    msg["To"] = to_email
    
    # Attach body
    if is_html:
        part = MIMEText(body, "html", "utf-8")
    else:
        part = MIMEText(body, "plain", "utf-8")
    
    msg.attach(part)
    
    # Send via SMTP_SSL
    with smtplib.SMTP_SSL(smtp_host, smtp_port) as server:
        server.login(smtp_user, smtp_password)
        server.send_message(msg)


def send_simple_email(
    to_email: str,
    subject: str,
    body: str,
    from_email: str = None
):
    """
    Send a simple text email.
    
    Args:
        to_email: Recipient
        subject: Subject
        body: Body text
        from_email: Sender (optional, uses inbox email)
    """
    if from_email is None:
        from_email = os.environ.get("AGENTMAIL_FROM_EMAIL", "excitedsilver931@agentmail.to")
    
    send_email_smtp(from_email, to_email, subject, body)