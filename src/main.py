#!/usr/bin/env python3
"""Email Digest - Fetch, translate and send email digests via GitHub Actions."""

import os
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from fetch_emails import fetch_recent_emails, get_message_content
from summarize import translate_email
from send_email import send_digest_email
from utils import load_processed_ids, save_processed_ids, is_today


def main():
    """Main entry point for the email digest workflow."""
    print(f"[{datetime.now(timezone.utc).isoformat()}] Starting email digest...")
    
    # Load configuration
    api_key = os.environ.get("AGENTMAIL_API_KEY")
    # Try inbox email first (new format), fall back to inbox ID (old format)
    inbox_email = os.environ.get("AGENTMAIL_INBOX_EMAIL", "excitedsilver931@agentmail.to")
    inbox_id = os.environ.get("AGENTMAIL_INBOX_ID", inbox_email)
    target_email = os.environ.get("TARGET_EMAIL")
    
    if not all([api_key, inbox_id, target_email]):
        print("Error: Missing required environment variables")
        print(f"  AGENTMAIL_API_KEY: {'set' if api_key else 'MISSING'}")
        print(f"  AGENTMAIL_INBOX_ID: {'set' if inbox_id else 'MISSING'}")
        print(f"  TARGET_EMAIL: {'set' if target_email else 'MISSING'}")
        sys.exit(1)
    
    # Load processed email IDs
    processed_ids = load_processed_ids()
    print(f"Loaded {len(processed_ids)} previously processed email IDs")
    
    # Fetch recent emails
    print(f"Fetching emails from inbox: {inbox_id}")
    all_messages = fetch_recent_emails(api_key, inbox_id)
    print(f"Found {len(all_messages)} total messages (inbox + sent)")
    
    # Filter to only INCOMING emails (where 'from' is NOT our inbox address)
    # AgentMail returns both incoming and outgoing messages in the same list
    messages = []
    for m in all_messages:
        from_addr = m.get("from", "")
        # If from_addr is a dict, extract the email
        if isinstance(from_addr, dict):
            from_addr = from_addr.get("email", "")
        # Skip if this is a sent email (from our own inbox)
        if from_addr == inbox_id or from_addr == inbox_email:
            continue
        messages.append(m)
    
    print(f"Found {len(messages)} incoming emails (excluding sent)")
    
    # DEBUG: Print first 5 incoming subjects
    print("\n=== Latest 5 INCOMING email subjects ===")
    for i, msg in enumerate(messages[:5]):
        subject = msg.get("subject", "No subject")
        sender = msg.get("from", "Unknown")
        if isinstance(sender, dict):
            sender = sender.get("email", "Unknown")
        received = msg.get("timestamp", "")[:19] if msg.get("timestamp") else ""
        print(f"{i+1}. [{received}] {subject[:60]} (from: {sender[:40]})")
    print("=== End of subjects ===\n")
    
    # Filter to today's unprocessed emails
    new_emails = []
    for msg in messages:
        msg_id = msg.get("id")
        received_at = msg.get("received_at", "")
        
        # Skip already processed
        if msg_id in processed_ids:
            continue
        
        # Skip if not today's email
        if not is_today(received_at):
            continue
        
        new_emails.append(msg)
    
    print(f"Found {len(new_emails)} new emails from today")
    
    if not new_emails:
        print("No new emails to process. Exiting.")
        return
    
    # Process each email
    translated_emails = []
    errors = []
    
    for msg in new_emails:
        msg_id = msg.get("id")
        print(f"\nProcessing email: {msg_id}")
        
        try:
            # Get full message content
            content = get_message_content(api_key, inbox_id, msg_id)
            
            # Translate using LLM
            translated = translate_email(content)
            translated_emails.append(translated)
            
            # Mark as processed
            processed_ids.add(msg_id)
            print(f"Successfully processed: {msg.get('subject', 'No subject')}")
            
        except Exception as e:
            error_msg = f"Error processing {msg_id}: {str(e)}"
            print(error_msg)
            errors.append(error_msg)
            # Still mark as processed to avoid infinite retries
            processed_ids.add(msg_id)
    
    # Save processed IDs
    save_processed_ids(processed_ids)
    print(f"\nSaved {len(processed_ids)} processed email IDs")
    
    # Send digest email
    if translated_emails:
        print(f"\nSending digest with {len(translated_emails)} emails to {target_email}")
        send_digest_email(target_email, translated_emails, errors)
        print("Digest email sent!")
    else:
        print("\nNo emails to send (all failed)")


if __name__ == "__main__":
    main()