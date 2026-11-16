# 币安五交易员公开操作记录监控

本项目每 5 分钟在同一个 GitHub Actions 工作流中读取五位交易员的网页“最新操作记录”：

| 交易员 | 项目 ID |
|---|---|
| 熬鹰资本 | 5075281354358777856 |
| 请填写昵称 | 5296057151807357697 |
| 刀箭穿心BTC（币安昵称：万箭穿心BTC） | 5247756265911980544 |
| Sky株式会社 | 4532994172262753536 |
| 发烧好了呢 | 5271501457743196416 |

第三位按要求显示为“刀箭穿心BTC”，同时独立核验币安接口实际昵称“万箭穿心BTC”，避免错误项目冒充。

识别规则：

- BUY + LONG：开多
- SELL + SHORT：开空
- SELL + LONG：平多
- BUY + SHORT：平空

程序没有下单、撤单、账户或资金接口，不需要币安 API Key，不调用 OpenAI API、ChatGPT、Codex 或任何付费模型。

## 独立状态与通知保证

五位交易员分别使用以下状态文件：

    .runtime/5075281354358777856.json
    .runtime/5296057151807357697.json
    .runtime/5247756265911980544.json
    .runtime/4532994172262753536.json
    .runtime/5271501457743196416.json

每份文件分别保存基准、最新操作时间、最新操作指纹、币安接口游标、去重指纹和待发送事件，互不覆盖。

1. 缺少某位交易员的状态文件时，第一次成功读取只建立该交易员的基准，不通知历史记录。
2. 升级前熬鹰资本的 state.json 会迁移到其项目 ID 文件，保留原基准和去重信息。
3. 新事件先写入对应状态文件再发送；Telegram 临时失败时只重试该交易员的待发事件。
4. 一个接口失败不会阻止另外四位继续检查，但工作流最终会标记失败以便发现问题。
5. positionShow 不控制操作记录监控。仓位隐藏时，只要独立操作记录接口有效，仍正常处理。
6. data=null、HTTP 错误或格式异常时保留该交易员原状态，不产生虚假提醒。

Telegram 通知包含交易员昵称、交易对、开多/开空/平多/平空、成交价格、成交数量、名义价值、操作时间、订单类型和项目 ID。

## 已验证接口

五个项目均通过以下币安网页公开只读接口验证：

    POST /bapi/futures/v1/friendly/future/copy-trade/lead-portfolio/order-history

2026-11-15 实测：

- 熬鹰资本：接口有效；positionShow=false 不影响操作记录。
- 请填写昵称：SIGNAL 项目，接口有效，读取到真实 UNITREE、SAMSUNG、SPCX 操作。
- 刀箭穿心BTC：币安实际昵称“万箭穿心BTC”，SIGNAL 项目，接口有效，读取到真实 BTCUSDT 操作。
- Sky株式会社：PUBLIC 项目，positionShow=false，但接口有效，读取到真实 TSLA、BTC、NVDA 操作。
- 发烧好了呢：SIGNAL 项目，接口有效，读取到真实 SOXS、AMD、MUU、MU 操作。

只验证接口而不发消息：

    PYTHONPATH=src python -m yingcapital_monitor --check-api

运行测试：

    python -m unittest discover -s tests -v

## GitHub Actions

只保留 .github/workflows/monitor.yml 一个工作流和原 cron：

    2-59/5 * * * *

五位交易员共用现有 TELEGRAM_BOT_TOKEN 和 TELEGRAM_CHAT_ID 两个 Repository Secrets，无需新增密钥或机器人。状态保存在独立 monitor-state 分支。

公开仓库使用标准 ubuntu-slim GitHub-hosted runner，按 GitHub 公共仓库标准 runner 规则免费。GitHub cron 是计划频率而非实时 SLA，平台繁忙时可能延迟；下一次成功执行会通过独立去重状态补抓仍在最新记录窗口内的交易。

本项目不会启用收费服务，也不会进行任何真实交易。
