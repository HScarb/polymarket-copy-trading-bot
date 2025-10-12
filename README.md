# Polymarket 复制交易机器人

自动跟随专业交易者在 Polymarket 上的交易策略，实现智能复制交易。

## 🌟 核心功能

- ✅ **实时监控**: 监控目标钱包的所有交易活动
- ✅ **自动跟单**: 根据配置自动执行复制交易
- ✅ **灵活策略**: 支持按比例缩放 (Scale) 和按比例分配 (Allocate) 模式
- ✅ **风险控制**: 最小金额过滤、错误重试、交易统计
- ✅ **多种订单**: 支持市价单和限价单
- ✅ **事件驱动**: 基于消息队列的低延迟架构

## 📋 系统要求

- Python 3.13+
- PostgreSQL (可选，用于数据持久化)
- 网络代理 (可选，用于访问 Polymarket API)

## 🚀 快速开始

### 1. 安装依赖

```bash
# 使用 uv 管理依赖（推荐）
uv sync

# 或使用 pip
pip install -r requirements.txt
```

### 2. 配置机器人

```bash
# 复制配置文件模板
cp config.example.yaml config.yaml

# 编辑配置文件
vim config.yaml
```

**关键配置**:

```yaml
# 设置要监控的目标钱包
monitoring:
  wallets:
    - "0x55be7aa03ecfbe37aa5460db791205f7ac9ddca3"

# 配置你的钱包和策略
user_wallets:
  - name: "MyWallet"
    address: "0x..."
    private_key_env: "MY_WALLET_PRIVATE_KEY"

    copy_strategy:
      min_trade_amount: 10      # 最小触发金额
      order_type: "market"      # 订单类型: market/limit
      copy_mode: "scale"        # 复制模式: scale/allocate
      scale_percentage: 10.0    # 按目标金额的 10% 跟单
```

### 3. 设置私钥（安全方式）

**推荐方式：使用 .env 文件**

```bash
# 复制 .env 示例文件
cp .env.example .env

# 编辑 .env 文件，填入实际私钥
vim .env
```

`.env` 文件内容示例：
```bash
# 替换为你的实际私钥（必须以 0x 开头）
MY_WALLET_PRIVATE_KEY=0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef
SCARB4_PRIVATE_KEY=0x...
```

**备选方式：直接设置环境变量**

```bash
# Linux/Mac
export MY_WALLET_PRIVATE_KEY="0x..."

# Windows CMD
set MY_WALLET_PRIVATE_KEY=0x...

# Windows PowerShell
$env:MY_WALLET_PRIVATE_KEY="0x..."
```

⚠️ **安全提示**:
- 永远不要将私钥写入 `config.yaml` 配置文件！
- `.env` 文件已在 `.gitignore` 中，不会被提交到版本控制
- 私钥必须以 `0x` 开头，长度为 66 个字符

### 4. 安装依赖并运行

```bash
# 安装/更新依赖（已添加 python-dotenv）
uv sync

# 激活虚拟环境
source .venv/bin/activate  # Linux/Mac
.venv\Scripts\activate     # Windows

# 运行主程序
python -m src.main
```

启动时会看到：
```
✓ 已加载环境变量文件: E:\...\polymarket-copy-trading-bot\.env
正在加载配置文件...
CopyTrader 'MyWallet' 已初始化 | 地址: 0x... | 模式: scale
监控运行中,按 Ctrl+C 退出...
```
## 📊 运行模式

### 监控模式（默认）

不配置 `user_wallets`，程序只监控并打印日志：

```yaml
# 不配置或注释掉 user_wallets
# user_wallets: []
```

### 复制交易模式

配置至少一个 `user_wallet`，程序自动执行复制交易：

```yaml
user_wallets:
  - name: "MyWallet"
    address: "0x..."
    # ... 策略配置
```

## 🎯 复制策略说明

### Scale 模式（按比例缩放）

按目标交易金额的固定百分比跟单：

```yaml
copy_mode: "scale"
scale_percentage: 10.0  # 目标交易 100 USDC，我跟 10 USDC
```

**适用场景**:
- 资金规模固定
- 希望固定倍数放大/缩小风险敞口

### Allocate 模式（按比例分配）

按目标钱包资产配置比例跟单（暂未完全实现）：

```yaml
copy_mode: "allocate"
# 目标用其总资产的 5% 交易，我也用我总资产的 5% 跟单
```

**适用场景**:
- 资金规模与目标不同
- 希望保持相同的资产配置比例

## 🛡️ 风险控制

### 过滤机制

```yaml
copy_strategy:
  # 最小触发金额，避免跟随小额测试交易
  min_trade_amount: 10
```

### 订单类型

**市价单** (推荐新手):
- 优点: 快速成交
- 缺点: 可能有滑点

```yaml
order_type: "market"
```

**限价单** (推荐进阶):
- 优点: 价格保障，避免滑点
- 缺点: 可能不成交

```yaml
order_type: "limit"
limit_order_duration: 7200  # 2 小时有效期
```

## 📁 项目结构

