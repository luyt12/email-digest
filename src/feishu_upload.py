#!/usr/bin/env python3
"""Upload EPUB file to Feishu and send notification via bot.

Uses Feishu Open API to:
1. Get tenant_access_token
2. Upload file via im/v1/images (or drive/v1/files)
3. Send message to user via bot

For file upload, we use the im/v1/files API which supports
sending files as messages via the bot.
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
    url = "https://open.feishu.cn/open-apis/im/v1/messages"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json; charset=utf-8"
    }
    
    params = {
        "receive_id_type": receive_id_type
    }
    
    data = {
        "receive_id": receive_id,
        "msg_type": "file",
        "content": json.dumps({"file_key": file_key})
    }
    
    resp = requests.post(url, headers=headers, params=params, json=data, timeout=30)
    resp.raise_for_status()
    result = resp.json()
    
    if result.get("code") != 0:
        raise RuntimeError(f"Failed to send file message: {result}")
    
    print(f"File message sent to {receive_id_type}={receive_id}")
    return result


def send_card_message(
    token: str,
    receive_id: str,
    epub_info: dict,
    receive_id_type: str = "open_id"
) -> dict:
    """Send a notification card message via Feishu bot.
    
    Args:
        token: tenant_access_token
        receive_id: User open_id or chat_id
        epub_info: Dict with article_count, date, time, schedule_label
        receive_id_type: "open_id" or "chat_id"
    """
    url = "https://open.feishu.cn/open-apis/im/v1/messages"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json; charset=utf-8"
    }
    
    article_count = epub_info.get("article_count", 0)
    date_str = epub_info.get("date", "")
    time_str = epub_info.get("time", "")
    schedule_label = epub_info.get("schedule_label", "")
    
    schedule_line = f'<div style="font-size:12px;color:#999;">时段: {schedule_label}</div>' if schedule_label else ''
    
    msg_content = {
        "config": {"wide_screen_mode": True},
        "header": {
            "title": {
                "tag": "plain_text",
                "content": "📰 邮件摘要已生成"
            },
            "template": "blue"
        },
        "elements": [
            {
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": f"📧 **{date_str} {time_str}**\n共 **{article_count}** 篇文章"
                }
            }
        ]
    }
    
    if schedule_label:
        msg_content["elements"].append({
            "tag": "div",
            "text": {
                "tag": "lark_md",
                "content": f"时段: {schedule_label}"
            }
        })
    
    params = {"receive_id_type": receive_id_type}
    
    data = {
        "receive_id": receive_id,
        "msg_type": "interactive",
        "content": json.dumps(msg_content, ensure_ascii=False)
    }
    
    resp = requests.post(url, headers=headers, params=params, json=data, timeout=30)
    resp.raise_for_status()
    result = resp.json()
    
    if result.get("code") != 0:
        print(f"Warning: Failed to send card message: {result}")
    else:
        print(f"Card message sent to {receive_id_type}={receive_id}")
    
    return result


def upload_and_notify(
    epub_path: str,
    feishu_user_open_id: str = "",
    epub_info: dict = None
) -> dict:
    """Full pipeline: upload EPUB and send notification via Feishu bot.
    
    Environment variables required:
        FEISHU_APP_ID
        FEISHU_APP_SECRET
    
    Args:
        epub_path: Local path to EPUB file
        feishu_user_open_id: User open_id to send notification to
        epub_info: Dict with article_count, date, time, schedule_label
    
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
    if feishu_user_open_id:
        file_msg_result = send_file_message(
            token=token,
            receive_id=feishu_user_open_id,
            file_key=file_key
        )
    
    # Step 4: Send card notification
    card_result = None
    if feishu_user_open_id and epub_info:
        card_result = send_card_message(
            token=token,
            receive_id=feishu_user_open_id,
            epub_info=epub_info
        )
    
    return {
        "file_key": file_key,
        "file_message": file_msg_result,
        "card_message": card_result
    }


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python feishu_upload.py <epub_path> [user_open_id]")
        sys.exit(1)
    
    epub_file = sys.argv[1]
    user_id = sys.argv[2] if len(sys.argv) > 2 else ""
    
    result = upload_and_notify(
        epub_path=epub_file,
        feishu_user_open_id=user_id,
        epub_info={"article_count": 0, "date": "test", "time": "test"}
    )
    
    print(json.dumps(result, indent=2, ensure_ascii=False))
