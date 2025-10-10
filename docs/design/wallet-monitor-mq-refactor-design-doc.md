# [钱包监控重构：消息队列与实时通知] 设计文档

## 1. 背景

### 1.1 功能简介

本次设计旨在对现有的 `WalletMonitor` 模块进行重构。当前实现将监控到的钱包活动直接存入数据库，而新方案将引入一个抽象的消息队列层，用于实时处理和分发这些活动。这将使系统从一个批处理、持久化优先的架构，演变为一个低延迟、事件驱动的实时通知架构，为后续的跟单交易、数据分析等多个消费场景提供灵活、解耦的数据源。

### 1.2 需求与痛点

- **痛点一 (紧耦合)**: `WalletMonitor` 与 `DatabaseHandler` 强耦合，所有数据都必须写入数据库。这使得添加新的数据消费方（如实时警报、UI更新）变得困难，因为它们都得轮询数据库，效率低下。
- **痛点二 (高延迟)**: 基于轮询和数据库写入的模式，从发现交易到可供下游使用存在固有延迟，不适合对实时性要求极高的复制交易场景。
- **需求一 (实时性)**: 需要一个发布/订阅（Pub/Sub）机制。当监控到新活动时，能够立即通知所有订阅了该钱包的模块（如交易执行器）。
- **需求二 (可扩展性)**: 系统应支持多种消息队列后端。初期可以快速实现一个内存队列用于开发和测试，但生产环境需要能无缝切换到更健壮的系统，如 RabbitMQ。
- **需求三 (灵活性)**: 监控逻辑应与通知逻辑分离。监控器只负责抓取数据并推送到队列，而队列系统负责将数据可靠地分发给一个或多个订阅者。

### 1.3 使用场景

- **场景**: 一个自动跟单机器人需要实时响应“聪明钱”钱包的交易。
- **步骤**:
  1. 机器人启动时，向消息队列系统订阅一个或多个目标钱包地址，并注册一个回调函数（`handle_new_trade`）。
  2. `WalletMonitor` 模块发现目标钱包有新交易活动。
  3. 它将这些活动数据作为消息发布到消息队列中。
  4. 消息队列系统立即将该消息推送给所有订阅者，触发机器人的 `handle_new_trade` 回调。
  5. 机器人几乎在交易发生的同时就收到了通知，并可以立即执行跟单操作。

## 2. 概要设计

本方案的核心是引入一个 `ActivityQueue` 抽象基类，它定义了消息队列的基本行为（入队和订阅）。然后提供至少两种实现：一个用于本地开发的 `InMemoryActivityQueue` 和一个用于生产的 `RabbitMQActivityQueue`。`WalletMonitor` 将不再与 `DatabaseHandler` 交互，而是将获取到的活动推送到 `ActivityQueue` 中。

```mermaid
flowchart TD
    A[加载配置 config.yaml] --> B{选择队列类型};
    B -->|memory| C1[创建 InMemoryActivityQueue];
    B -->|rabbitmq| C2[创建 RabbitMQActivityQueue];
    
    subgraph "初始化阶段"
        C1 --> D(初始化 WalletMonitor);
        C2 --> D(初始化 WalletMonitor);
        E[交易机器人/其他消费者] --> F(调用 subscribe 方法);
        F --> C1;
        F --> C2;
    end

    subgraph "运行阶段"
        D --> G{定时监控};
        G --> H[调用 get_activity];
        H --> I{有新活动?};
        I -->|是| J[调用 enqueue 方法];
        J --> C1;
        J --> C2;
        C1 --> K[触发内存回调];
        C2 --> L[通过 Broker 推送消息];
        K --> M(执行订阅者回调函数);
        L --> M;
        I -->|否| G;
    end
```

### 2.1 模块划分

