# Email Digest

自动获取邮箱新邮件，用 LLM 翻译后发送到目标邮箱。

## 功能

- 定时检查 AgentMail 收件箱
- 提取当日新邮件
- 使用 LLM 翻译为中文
- 发送摘要到目标邮箱

## 配置

### GitHub Secrets

| Secret | 说明 |
|--------|------|
| `AGENTMAIL_API_KEY` | AgentMail API Key |
| `AGENTMAIL_INBOX_ID` | 收件箱 ID |
| `TARGET_EMAIL` | 接收摘要的邮箱 |
| `NVIDIA_API_KEY` | NVIDIA API Key（翻译用） |

## 触发时间

- 每天 08:40, 13:40, 19:40 北京时间
- 也支持手动触发

## 本地测试

```bash
pip install -r requirements.txt

export AGENTMAIL_API_KEY="your_key"
export AGENTMAIL_INBOX_ID="your_inbox_id"
export TARGET_EMAIL="your@email.com"
export NVIDIA_API_KEY="your_nvidia_key"

python -m src.main
```

## 项目结构

```
email-digest/
├── src/
│   ├── main.py          # 入口
│   ├── config.py       # 配置
│   ├── fetch_emails.py # 获取邮件
│   ├── summarize.py   # LLM 翻译
│   ├── send_email.py  # 发送邮件
│   └── utils.py      # 工具函数
├── data/
│   └── processed_emails.json  # 已处理ID
├── .github/
│   └── workflows/
│       └── daily-digest.yml
├── requirements.txt
└── README.md
```

## License

MIT