# 熬鹰资本币安公开仓位监控

这是一个只读监控项目。它每 5 分钟读取币安交易员“熬鹰资本”（项目 ID `5075281354358777856`）的**当前公开仓位快照**，比较上一次有效快照，并通过 Telegram 提醒以下变化：

- 新开仓
- 加仓
- 减仓
- 平仓
- 反手（同一交易对从单一多头切换为单一空头，或相反）

程序没有任何下单、撤单、账户或资金接口，也不需要币安 API Key。

部署后的定时任务也**不会调用 OpenAI API、ChatGPT、Codex 或任何付费 AI 模型**。项目没有 AI SDK、AI 密钥或相关网络请求；每次运行只是普通 Python 程序调用币安公开只读接口，并在有变化时调用 Telegram Bot API。

## 行为保证

1. 不调用订单历史或已平仓历史接口，不下载、分析或通知旧交易。
2. 首次取得**有效**仓位列表时只保存基准，不发送提醒。
3. `positionShow` 不是 `true`、`data=null`、超时、HTTP 错误或数据格式异常均视为“数据不可用”，保留原基准，绝不当作空仓，因此不会误报平仓。
4. 只有 `positionShow=true` 且币安明确返回有效列表时才比较；在此前提下，明确的空列表 `[]` 才代表有效空仓。
5. 没有数量变化时不发送消息；价格和浮盈变化本身不触发提醒。
6. Telegram 临时发送失败时会保留待发事件，下次运行只重试未送达事件。
7. 状态保存在仓库的独立 `monitor-state` 分支，主分支不会被定时状态提交污染；状态只含币安公开仓位数据和通知渠道送达布尔值。
8. 首次建基准及检测到任何变化时都会二次读取；两次数量快照不一致或第二次不可用时，保留旧基准且不通知。

## 当前接口验证结果

项目详情接口可访问，返回昵称“熬鹰资本”、状态 `ACTIVE`。但在验证时：

```text
positionShow=false
positions data=null
```

这表示该交易员当时没有向公众开放当前仓位。系统可以部署并定时检查，但在币安返回有效仓位列表之前不会建立基准，也不会产生仓位提醒。该安全行为是有意设计。

## 本地测试

项目只使用 Python 标准库：

```bash
python -m pip install -e .
python -m unittest discover -s tests -v
yingcapital-monitor --check-api
```

`--check-api` 不需要通知密钥。接口可访问但仓位未公开时退出码为 `2`。

## GitHub Actions 零费用部署方案

使用**公开 GitHub 仓库**。GitHub 官方说明：公共仓库使用标准 GitHub-hosted runner 免费且不限量。本项目的工作流位于 `.github/workflows/monitor.yml`，定时表达式为 `2-59/5 * * * *`（每小时第 2、7、12……57 分钟），使用官方标准 `ubuntu-slim` 1 vCPU runner，因此不产生 Actions 计算费。

正式部署后，工作流只支持 `schedule` 和仓库管理员手动触发，不监听 `push`、`pull_request` 或 `pull_request_target`。两个 GitHub 官方 Action 均固定到核实过的完整 commit SHA；程序不安装第三方 Python 依赖。首次推送时会暂时保留为“仅手动触发”，Secrets 测试通过后才启用五分钟计划任务。

在私有仓库的 **Settings → Secrets and variables → Actions** 中建立这些 Repository secrets：

| Secret | 说明 |
|---|---|
| `TELEGRAM_BOT_TOKEN` | 从 BotFather 获取的机器人 Token |
| `TELEGRAM_CHAT_ID` | Telegram 接收方 Chat ID |

Telegram Bot Token 和 Chat ID 只从 GitHub Secrets 注入，不会进入代码、状态文件或提交历史。GitHub 官方说明 fork 发起的工作流不会取得这些 Secrets，并会自动遮蔽日志中意外打印的 Secret 原值。

配置后先在 **Actions → Monitor public positions → Run workflow** 勾选 `test_notification`，验证 Telegram。正常定时任务首次取得有效仓位时只建立基准。Telegram 私聊机器人通常还需要先在客户端向机器人点击 **Start**。

## 监控边界

此版本严格按快照比较，不读取成交记录。因此，如果某个仓位在两次五分钟检查之间开仓后又完全平仓、且最终快照与之前相同，系统无法观察到这个瞬时过程。这是“不读取历史交易”与五分钟快照方案的固有限制。

## 安全

- 不把真实密钥写入 `.env`、代码、状态文件或仓库。
- 不记录 Bot Token、Chat ID 或完整请求头。
- 仓位状态只包含币安公开数据。
- 代码中不存在真实交易功能。
- 代码中不存在 OpenAI、ChatGPT、Codex 或其他 AI 模型调用。

## 可能的服务费用

- 本方案使用公开仓库的标准 `ubuntu-slim` runner；按 GitHub 当前规则，其 Actions 计算用量免费且不限量。
- Telegram Bot API 通常不收费。

本项目不会自动开通、购买或启用任何收费服务。

## 公共仓库风险

- 源码、工作流、Actions 日志和 `monitor-state` 分支对所有人可见；状态分支只保存本来就公开的币安仓位快照，不保存用户凭据或收件信息。
- 不要向仓库添加不受信任的写权限协作者；有写权限的人可以修改默认分支上的工作流并使用仓库 Secrets。
- GitHub 定时任务可能因平台高负载而延迟，极端情况下可能丢弃排队任务；五分钟是 GitHub 支持的最短间隔，并非实时保证。
- 公共仓库连续 60 天无仓库活动时，GitHub 可能自动停用定时工作流，需要手动重新启用。状态分支通常会持续产生仓库活动，但仍建议定期检查 Actions 状态。

