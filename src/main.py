#!/usr/bin/env python3
"""Email Digest - Fetch, translate and send email digests via GitHub Actions.

修改版：每次运行仅抓取上一个时间点之后的邮件，每封邮件单独发送。
"""

import os
import json
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from fetch_emails import fetch_recent_emails, get_message_content
from summarize import translate_email
from send_email import send_single_email
from utils import load_processed_ids, save_processed_ids, load_last_run_time, save_last_run_time


# 运行时间点配置（北京时间）
SCHEDULE_TIMES = [
    (4, 40),   # 04:40
    (8, 40),   # 08:40
    (13, 40),  # 13:40
    (16, 40),  # 16:40
    (19, 40),  # 19:40
    (23, 40),  # 23:40
]


def get_time_window():
    """
    计算当前运行的时间窗口。
    
    返回：(start_time, end_time) 北京时间的 datetime 对象
    
    逻辑：
    - 04:40 运行 → 抓取 0:00 ~ 04:40
    - 08:40 运行 → 抓取 4:41 ~ 08:40
    - 13:40 运行 → 抓取 8:41 ~ 13:40
    - ...
    """
    beijing_tz = timezone(timedelta(hours=8))
    now_beijing = datetime.now(beijing_tz)
    
    # 找到当前时间点属于哪个运行时间点
    current_hour = now_beijing.hour
    current_minute = now_beijing.minute
    
    # 找到最接近的运行时间点（允许误差 ±30 分钟）
    matched_schedule = None
    for i, (h, m) in enumerate(SCHEDULE_TIMES):
        # 计算时间差（分钟）
        schedule_minutes = h * 60 + m
        current_minutes = current_hour * 60 + current_minute
        diff = abs(schedule_minutes - current_minutes)
        
        if diff <= 30:  # 30分钟误差
            matched_schedule = i
            break
    
    if matched_schedule is None:
        # 没有匹配的时间点，可能是手动触发
        # 使用最近的一个时间点
        print(f"Warning: No matching schedule time found, using default window")
        matched_schedule = 0
    
    # 计算时间窗口
    schedule_hour, schedule_minute = SCHEDULE_TIMES[matched_schedule]
    
    # 结束时间：当前运行时间点
    end_time = now_beijing.replace(hour=schedule_hour, minute=schedule_minute, second=0, microsecond=0)
    
    # 开始时间：上一个时间点的下一分钟
    if matched_schedule == 0:
        # 第一个时间点 (04:40)，上一个时间点是 23:40（前一天）
        # 但对于 04:40，我们从当天 0:00 开始
        start_time = end_time.replace(hour=0, minute=0, second=0, microsecond=0)
    else:
        # 其他时间点
        prev_hour, prev_minute = SCHEDULE_TIMES[matched_schedule - 1]
        start_time = end_time.replace(hour=prev_hour, minute=prev_minute + 1, second=0, microsecond=0)
    
    return start_time, end_time


