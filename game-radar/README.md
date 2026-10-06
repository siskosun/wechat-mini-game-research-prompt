# 每日游戏雷达投递

这个目录承载“每日游戏雷达”的公开归档与飞书投递。

## 链路

ChatGPT 定时任务 → `game-radar/reports/YYYY-MM-DD.md` → GitHub Actions → 飞书群自定义机器人。

正常运行不依赖 Remote Desktop Commander、Windows 本机或 Gmail。

## 目录

- `reports/`：每日完整雷达，按 Asia/Shanghai 日期命名。
- `send_feishu.py`：只负责把指定日报通过飞书自定义机器人 Webhook 发送到群。
- `.github/workflows/game-radar-to-feishu.yml`：仅在 `reports/*.md` 新增时自动投递。

## 一次性配置

在仓库 Settings → Secrets and variables → Actions 中创建：

- `FEISHU_WEBHOOK_URL`：飞书群自定义机器人的完整 Webhook URL。
- `FEISHU_SIGNING_SECRET`：可选。仅当机器人开启“签名校验”时设置。

不要把 Webhook URL 或签名密钥写进公开文件、Issue、日志或提交历史。

## 去重规则

自动投递只处理本次提交里“新增”的 `game-radar/reports/*.md`。定时任务如果发现当天文件已经存在，应直接结束，不覆盖、不重复提交。

## 故障判断

- 当天报告文件不存在：生成任务失败。
- 报告文件存在，但对应 `Game radar to Feishu` workflow 失败：投递失败。
- workflow 成功：视为飞书投递完成。
