#!/usr/bin/env python3
"""Email Digest - Fetch, translate and send email digests via GitHub Actions.

修改版：每次运行仅抓取上一个时间点之后的邮件，每封邮件单独发送。
支持手动指定时间窗口索引（用于补救触发）。
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
from utils import load_processed_ids, save_processed_ids


# 运行时间点配置（北京时间）
SCHEDULE_TIMES = [
    (4, 40),   # 0: 04:40 - 抓取 0:00 ~ 04:40
    (8, 40),   # 1: 08:40 - 抓取 4:41 ~ 08:40
    (13, 40),  # 2: 13:40 - 抓取 8:41 ~ 13:40
    (16, 40),  # 3: 16:40 - 抓取 13:41 ~ 16:40
    (19, 40),  # 4: 19:40 - 抓取 16:41 ~ 19:40
    (23, 40),  # 5: 23:40 - 抓取 19:41 ~ 23:40
]


def get_time_window_for_schedule(schedule_index):
    """
    根据时间窗口索引计算时间窗口。
    
    自动处理跨日补救：如果时间点在当前时间之后，说明是跨日补救，
    自动回退到前一天。
    
    Args:
        schedule_index: 0-5，对应 04:40, 08:40, 13:40, 16:40, 19:40, 23:40
        
    Returns:
        (start_time, end_time) 北京时间的 datetime 对象
    """
    beijing_tz = timezone(timedelta(hours=8))
    now_beijing = datetime.now(beijing_tz)
    
    schedule_hour, schedule_minute = SCHEDULE_TIMES[schedule_index]
    
    # 结束时间：时间点
    end_time = now_beijing.replace(hour=schedule_hour, minute=schedule_minute, second=0, microsecond=0)
    
    # 跨日补救：如果结束时间在当前时间之后，回退一天
    # 例如：次日 02:40 补救 23:40 → end_time 从次日 23:40 回退到前日 23:40
    if end_time > now_beijing:
        end_time -= timedelta(days=1)
    
    # 开始时间：上一个时间点的下一分钟
    if schedule_index == 0:
        # 第一个时间点 (04:40)，从当天 0:00 开始
        start_time = end_time.replace(hour=0, minute=0, second=0, microsecond=0)
    else:
        # 其他时间点
        prev_hour, prev_minute = SCHEDULE_TIMES[schedule_index - 1]
        start_time = end_time.replace(hour=prev_hour, minute=prev_minute, second=0, microsecond=0)
        # 加一分钟
        start_time = start_time + timedelta(minutes=1)
    
    return start_time, end_time


def get_time_window():
    """
    自动计算当前运行的时间窗口。
    
    Returns:
        (start_time, end_time, schedule_index) 北京时间的 datetime 对象
        schedule_index 为 None 表示手动触发（使用默认时间窗口）
    """
    beijing_tz = timezone(timedelta(hours=8))
    now_beijing = datetime.now(beijing_tz)
    
    current_hour = now_beijing.hour
    current_minute = now_beijing.minute
    
    # 找到最接近的运行时间点（允许误差 ±30 分钟）
    matched_schedule = None
    for i, (h, m) in enumerate(SCHEDULE_TIMES):
        schedule_minutes = h * 60 + m
        current_minutes = current_hour * 60 + current_minute
        diff = abs(schedule_minutes - current_minutes)
        
        if diff <= 30:
            matched_schedule = i
            break
    
    if matched_schedule is not None:
        start_time, end_time = get_time_window_for_schedule(matched_schedule)
        return start_time, end_time, matched_schedule
    else:
        # 手动触发：抓取最近 4 小时的邮件
        end_time = now_beijing
        start_time = end_time - timedelta(hours=4)
        return start_time, end_time, None


def main():
    """Main entry point for the email digest workflow."""
    print(f"[{datetime.now(timezone.utc).isoformat()}] Starting email digest...")
    
    # 检查是否指定了时间窗口索引（用于补救触发）
    schedule_index_str = os.environ.get("SCHEDULE_INDEX", "")
    force_schedule = False
    schedule_index = None
    
    if schedule_index_str:
        try:
            schedule_index = int(schedule_index_str)
            if 0 <= schedule_index < len(SCHEDULE_TIMES):
                force_schedule = True
                print(f"强制使用时间窗口索引: {schedule_index} ({SCHEDULE_TIMES[schedule_index][0]:02d}:{SCHEDULE_TIMES[schedule_index][1]:02d})")
            else:
                print(f"警告: 无效的 SCHEDULE_INDEX={schedule_index}，忽略")
                schedule_index = None
        except ValueError:
            print(f"警告: 无法解析 SCHEDULE_INDEX={schedule_index_str}，忽略")
            schedule_index = None
    
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
    if force_schedule:
        start_time, end_time = get_time_window_for_schedule(schedule_index)
        schedule_label = f"时间点 {schedule_index} ({SCHEDULE_TIMES[schedule_index][0]:02d}:{SCHEDULE_TIMES[schedule_index][1]:02d})"
    else:
        start_time, end_time, matched_schedule = get_time_window()
        if matched_schedule is not None:
            schedule_label = f"时间点 {matched_schedule}"
        else:
            schedule_label = "手动触发模式"
            print("手动触发模式：抓取最近 4 小时的邮件")
    
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
            from_email = from_addr.split('<')[-1].split('>')[0] if '<' in from_addr else from_addr
        
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
        timestamp = msg.get("timestamp", "") or msg.get("received_at", "") or msg.get("created_at", "")
        
        if msg_id in processed_ids:
            continue
        
        if timestamp:
            try:
                dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
                dt_beijing = dt.astimezone(beijing_tz)
                
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
            content = get_message_content(api_key, inbox_id, msg_id)
            translated = translate_email(content)
            
            sender = msg.get("from", {})
            if isinstance(sender, dict):
                sender_name = sender.get("name", "") or sender.get("email", "").split('@')[0]
            else:
                sender_name = str(sender).split('<')[0].strip() or str(sender).split('@')[0]
            
            article_title = msg.get("subject", "无主题")
            
            # 去除 Blogtrottr 等 RSS 转发服务的前缀（如 "Blogtrottr - " 或 "Blogtrottr: "）
            SENDER_PREFIX_RE = re.compile(r'^(Blogtrottr\s*[-–—:]\s*)+', re.IGNORECASE)
            sender_name = SENDER_PREFIX_RE.sub('', sender_name).strip()
            article_title = SENDER_PREFIX_RE.sub('', article_title).strip()
            
            email_subject = f"{sender_name} - {article_title}"
            
            print(f"\n发送邮件: {email_subject}")
            send_single_email(target_email, translated, email_subject)
            print(f"✅ 邮件发送成功")
            
            processed_ids.add(msg_id)
            
        except Exception as e:
            error_msg = f"Error processing {msg_id}: {str(e)}"
            print(f"❌ {error_msg}")
            processed_ids.add(msg_id)
    
    save_processed_ids(processed_ids)
    print(f"\n{'='*60}")
    print(f"保存 {len(processed_ids)} 个已处理邮件 ID")
    print("完成！")


if __name__ == "__main__":
    main()
