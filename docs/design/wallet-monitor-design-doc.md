# [Polymarket 钱包监控模块] 设计文档

## 1. 背景

### 1.1 功能简介

该模块是 Polymarket 复制交易机器人的核心组件之一。它负责持续监控一组指定的钱包地址，自动获取它们在 Polymarket 上的最新交易活动，为后续的自动跟单功能提供实时数据支持。

### 1.2 需求与痛点

- **需求**: 为了实现可靠的复制交易，机器人需要一个能够实时、准确地捕获目标交易员所有链上行为的系统。
- **痛点**: 手动通过浏览器或API去跟踪多个钱包的交易活动，不仅效率低下、耗时耗力，而且容易出错或遗漏，完全无法满足自动化交易系统所要求的毫秒级响应和高可靠性。因此，一个自动化的、健壮的监控系统是实现高效复制交易策略的必备基础。

### 1.3 使用场景

- **场景**: 用户希望跟随一位或多位“聪明钱”交易员的策略。
- **步骤**:
  1. 用户在配置文件中填入目标交易员的钱包地址列表。
  2. 启动机器人，钱包监控模块自动在后台运行。
  3. 模块按预设的时间间隔（例如每30秒）并发地检查所有目标钱包。
  4. 一旦发现新交易，系统会立即将其解析并存入数据库，同时打印日志告警，为交易执行模块提供决策依据。

## 2. 概要设计

本模块的整体思路通过以下几个步骤实现：

1.  **配置加载**: 系统启动时，通过 `ConfigLoader` 加载 `config.yaml` 文件，获取数据库URL、待监控的钱包地址列表和API轮询间隔等核心配置。
2.  **核心初始化**: 主程序根据加载的配置，初始化 `WalletMonitor` 类。该类内部会创建一个 `PolymarketDataClient` 实例用于API交互，并维护一个用于并发处理的线程池。
3.  **任务创建与调度**: `WalletMonitor` 为配置文件中的每一个钱包地址，都创建一个独立的、可重复执行的监控任务，并将其提交到线程池中等待调度。
4.  **并发监控**: 线程池中的线程定时（根据 `poll_interval_seconds`）执行监控任务。每个任务负责一个钱包地址，通过调用 `PolymarketDataClient.get_activity()` 方法来获取该钱包的最新交易活动。
5.  **数据持久化与记录**: 获取到交易数据后，任务会调用 `DatabaseHandler` 模块。该模块负责将新的、未被记录过的交易数据存入PostgreSQL数据库，并通过 `Logger` 记录操作日志。

```mermaid
flowchart TD
    A[加载配置 config.yaml] --> B(初始化 WalletMonitor);
    B --> C{创建线程池和 PolymarketDataClient};
    C --> D[为每个钱包地址创建监控任务];
    D --> E{定时调度任务};
    E --> F[线程执行: 调用 get_activity];
    F --> G[polymarket-apis SDK];
    G --> H{有新交易?};
    H -->|是| I[存入 PostgreSQL 数据库];
    I --> J[记录日志];
    J --> E;
    H -->|否| E;
```

### 2.1 模块划分

*   **`ConfigLoader`**: 负责读取和解析 `config.yaml` 文件，为整个应用提供统一、只读的配置访问接口。
*   **`WalletMonitor`**: 核心调度器。负责初始化、管理线程池和 `PolymarketDataClient`，并根据配置安排和调度所有钱包的监控任务。
*   **`DatabaseHandler`**: 负责数据库的连接、初始化和所有CRUD操作。它使用 Peewee ORM 将获取的交易数据写入 PostgreSQL 数据库。
*   **`Logger`**: 提供一个全局的日志记录器，用于输出不同级别的运行信息（如DEBUG, INFO, ERROR）。

### 2.2 核心流程

