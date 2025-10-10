# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

Polymarket 复制交易机器人 - 使用事件驱动架构实时监控指定钱包地址在 Polymarket 上的交易活动，通过消息队列系统将活动分发给多个订阅者进行处理。

## 核心架构

### 数据流（消息队列架构）
```
Polymarket API → WalletMonitor → ActivityQueue → Subscribers
                                      ↓
                                  [订阅者1: 交易执行器]
                                  [订阅者2: 数据记录器]
                                  [订阅者3: 告警系统]
```

### 关键组件

1. **WalletMonitor** (`src/wallet_monitor.py`)
   - 核心监控逻辑，每个钱包运行在独立线程中
   - 从当前时间开始监控，只获取启动后的新活动
   - 分批获取交易数据（默认500条/批）
   - 将活动推送到 ActivityQueue 而不是直接存储

2. **ActivityQueue** (`src/activity_queue.py`)
   - 抽象基类，定义消息队列接口
   - 两个核心方法：`enqueue(wallet, activities)` 和 `subscribe(wallet, callback)`
   - 支持多种实现（内存队列、RabbitMQ 等）

3. **InMemoryActivityQueue** (`src/in_memory_activity_queue.py`)
   - ActivityQueue 的内存实现，用于开发和测试
   - 使用 ThreadPoolExecutor 异步执行订阅者回调
   - 维护订阅者字典，支持一个钱包多个订阅者
   - 自动处理回调异常，不影响其他订阅者

4. **DatabaseHandler** (`src/database_handler.py`) [保留用于其他功能]
   - 使用 Peewee ORM 管理 PostgreSQL 连接
   - 提供检查点的 CRUD 操作（使用 UPSERT）
   - 批量保存交易数据，自动处理主键冲突（去重）

5. **Models** (`src/models.py`) [保留用于其他功能]
   - `Trade`: 交易记录（主键：transaction_hash）
   - `WalletCheckpoint`: 钱包同步进度（主键：wallet_address）

### 消息队列机制

**订阅流程**：
1. 订阅者调用 `activity_queue.subscribe(wallet_address, callback_function)`
2. 队列将回调函数注册到对应钱包的订阅者列表

**发布流程**：
1. WalletMonitor 检测到新活动
2. 调用 `activity_queue.enqueue(wallet_address, activities)`
3. 队列异步通知所有订阅者（通过 ThreadPoolExecutor）
4. 订阅者的回调函数被触发，接收活动数据

**错误处理**：
- 回调函数异常被捕获并记录，不影响其他订阅者
- 监控器异常不影响队列系统
- 支持优雅关闭（shutdown）

## 开发命令

### 环境设置
```bash
# 使用 uv 管理依赖
uv sync
```

### 运行程序
```bash
# 激活虚拟环境（Windows）
.venv/Scripts/activate

# 运行主程序
python -m src.main
```

### 测试
```bash
# 测试消息队列功能（推荐）
python test_message_queue.py

# 测试检查点功能（旧版，保留用于其他功能）
python test_checkpoint.py

# 验证检查点数据（旧版）
python verify_checkpoint.py

# 测试完整监控流程（旧版）
python test_monitor.py
```

## 配置文件

### config.yaml 结构
```yaml
database:
  url: "postgresql://user:password@host:port/dbname"  # 保留用于其他功能

logging:
  log_dir: "logs"
  level: "INFO"  # DEBUG, INFO, WARNING, ERROR

polymarket_api:
  proxy: "http://localhost:7891"  # 可选
  timeout: 30.0

monitoring:
  wallets:
    - "0x..."  # 监控的钱包地址列表
  poll_interval_seconds: 60
  batch_size: 500  # 每次 API 请求获取的交易数量

# 消息队列配置
queue:
  type: "memory"  # 可选: "memory" 或 "rabbitmq"
  memory:
    max_workers: 10  # 回调执行的最大线程数
  rabbitmq:  # RabbitMQ 配置（尚未实现）
    host: "localhost"
    port: 5672
    username: "guest"
    password: "guest"
    exchange: "polymarket_activities"
```

## 关键设计决策

1. **事件驱动架构**：使用发布/订阅模式实现低延迟实时通知
2. **解耦设计**：WalletMonitor 与数据处理逻辑完全解耦，通过 ActivityQueue 通信
3. **并发模型**：
   - 每个钱包在独立线程中监控
   - 订阅者回调在独立线程池中异步执行
4. **实时监控**：从启动时刻开始监控，只关注新发生的活动
5. **批量获取**：分批获取活动（batch_size），自动处理分页
6. **可扩展性**：通过 ActivityQueue 抽象支持多种队列实现（内存、RabbitMQ）
7. **异常隔离**：订阅者回调异常不影响其他订阅者

## 如何使用（示例）

### 创建自定义订阅者

```python
def my_trading_bot(activities: List[dict]):
    """自定义回调函数处理活动"""
    for activity in activities:
        # 提取数据
        tx_hash = getattr(activity, 'transaction_hash', None)
        market_id = getattr(activity, 'condition_id', None)
        outcome = getattr(activity, 'outcome', None)

        # 实现你的交易逻辑
        execute_copy_trade(market_id, outcome)

# 在 main.py 中订阅
activity_queue.subscribe(wallet_address, my_trading_bot)
```

### 数据库表结构（保留用于其他功能）

#### trades
- `transaction_hash` (PK): 交易哈希
- `wallet_address`: 钱包地址（索引）
- `market_id`: 市场ID（索引）
- `outcome`: 结果
- `amount`: 金额（Decimal 36,18）
- `price`: 价格（Decimal 36,18）
- `timestamp`: 时间戳（索引）

#### wallet_checkpoints
- `wallet_address` (PK): 钱包地址
- `last_synced_timestamp`: 最后同步的时间戳（索引）
- `updated_at`: 更新时间（索引）

## 依赖项

- `polymarket-apis`: Polymarket API 客户端
- `peewee`: ORM 框架
- `psycopg2-binary`: PostgreSQL 驱动
- `pyyaml`: 配置文件解析
- `httpx`: HTTP 客户端（用于代理配置）

## 日志

- 控制台输出：实时日志
- 文件输出：`logs/YYYY-MM-DD.log`（按日期分割）
- 日志级别：可通过 config.yaml 配置

## 错误处理

- API 请求失败：记录错误后在下次轮询时重试
- 订阅者回调异常：捕获并记录，不影响其他订阅者
- 优雅关闭：SIGINT/SIGTERM 信号处理，关闭监控器和队列线程池

## 架构演进

项目已从**批处理、持久化优先**架构演进为**事件驱动、实时通知**架构：

### 旧架构（保留用于参考）
- 直接存储到数据库
- 使用检查点系统进行断点续传
- 数据消费者需要轮询数据库

### 新架构（当前）
- 使用消息队列分发活动
- 支持多个订阅者实时接收通知
- 从启动时刻开始监控新活动
- 数据持久化成为可选的订阅者功能

### 未来扩展
- 实现 RabbitMQ 队列支持生产环境
- 添加更多订阅者（告警、分析、持久化等）
- 支持跨进程消息传递
