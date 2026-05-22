#!/usr/bin/env python3
"""Upload EPUB file to Feishu and send notification via bot.

Uses Feishu Open API to:
1. Get tenant_access_token
2. Upload file via im/v1/files
3. Send file message to user via bot
4. Send text notification with article list

Updated: Use FEISHU_RECEIVE_ID (consistent with journal-weekly-delivery)
"""

import os
import json
import requests
from typing import Optional


def get_tenant_access_token(app_id: str, app_secret: str) -> str:
    """Get Feishu tenant_access_token."""
    url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
    headers = {"Content-Type": "application/json; charset=utf-8"}
    data = {
        "app_id": app_id,
        "app_secret": app_secret
    }
    
    resp = requests.post(url, headers=headers, json=data, timeout=30)
    resp.raise_for_status()
    result = resp.json()
    
    if result.get("code") != 0:
        raise RuntimeError(f"Failed to get tenant_access_token: {result}")
    
    token = result.get("tenant_access_token")
    if not token:
        raise RuntimeError(f"No tenant_access_token in response: {result}")
    
    print(f"Got tenant_access_token: {token[:8]}...")
    return token


def upload_file_as_message(token: str, file_path: str) -> str:
    """Upload a file to Feishu for sending as a message.
    
    Uses the im/v1/files API which allows sending files up to 30MB
    as message attachments.
    
    Returns:
        file_key for use in message sending
    """
    url = "https://open.feishu.cn/open-apis/im/v1/files"
    headers = {
        "Authorization": f"Bearer {token}"
    }
    
    file_name = os.path.basename(file_path)
    file_size = os.path.getsize(file_path)
    
    print(f"Uploading file: {file_name} ({file_size} bytes)")
    
    with open(file_path, 'rb') as f:
        files = {
            "file_type": (None, "stream"),  # stream = generic file
            "file_name": (None, file_name),
            "file": (file_name, f, "application/epub+zip")
        }
        
        resp = requests.post(url, headers=headers, files=files, timeout=120)
        resp.raise_for_status()
        result = resp.json()
    
    if result.get("code") != 0:
        raise RuntimeError(f"Failed to upload file: {result}")
    
    file_key = result.get("data", {}).get("file_key")
    if not file_key:
        raise RuntimeError(f"No file_key in response: {result}")
    
    print(f"File uploaded, file_key: {file_key}")
    return file_key


def send_file_message(
    token: str,
    receive_id: str,
    file_key: str,
    receive_id_type: str = "open_id"
) -> dict:
    """Send a file message to user via Feishu bot.
    
    Args:
        token: tenant_access_token
        receive_id: User open_id or chat_id
        file_key: File key from upload
        receive_id_type: "open_id" or "chat_id"
    """
    url = f"https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type={receive_id_type}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    data = {
        "receive_id": receive_id,
        "msg_type": "file",
        "content": json.dumps({"file_key": file_key})
    }
    
    resp = requests.post(url, headers=headers, json=data, timeout=30)
    
    # Log full response for debugging
    try:
        result = resp.json()
    except:
        print(f"Failed to parse response as JSON: {resp.text}")
        resp.raise_for_status()
    
    if resp.status_code >= 400:
        print(f"Feishu API error: HTTP {resp.status_code} - {result}")
        resp.raise_for_status()
    
    if result.get("code") != 0:
        raise RuntimeError(f"Failed to send file message: {result}")
    
    print(f"File message sent to {receive_id_type}={receive_id}")
    return result


def send_text_message(
    token: str,
    receive_id: str,
    text: str,
    receive_id_type: str = "open_id"
) -> dict:
    """Send a plain text message via Feishu bot.
    
    Args:
        token: tenant_access_token
        receive_id: User open_id or chat_id
        text: Text content to send
        receive_id_type: "open_id" or "chat_id"
    """
    url = f"https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type={receive_id_type}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    data = {
        "receive_id": receive_id,
        "msg_type": "text",
        "content": json.dumps({"text": text}, ensure_ascii=False)
    }
    
    resp = requests.post(url, headers=headers, json=data, timeout=30)
    
    # Log full response for debugging
    try:
        result = resp.json()
    except:
        print(f"Failed to parse response as JSON: {resp.text}")
        resp.raise_for_status()
    
    if resp.status_code >= 400:
        print(f"Feishu API error: HTTP {resp.status_code} - {result}")
        resp.raise_for_status()
    
    if result.get("code") != 0:
        print(f"Warning: Failed to send text message: {result}")
    else:
        print(f"Text message sent to {receive_id_type}={receive_id}")
    
    return result


def upload_and_notify(
    epub_path: str,
    feishu_receive_id: str = "",
    epub_info: dict = None,
    translated_emails: list = None
) -> dict:
    """Full pipeline: upload EPUB and send notification via Feishu bot.
    
    Environment variables required:
        FEISHU_APP_ID
        FEISHU_APP_SECRET
    
    Args:
        epub_path: Local path to EPUB file
        feishu_receive_id: User open_id to send notification to
        epub_info: Dict with article_count, date, time, schedule_label
        translated_emails: List of translated email dicts (for article list)
    
    Returns:
        Dict with upload and notification results
    """
    app_id = os.environ.get("FEISHU_APP_ID", "")
    app_secret = os.environ.get("FEISHU_APP_SECRET", "")
    
    if not app_id or not app_secret:
        raise RuntimeError("FEISHU_APP_ID and FEISHU_APP_SECRET environment variables are required")
    
    # Step 1: Get access token
    token = get_tenant_access_token(app_id, app_secret)
    
    # Step 2: Upload file
    file_key = upload_file_as_message(token=token, file_path=epub_path)
    
    # Step 3: Send file message to user
    file_msg_result = None
    if feishu_receive_id:
        print(f"Sending file message to receive_id: {feishu_receive_id[:10]}...")
        file_msg_result = send_file_message(
            token=token,
            receive_id=feishu_receive_id,
            file_key=file_key
        )
    else:
        print("Warning: feishu_receive_id is empty, skipping file message")
    
    # Step 4: Send text notification with article list
    text_result = None
    if feishu_receive_id and epub_info:
        article_count = epub_info.get("article_count", 0)
        date_str = epub_info.get("date", "")
        time_str = epub_info.get("time", "")
        
        # Build article list text
        lines = [f"📰 邮件摘要 {date_str} {time_str}，共 {article_count} 篇文章"]
        
        if translated_emails:
            for idx, email in enumerate(translated_emails, 1):
                subject = email.get('translated_subject') or email.get('original_subject', '无标题')
                author = email.get('author', '')
                if author:
                    lines.append(f"{idx}. {subject}（{author}）")
                else:
                    lines.append(f"{idx}. {subject}")
        
        text_content = "\n".join(lines)
        text_result = send_text_message(
            token=token,
            receive_id=feishu_receive_id,
            text=text_content
        )
    
    return {
        "file_key": file_key,
        "file_message": file_msg_result,
        "text_message": text_result
    }


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python feishu_upload.py <epub_path> [receive_id]")
        sys.exit(1)
    
    epub_file = sys.argv[1]
    receive_id = sys.argv[2] if len(sys.argv) > 2 else ""
    
    result = upload_and_notify(
        epub_path=epub_file,
        feishu_receive_id=receive_id,
        epub_info={"article_count": 0, "date": "test", "time": "test"}
    )
    
    print(json.dumps(result, indent=2, ensure_ascii=False))