1.  程序入口调用 `ConfigLoader` 加载 `config.yaml`。
2.  使用加载的配置实例化 `WalletMonitor` 类，该类在初始化时会创建一个 `PolymarketDataClient` 实例。
3.  `WalletMonitor` 调用其 `start()` 方法，该方法会启动内部的线程池，并为钱包列表中的每个地址提交一个永久运行的监控任务。
4.  每个监控任务在一个独立的线程中，按照预设的时间间隔（`poll_interval_seconds`）被周期性触发。
5.  任务触发时，使用 `PolymarketDataClient` 实例调用 `get_activity(user=wallet_address, type="TRADE")` 获取对应钱包的最新交易活动列表。
6.  获取数据后，任务调用 `DatabaseHandler` 将这批交易数据传入。`DatabaseHandler` 负责比对数据库，只将新的、未记录的交易（通过`transaction_hash`唯一标识）存入数据库。
7.  记录本次轮询的结果（如发现N条新交易），完成一次监控循环，然后线程休眠，等待下一次触发。

## 3. 数据模型/API设计

### 3.1 数据结构

**配置文件 (`config.yaml`)**

```yaml
database:
  url: "postgresql://user:password@localhost:5432/polymarket_bot"

monitoring:
  wallets:
    - "0x..."
    - "0x..."
  poll_interval_seconds: 60
```

**交易数据模型 (`Trade`)**
使用 Peewee 定义的数据库表结构，字段将根据 `polymarket_apis` 返回的 `Activity` 对象进行调整。

```mermaid
classDiagram
    class Trade {
        <<Model>>
        +String transaction_hash PK
        +String wallet_address
        +String market_id
        +String outcome
        +Decimal amount
        +Decimal price
        +DateTime timestamp
    }
```

### 3.2 API 设计

**`WalletMonitor` 类**
```python
class WalletMonitor:
    def __init__(self, wallets: list[str], poll_interval: int, db_url: str):
        """初始化监控器，配置钱包、轮询间隔和数据库"""
        pass

    def start(self):
        """启动所有监控任务和线程池"""
        pass

    def stop(self):
        """平滑地停止所有监控任务"""
        pass
```

**`ConfigLoader` 模块**
```python
def load_config(path: str = "config.yaml") -> dict:
    """从指定路径加载 YAML 配置文件并返回一个字典"""
    pass
```

**`DatabaseHandler` 模块**
```python
class DatabaseHandler:
    @staticmethod
    def initialize_database(db_url: str):
        """连接数据库并创建表结构"""
        pass

    @staticmethod
    def save_trades(trades_data: list[dict]) -> int:
        """保存一批交易数据，返回新插入的记录数"""
        pass
```

## 4. 详细设计

### 4.1 流程/模块一：钱包监控 (`WalletMonitor`)

`WalletMonitor` 是整个模块的“大脑”。其 `__init__` 方法接收配置参数，创建一个 `PolymarketDataClient` 实例，一个 `concurrent.futures.ThreadPoolExecutor` 实例，以及一个用于优雅停止的 `threading.Event`。

`start` 方法会遍历钱包列表，为每个钱包地址向线程池提交一个 `_monitor_wallet` 任务。

核心的私有方法 `_monitor_wallet` 是一个无限循环。在循环的每一次迭代中，它会：
1.  调用 `self.data_client.get_activity()` 获取数据。
2.  将返回的 `Activity` 对象列表转换为适合存入数据库的字典列表。
3.  调用 `DatabaseHandler.save_trades()` 保存数据。
4.  调用 `Logger` 记录信息。
5.  使用 `self.stop_event.wait(self.poll_interval)` 来实现定时和可中断的等待。

**交互时序图**
```mermaid
sequenceDiagram
    participant Monitor as WalletMonitor
    participant SDK as polymarket-apis
    participant DB as DatabaseHandler
    participant Logger

    loop 定时轮询
        Monitor->>SDK: get_activity(user=wallet_address, type="TRADE")
        activate SDK
        SDK-->>Monitor: [activity1, activity2, ...]
        deactivate SDK

        Monitor->>Monitor: 转换 Activity 对象为字典
        Monitor->>DB: save_trades(trade_list)
        activate DB
        Note right of DB: 在单个事务中<br/>批量插入新交易<br/>(on_conflict_ignore)
        DB-->>Monitor: num_new_trades
        deactivate DB

        alt num_new_trades > 0
            Monitor->>Logger: log.info("Saved X new trades")
        else
            Monitor->>Logger: log.debug("No new trades")
        end
    end
```