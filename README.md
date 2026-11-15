# 熬鹰资本币安公开操作记录监控

这是一个只读监控项目。它每 5 分钟读取币安交易员“熬鹰资本”（项目 ID 5075281354358777856）网页中的**最新操作记录**，在启动后发现以下新成交时发送 Telegram：

- BUY + LONG：开多
- SELL + SHORT：开空
- SELL + LONG：平多
- BUY + SHORT：平空

程序没有下单、撤单、账户或资金接口，不需要币安 API Key，不调用 OpenAI API、ChatGPT、Codex 或任何其他 AI/付费模型。

## 数据源与行为保证

使用币安网页自身调用的公开只读接口：

    POST /bapi/futures/v1/friendly/future/copy-trade/lead-portfolio/order-history

1. 第一次成功读取时，把当时可见的最新操作记录全部保存为基准，不通知旧交易。
2. 后续只通知指纹未见过的新操作；没有新记录不发送消息。
3. 去重状态和待发 Telegram 事件保存在独立的 monitor-state 分支。
4. 新事件先写入持久化状态再发送；Telegram 临时失败时，下次运行重试。
5. 接口超时、HTTP 错误、data=null 或数据格式异常时，工作流失败并保留原状态，不把不可用误判成交易。
6. 操作记录接口与当前仓位公开状态彼此独立。即使 positionShow=false，只要操作记录接口仍返回有效 list，监控就正常处理；程序不读取当前仓位接口。
7. 每次最多读取最近 7 天的最新 100 条记录。正常五分钟轮询时足以覆盖新操作；若五分钟内超过 100 条，会在日志明确警告可能存在接口分页间隙。

## 已验证的真实接口结果

2026-11-14 实测项目详情仍为 positionShow=false，但最新操作记录接口成功返回 code=000000 和真实成交列表。接口中的一条记录为：

    BTCUSDT / BUY / LONG / MARKET
    executedQty=9.079
    avgPrice=63837.88902
    orderTime=1794698499143

程序将其识别为“开多”。这正是网页约下午 6:21 显示的操作，证明此前漏报原因是旧程序只监控当前仓位，而不是操作记录。迁移后的首次运行会把它作为旧记录建立基准，不补发提醒；其后新增的操作才会通知。

--check-api 会读取并打印接口最新真实记录的动作、合约、数量和时间戳，不发送模拟消息：

    PYTHONPATH=src python -m yingcapital_monitor --check-api

## 本地测试

项目只使用 Python 标准库：

    python -m unittest discover -s tests -v

测试覆盖四种操作映射、真实接口字段样本、首次基准不通知、新记录仅通知一次、状态迁移以及接口不可用时保留状态。

## GitHub Actions 部署

工作流位于 .github/workflows/monitor.yml，cron 为 2-59/5 * * * *，即每小时第 2、7、12……57 分钟计划执行。它使用公共仓库的标准 ubuntu-slim GitHub-hosted runner；按 GitHub 对公共仓库标准 runner 的规则，Actions 计算用量免费。工作流不安装第三方 Python 包。

只需要两个 Repository Secrets：

| Secret | 说明 |
|---|---|
| TELEGRAM_BOT_TOKEN | Telegram Bot Token |
| TELEGRAM_CHAT_ID | Telegram 接收方 Chat ID |

密钥只由 GitHub Secrets 注入，不进入代码、状态、日志或提交历史。工作流仅有定时触发和仓库管理员手动触发，不响应外部 PR。

## 运行边界与风险

- 此接口是币安网页公开 BAPI，并非承诺长期兼容的正式开发者 API；币安若改接口，工作流会明确失败，不会假装监控正常。
- GitHub cron 的五分钟是计划频率，不是实时 SLA。平台高负载时可能延迟或漏调度；下一次成功运行仍会从最近记录中补抓尚未见过的交易。
- 公共仓库的源码、工作流、日志和 monitor-state 分支公开。状态只包含公开交易指纹和必要的待发公开交易内容，不保存 Telegram Token、Chat ID 或私人数据。
- GitHub 可能暂停长期无仓库活动的定时工作流，应定期检查 Actions 页面。

本项目不会自动开通、购买或启用收费服务，也不会进行任何真实交易。
