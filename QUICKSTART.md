# 快速启动指南

5 分钟开始使用 Polymarket 复制交易机器人。

## 📦 第一步：安装依赖

```bash
# 克隆或下载项目后，进入项目目录
cd polymarket-copy-trading-bot

# 安装依赖（需要先安装 uv）
uv sync
```

## ⚙️ 第二步：配置文件

### 1. 创建配置文件

```bash
cp config.example.yaml config.yaml
```

### 2. 编辑 `config.yaml`

最少需要配置这两项：

```yaml
monitoring:
  wallets:
    - "0x55be7aa03ecfbe37aa5460db791205f7ac9ddca3"  # 改成你要监控的目标钱包

user_wallets:
  - name: "MyWallet"
    address: "0xYourWalletAddress"  # 改成你的钱包地址
    private_key_env: "MY_WALLET_PRIVATE_KEY"

    copy_strategy:
      min_trade_amount: 10
      order_type: "market"
      copy_mode: "scale"
      scale_percentage: 10.0  # 按目标金额的 10% 跟单
```

## 🔐 第三步：设置私钥

### 使用 .env 文件（推荐）

```bash
# 1. 创建 .env 文件
cp .env.example .env

# 2. 编辑 .env 文件
vim .env  # 或使用任何文本编辑器
```

在 `.env` 中添加：

```bash
MY_WALLET_PRIVATE_KEY=0x你的私钥（必须以0x开头）
```

⚠️ **重要**: 私钥必须是完整的 66 个字符（包括 `0x`）

### 或直接设置环境变量

```bash
# Linux/Mac
export MY_WALLET_PRIVATE_KEY="0x..."

# Windows PowerShell
$env:MY_WALLET_PRIVATE_KEY="0x..."
```

## 🚀 第四步：运行

```bash
# 激活虚拟环境
source .venv/bin/activate  # Linux/Mac
.venv\Scripts\activate     # Windows

# 运行
python -m src.main
```

## ✅ 预期输出

成功启动后会看到：

```
✓ 已加载环境变量文件: E:\...\polymarket-copy-trading-bot\.env
正在加载配置文件...
活动队列已创建: InMemoryActivityQueue
检测到 1 个用户钱包配置，正在初始化复制交易器...
CopyTrader 'MyWallet' 已初始化 | 地址: 0x... | 模式: scale
CopyTrader 'MyWallet' 开始跟随钱包: 0x...
复制交易器 'MyWallet' 已启动
开始监控 1 个钱包地址
钱包 0x...: 设置检查点为 2025-10-12 13:00:00+08:00（东八区）
监控运行中,按 Ctrl+C 退出...
```

## 📊 看到交易

当目标钱包有交易时，你会看到：

```
[MyWallet] 收到 1 条活动来自钱包 0x...
[MyWallet] 准备复制交易 | 市场: Will Trump win? | 方向: BUY | 结果: YES | 金额: $10.00
[MyWallet] 市价单已提交 | token_id: 0x... | 方向: BUY | 金额: $10.00
[MyWallet] ✓ 复制交易成功 | 订单ID: 0x...
```

## 🛑 停止程序

按 `Ctrl+C` 停止，会看到统计信息：

```
收到退出信号,正在关闭...
[MyWallet] 交易统计:
  - 总活动数: 50
  - 已过滤: 30
  - 尝试交易: 20
  - 成功: 19
  - 失败: 1
监控已停止
```

## ⚠️ 常见问题

### 问题：环境变量未设置

```
ValueError: 环境变量 'MY_WALLET_PRIVATE_KEY' 未设置
```

**解决**:
1. 确认 `.env` 文件存在且在项目根目录
2. 确认私钥以 `0x` 开头
3. 重启终端或重新激活虚拟环境

### 问题：没有看到 .env 加载提示

**解决**:
```bash
# 确认依赖已安装
uv sync

# 确认 python-dotenv 已安装
pip list | grep dotenv
```

### 问题：交易全部被过滤

**检查**:
- `min_trade_amount` 是否设置过高
- 目标钱包是否有交易活动
- 查看日志了解具体原因

### 问题：钱包余额不足

```
InsufficientBalanceError: 余额不足
```

**解决**:
- 确保钱包有足够的 USDC
- 降低 `scale_percentage`

## 📝 下一步

- 查看 [README.md](README.md) 了解完整功能
- 查看 [COPY_TRADING_IMPLEMENTATION.md](COPY_TRADING_IMPLEMENTATION.md) 了解实现细节
- 调整 `config.yaml` 中的策略参数
- 监控 `logs/` 目录中的日志文件

## 🔒 安全提醒

1. ✅ 使用 `.env` 文件存储私钥
2. ✅ 不要提交 `.env` 到 Git（已在 .gitignore）
3. ✅ 从小额测试开始（例如 `scale_percentage: 1.0`）
4. ✅ 使用专用的测试钱包
5. ✅ 定期检查账户余额和交易记录

---

**开始交易吧！🎯**

遇到问题？查看 [README.md](README.md) 的故障排查章节或提交 Issue。
