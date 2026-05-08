# Email Digest

自动获取邮箱新邮件，用 LLM 翻译后发送到目标邮箱。

## 功能

- 每天 6 次定时检查 AgentMail 收件箱
- 仅抓取上一个时间点之后的新邮件
- 使用 LLM 翻译为中文
- **每封邮件单独发送**（标题为"来源名 - 文章标题"）

## 配置

### GitHub Secrets

| Secret | 说明 |
|--------|------|
| `AGENTMAIL_API_KEY` | AgentMail API Key |
| `AGENTMAIL_INBOX_ID` | 收件箱 ID |
| `TARGET_EMAIL` | 接收摘要的邮箱 |
| `NVIDIA_API_KEY` | NVIDIA API Key（翻译用） |

## 触发时间

每天 6 次（北京时间）：

| 时间 | 抓取范围 |
|------|---------|
| 04:40 | 0:00 ~ 04:40 |
| 08:40 | 4:41 ~ 08:40 |
| 13:40 | 8:41 ~ 13:40 |
| 16:40 | 13:41 ~ 16:40 |
| 19:40 | 16:41 ~ 19:40 |
| 23:40 | 19:41 ~ 23:40 |

也支持手动触发。

## 邮件格式

每封邮件单独发送，标题格式：**来源名 - 文章标题**

邮件内容包含：
- 原文信息（标题、发件人、时间）
- 翻译内容
- 字数统计和翻译模型

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
│   ├── main.py          # 入口（时间窗口逻辑）
│   ├── config.py       # 配置
│   ├── fetch_emails.py # 获取邮件
│   ├── summarize.py   # LLM 翻译
│   ├── send_email.py  # 发送邮件（单封发送）
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
