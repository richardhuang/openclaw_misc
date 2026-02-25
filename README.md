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