*   **`WalletMonitor` (重构)**: 不再负责数据持久化，而是将获取到的新 `activity` 列表推送至注入的 `ActivityQueue` 实例。启动时，将以当前时间作为监控的起点。
*   **`ActivityQueue` (新增, 抽象基类)**: 定义统一的接口，包含 `enqueue(wallet_address, activities)` 和 `subscribe(wallet_address, callback)` 两个核心方法。
*   **`InMemoryActivityQueue` (新增, 实现类)**: `ActivityQueue` 的内存实现。使用一个字典来维护订阅关系，当消息入队时，直接在内存中查找并调用对应的回调函数。
*   **`RabbitMQActivityQueue` (新增, 待实现)**: `ActivityQueue` 的 RabbitMQ 实现。使用 `pika` 库，`enqueue` 会将消息发布到 RabbitMQ 的交换机，`subscribe` 会创建一个队列并绑定到相应的 `routing_key`（如钱包地址）。
*   **`ConfigLoader` (修改)**: 增加 `queue` 相关配置，包括 `type` (memory/rabbitmq) 和 RabbitMQ 的连接参数。

### 2.2 核心流程

1.  **启动**: 程序通过 `ConfigLoader` 加载配置，确定 `queue.type`。
2.  **依赖注入**: 根据配置创建 `InMemoryActivityQueue` 或 `RabbitMQActivityQueue` 的实例。
3.  **初始化监控器**: 将队列实例注入到 `WalletMonitor` 的构造函数中。
4.  **订阅**: 外部模块（如 `main.py` 或未来的交易模块）调用队列实例的 `subscribe` 方法，注册对特定钱包地址感兴趣的回调函数。
5.  **开始监控**: `WalletMonitor.start()` 启动后，`_monitor_wallet` 任务不再从数据库读取检查点，而是以任务启动的当前时间 `datetime.now()` 作为初始 `after` 参数来获取活动。
6.  **消息入队**: 当 `get_activity` 返回新的活动列表时，`WalletMonitor` 调用 `self.activity_queue.enqueue(wallet_address, activities)`。
7.  **消息分发**:
    *   **内存队列**: `enqueue` 方法查找内部的订阅者字典，并为每个匹配的回调函数提交一个异步执行任务（使用线程池避免阻塞）。
    *   **RabbitMQ**: `enqueue` 方法将活动序列化（如JSON）并发布到 Broker。Broker 负责将消息路由到订阅了该钱包地址的消费者队列。
8.  **执行回调**: 订阅者的回调函数被触发，接收到新的活动列表作为参数。

## 3. 数据模型/API设计

### 3.1 数据结构

**配置文件 (`config.yaml` 更新)**
```yaml
database:
  url: "postgresql://user:password@localhost:5432/polymarket_bot" # 保留，可能用于其他功能

monitoring:
  wallets:
    - "0x..."
  poll_interval_seconds: 30
  batch_size: 500

# 新增队列配置
queue:
  type: "memory"  # 可选: "memory" 或 "rabbitmq"
  rabbitmq:
    host: "localhost"
    port: 5672
    username: "guest"
    password: "guest"
    exchange: "polymarket_activities"
```

**类关系图**
```mermaid
classDiagram
    class ActivityQueue {
        <<Abstract>>
        +enqueue(wallet_address: str, activities: list)
        +subscribe(wallet_address: str, callback: Callable)
    }

    class InMemoryActivityQueue {
        -subscribers: dict
        -executor: ThreadPoolExecutor
        +enqueue(wallet_address: str, activities: list)
        +subscribe(wallet_address: str, callback: Callable)
    }

    class RabbitMQActivityQueue {
        -connection: pika.BlockingConnection
        -channel: pika.Channel
        -exchange: str
        +enqueue(wallet_address: str, activities: list)
        +subscribe(wallet_address: str, callback: Callable)
    }

    class WalletMonitor {
        -activity_queue: ActivityQueue
        +__init__(..., activity_queue: ActivityQueue)
        - _monitor_wallet(wallet_address: str)
    }

    WalletMonitor o-- ActivityQueue
    ActivityQueue <|-- InMemoryActivityQueue
    ActivityQueue <|-- RabbitMQActivityQueue
```

