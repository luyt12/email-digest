import os
import requests

api_key = "am_us_f25361faa1077ccfcdd0dfb13d972965b55b0920c5fdbb35254b3dbbc501c26e"
inbox_id = "excitedsilver931@agentmail.to"
url = f"https://api.agentmail.to/v0/inboxes/{inbox_id}/messages?limit=5&ascending=false"
headers = {"Authorization": f"Bearer {api_key}"}

resp = requests.get(url, headers=headers)
if resp.status_code == 200:
    data = resp.json()
    messages = data.get("results", []) if isinstance(data, dict) else data
    print(f"Found {len(messages)} messages")
    for i, msg in enumerate(messages):
        print(f"{i+1}. {msg.get('subject', 'No subject')}")
else:
    print(f"Error: {resp.status_code} {resp.text}")