```
polymarket-copy-trading-bot/
├── src/
│   ├── main.py                  # 主程序入口
│   ├── copy_trader.py          # 复制交易核心类 ⭐ NEW
│   ├── wallet_monitor.py       # 钱包监控器
│   ├── activity_queue.py       # 消息队列接口
│   ├── in_memory_activity_queue.py  # 内存队列实现
│   ├── config_loader.py        # 配置加载器（已扩展）
│   ├── database_handler.py     # 数据库处理
│   ├── models.py               # 数据模型
│   └── logger.py               # 日志工具
├── config.yaml                 # 配置文件（需创建）
├── config.example.yaml         # 配置文件示例 ⭐ NEW
├── test_copy_trader.py         # 单元测试 ⭐ NEW
├── COPY_TRADING_IMPLEMENTATION.md  # 实现文档 ⭐ NEW
└── README.md                   # 本文件
```

## 🧪 测试

```bash
# 运行单元测试
python test_copy_trader.py

# 运行消息队列测试
python test_message_queue.py
```

## 📝 日志

日志文件位于 `logs/` 目录，按日期分割：

```bash
# 实时查看日志
tail -f logs/$(date +%Y-%m-%d).log  # Linux/Mac
type logs\YYYY-MM-DD.log            # Windows
```

日志包含：
- 监控状态
- 交易活动
- 复制交易决策
- 订单执行结果
- 错误和重试信息

## 🔧 配置参考

### 完整配置示例

```yaml
# 数据库配置（可选）
database:
  url: "postgresql://user:pass@localhost:5432/polymarket_bot"

# 日志配置
logging:
  log_dir: "logs"
  level: "INFO"  # DEBUG, INFO, WARNING, ERROR

# API 配置
polymarket_api:
  proxy: "http://localhost:7891"  # 可选
  timeout: 30.0

# 监控配置
monitoring:
  wallets:
    - "0x..."  # 目标钱包地址
  poll_interval_seconds: 5
  batch_size: 100

# 消息队列配置
queue:
  type: "memory"
  memory:
    max_workers: 10

# 复制交易配置
user_wallets:
  - name: "MyWallet"
    address: "0x..."
    private_key_env: "MY_WALLET_PRIVATE_KEY"

    copy_strategy:
      min_trade_amount: 10
      order_type: "market"
      limit_order_duration: 7200
      copy_mode: "scale"
      scale_percentage: 10.0
```

## ⚠️ 安全建议

1. **私钥管理**
   - 使用环境变量存储私钥
   - 生产环境使用密钥管理服务（AWS Secrets Manager、HashiCorp Vault）
   - 定期轮换私钥

2. **资金安全**
   - 使用专用的交易钱包
   - 从小额测试开始
   - 定期检查账户余额

3. **风险控制**
   - 设置合理的 `min_trade_amount`
   - 使用较小的 `scale_percentage` 开始
   - 监控交易统计和失败率

4. **运营安全**
   - 监控程序运行状态
   - 设置告警机制
   - 定期备份配置和数据

## 📊 监控指标

程序退出时会打印交易统计：

```
[MyWallet] 交易统计:
  - 总活动数: 150
  - 已过滤: 100
  - 尝试交易: 50
  - 成功: 48
  - 失败: 2
```

## 🐛 故障排查

### 问题: 程序无法启动

**检查**:
- 环境变量是否设置
- 配置文件格式是否正确
- 依赖是否完整安装

### 问题: 无法执行交易

**检查**:
- 钱包余额是否充足
- 网络连接是否正常
- 私钥是否正确
- API 访问是否受限

### 问题: 交易被过滤

**检查**:
- `min_trade_amount` 是否设置过高
- 活动类型是否为 `TRADE`
- 查看日志了解具体原因

## 🛠️ 开发

### 添加自定义订阅者

```python
def my_custom_handler(activities: List[dict]):
    for activity in activities:
        # 自定义处理逻辑
        pass

# 在 main.py 中订阅
activity_queue.subscribe(wallet_address, my_custom_handler)
```

### 扩展过滤逻辑

在 `CopyTrader._should_process_activity()` 中添加自定义过滤条件：

```python
# 添加市场白名单过滤
whitelist = self.strategy_config.get('whitelist_markets', [])
if whitelist and market_id not in whitelist:
    return False
```

## 📚 相关文档

- [设计文档](docs/design/copy-trading-feature-design.md)
- [实现总结](COPY_TRADING_IMPLEMENTATION.md)
- [消息队列重构总结](MESSAGE_QUEUE_REFACTOR_SUMMARY.md)
- [Polymarket CLOB API 文档](https://docs.polymarket.com/)
- [py-clob-client GitHub](https://github.com/Polymarket/py-clob-client)

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

## 📄 许可证

[MIT License](LICENSE)

## ⚖️ 免责声明

本软件仅供学习和研究使用。使用本软件进行实际交易的风险由用户自行承担。作者不对任何资金损失负责。

**重要提示**:
- 加密货币交易存在高风险
- 过去的表现不代表未来收益
- 请仅使用您能承受损失的资金
- 在使用前充分理解交易规则和风险

---

**Happy Trading! 🚀**

如有问题，请查看日志文件或提交 Issue。