### 3.2 API 设计

**`ActivityQueue` (新)**
```python
from abc import ABC, abstractmethod
from typing import Callable, List

class ActivityQueue(ABC):
    @abstractmethod
    def enqueue(self, wallet_address: str, activities: List[dict]):
        """将活动列表放入队列"""
        pass

    @abstractmethod
    def subscribe(self, wallet_address: str, callback: Callable[[List[dict]], None]):
        """订阅指定钱包的活动，注册回调函数"""
        pass
```

**`WalletMonitor` (修改)**
```python
class WalletMonitor:
    def __init__(self, wallets: list[str], poll_interval: int, activity_queue: ActivityQueue, ...):
        """初始化时注入 ActivityQueue 实例，移除 db_url"""
        self.activity_queue = activity_queue
        # ... 其他初始化
    
    # _monitor_wallet 将使用 self.activity_queue.enqueue()
```

## 4. 详细设计

### 4.1 流程/模块一：`WalletMonitor` 重构

`_monitor_wallet` 方法是改动的核心。它将不再需要 `DatabaseHandler`。

1.  **移除检查点**: 不再使用 `DatabaseHandler.get_checkpoint`。每个监控任务启动时，将记录当前时间作为初始同步点。
2.  **获取逻辑**: `get_activity` 的 `after` 参数将使用这个初始时间戳。在分页循环中，`after` 参数会更新为上一批次中最新的活动时间戳，以确保能拉取完一轮中的所有新数据。
3.  **推送队列**: 获取到 `activities` 后，不再调用 `_convert_activities_to_trades` 和 `DatabaseHandler.save_trades`，而是直接调用 `self.activity_queue.enqueue(wallet_address, activities)`。

**交互时序图**
```mermaid
sequenceDiagram
    participant Main as main.py
    participant Monitor as WalletMonitor
    participant Queue as ActivityQueue
    participant Subscriber as TradingBot

    Main->>Queue: subscribe("0xabc...", bot.handle_trade)
    Main->>Monitor: start()

    loop 定时轮询
        Monitor->>Monitor: last_ts = get_latest_timestamp()
        Monitor->>PolymarketAPI: get_activity(after=last_ts)
        PolymarketAPI-->>Monitor: [activity1, activity2]

        alt 有新活动
            Monitor->>Queue: enqueue("0xabc...", [activity1, activity2])
            activate Queue
            Queue-->>Subscriber: bot.handle_trade([activity1, activity2])
            deactivate Queue
            Monitor->>Monitor: 更新 last_ts 为本批次最新时间
        else 无新活动
            Note over Monitor: 等待下次轮询
        end
    end
```

### 4.2 流程/模块二：`InMemoryActivityQueue` 实现

这是一个简单但功能完备的实现，用于快速开发和测试。

1.  **`__init__`**: 初始化一个 `defaultdict(list)` 用于存储订阅者，以及一个 `ThreadPoolExecutor` 用于异步执行回调，避免阻塞 `enqueue` 的调用方（即 `WalletMonitor`）。
    ```python
    self.subscribers = defaultdict(list)
    self.executor = ThreadPoolExecutor(max_workers=10)
    ```
2.  **`subscribe`**: 将传入的 `callback` 添加到对应 `wallet_address` 的列表中。
    ```python
    self.subscribers[wallet_address].append(callback)
    log.info(f"新订阅者已添加至钱包: {wallet_address}")
    ```
3.  **`enqueue`**:
    - 检查 `wallet_address` 是否有订阅者。
    - 如果有，遍历该地址的回调列表。
    - 对于每个回调，使用 `self.executor.submit(callback, activities)` 将其提交到线程池执行。这可以防止某个回调执行缓慢而阻塞整个事件流。
