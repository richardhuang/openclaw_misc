# openclaw_misc

这是一个包含各种openclaw相关工具和脚本的仓库。

## 目录结构

- `scripts/` - 包含各种实用脚本

## 脚本说明

### format_log_tail.sh

这是一个用于格式化监控openclaw日志文件的脚本，具有以下特性：

- 实时监控日志文件的新内容
- 将UTC时间戳转换为GMT+8时区显示
- 为不同的模块名分配固定的颜色以便区分
- 格式化输出，使日志更易于阅读
- 清晰的颜色分层（时间戳、模块、日志级别）

使用方法：
```bash
./scripts/format_log_tail.sh
```

### get_openclaw_daily_usage.py

这是一个用于获取OpenClaw每日Token用量的脚本，具有以下特性：

- 通过WebSocket API连接到OpenClaw Gateway
- 获取指定天数范围内的每日Token使用情况
- 将数据保存到SQLite数据库
- 提供使用情况摘要统计

**环境要求**：
- Python 3.6+
- websockets库 (`pip install websockets`)

**配置要求**：
需要在 `~/.openclaw/openclaw.json` 中启用不安全认证：
```json
{
  "gateway": {
    "controlUi": {
      "dangerouslyDisableDeviceAuth": true
    }
  }
}
```

**使用方法**：

1. 设置OpenClaw Gateway Token（从配置文件中获取）：
```bash
export OPENCLAW_TOKEN="your_gateway_token"
```

2. 获取最近7天的用量（默认）：
```bash
python3 scripts/get_openclaw_daily_usage.py
```

3. 获取指定天数的用量：
```bash
python3 scripts/get_openclaw_daily_usage.py --days 30
```

4. 保存数据到数据库：
```bash
python3 scripts/get_openclaw_daily_usage.py --save --days 30
```

5. 查看数据库状态：
```bash
python3 scripts/get_openclaw_daily_usage.py --status
```

6. 列出所有已记录的数据：
```bash
python3 scripts/get_openclaw_daily_usage.py --list-all
```

**输出示例**：
```
==================================================
DAILY TOKEN USAGE SUMMARY
==================================================
2026-02-26: 1,403,748 tokens
2026-02-25: 41,548,324 tokens
2026-02-24: 48,289,654 tokens
...
--------------------------------------------------
TOTAL TOKENS: 114,224,574
DAYS WITH USAGE: 7
AVERAGE PER DAY: 16,317,796
```