def main():
    """Main entry point for the email digest workflow."""
    print(f"[{datetime.now(timezone.utc).isoformat()}] Starting email digest...")
    
    # Load configuration
    api_key = os.environ.get("AGENTMAIL_API_KEY")
    inbox_email = os.environ.get("AGENTMAIL_INBOX_EMAIL", "excitedsilver931@agentmail.to")
    inbox_id = os.environ.get("AGENTMAIL_INBOX_ID", inbox_email)
    target_email = os.environ.get("TARGET_EMAIL")
    
    if not all([api_key, inbox_id, target_email]):
        print("Error: Missing required environment variables")
        print(f"  AGENTMAIL_API_KEY: {'set' if api_key else 'MISSING'}")
        print(f"  AGENTMAIL_INBOX_ID: {'set' if inbox_id else 'MISSING'}")
        print(f"  TARGET_EMAIL: {'set' if target_email else 'MISSING'}")
        sys.exit(1)
    
    # 计算时间窗口
    start_time, end_time = get_time_window()
    print(f"\n时间窗口: {start_time.strftime('%Y-%m-%d %H:%M')} ~ {end_time.strftime('%Y-%m-%d %H:%M')} (北京时间)")
    
    # Load processed email IDs
    processed_ids = load_processed_ids()
    print(f"Loaded {len(processed_ids)} previously processed email IDs")
    
    # Fetch recent emails
    print(f"\nFetching emails from inbox: {inbox_id}")
    all_messages = fetch_recent_emails(api_key, inbox_id, limit=100)
    print(f"Found {len(all_messages)} total messages")
    
    # Filter out SENT emails (from AgentMail itself)
    messages = []
    for m in all_messages:
        from_addr = m.get("from", "")
        if isinstance(from_addr, dict):
            from_email = from_addr.get("email", "")
        else:
            # Parse "Name <email>" format
            from_email = from_addr.split('<')[-1].split('>')[0] if '<' in from_addr else from_addr
        
        # Skip if sender is our own AgentMail address
        if from_email == inbox_email or from_email == "excitedsilver931@agentmail.to":
            continue
        if isinstance(from_addr, str) and inbox_email in from_addr:
            continue
        
        messages.append(m)
    
    print(f"Found {len(messages)} INBOX emails (excluding sent from AgentMail)")
    
    # Filter to emails within time window
    new_emails = []
    beijing_tz = timezone(timedelta(hours=8))
    
    for msg in messages:
        msg_id = msg.get("message_id") or msg.get("id")
        timestamp = msg.get("timestamp", "")
        
        # Skip already processed
        if msg_id in processed_ids:
            continue
        
        # Parse timestamp and check if within time window
        if timestamp:
            try:
                dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
                dt_beijing = dt.astimezone(beijing_tz)
                
                # Check if within time window
                if start_time <= dt_beijing <= end_time:
                    new_emails.append(msg)
                    print(f"  ✓ [{dt_beijing.strftime('%H:%M')}] {msg.get('subject', 'No subject')[:50]}")
            except Exception as e:
                print(f"Warning: Could not parse timestamp '{timestamp}': {e}")
                continue
    
    print(f"\n找到 {len(new_emails)} 封新邮件")
    
    if not new_emails:
        print("No new emails to process. Exiting.")
        return
    
    # Process each email and send individually
    for msg in new_emails:
        msg_id = msg.get("message_id") or msg.get("id")
        print(f"\n{'='*60}")
        print(f"处理邮件: {msg_id}")
        print(f"  主题: {msg.get('subject', 'No subject')}")
        print(f"  发件人: {msg.get('from', 'Unknown')}")
        
        try:
            # Get full message content
            content = get_message_content(api_key, inbox_id, msg_id)
            
            # Translate using LLM
            translated = translate_email(content)
            
            # 提取来源名称（发件人名称或邮箱前缀）
            sender = msg.get("from", {})
            if isinstance(sender, dict):
                sender_name = sender.get("name", "") or sender.get("email", "").split('@')[0]
            else:
                sender_name = str(sender).split('<')[0].strip() or str(sender).split('@')[0]
            
            # 文章标题
            article_title = msg.get("subject", "无主题")
            
            # 邮件标题：来源名 + 文章标题
            email_subject = f"{sender_name} - {article_title}"
            
            # Send individual email
            print(f"\n发送邮件: {email_subject}")
            send_single_email(target_email, translated, email_subject)
            print(f"✅ 邮件发送成功")
            
            # Mark as processed
            processed_ids.add(msg_id)
            
        except Exception as e:
            error_msg = f"Error processing {msg_id}: {str(e)}"
            print(f"❌ {error_msg}")
            # Still mark as processed to avoid infinite retries
            processed_ids.add(msg_id)
    
    # Save processed IDs
    save_processed_ids(processed_ids)
    print(f"\n{'='*60}")
    print(f"保存 {len(processed_ids)} 个已处理邮件 ID")
    print("完成！")


if __name__ == "__main__":
    main()
