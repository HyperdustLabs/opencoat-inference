# OpenCOAT A2A Trusted Inference Service

## 产品需求与架构初稿 v0.2

> 本文档用于把当前讨论沉淀成可交给 Codex / 开发团队继续做技术实现分析的产品与架构说明。
>
> 暂定名称：**OpenCOAT**。如果代码库或品牌当前叫 OpenCode，可在后续统一命名。本文统一使用 OpenCOAT 表示这个“可信 Agent-to-Agent LLM 推理访问层”。

---

# 1. 一句话定位

**OpenCOAT 是一个面向 AI 智能体的可信 A2A LLM 推理服务层。**

它不是给人类直接使用的 API Gateway，而是让一个智能体可以可信地向另一个推理服务智能体请求 LLM 推理能力，并通过微支付完成结算。

英文定位：

> **No API for humans. Only trusted A2A LLM access.**
>
> **OpenCOAT is an agentic inference layer enabling trusted agent-to-agent access to LLM services.**

---

# 2. 核心判断

现在大多数智能体产品的用户体验仍然是：

```text
用户安装 Agent
  ↓
系统要求用户填写 OpenAI / Claude / Gemini / DeepSeek API Key
  ↓
用户需要自己管理 API Key、余额、模型、价格和可用性
```

这不是 Agent-native 的体验，而是 Human-to-API 的旧模式。

OpenCOAT 要解决的问题是：

```text
不是让人类管理 API Key，
而是让智能体自己发现、协商、支付并调用可信推理服务。
```

也就是说，OpenCOAT 的核心不是“卖 token”，而是把 LLM 推理服务变成智能体之间可以交易的高频基础服务。

---

# 3. 为什么这是 Agent Economy 的高频场景

很多项目都在讲 Agent-to-Agent、Agent Society、Agent Economy，但一个关键问题一直没有被清楚回答：

```text
Agent 之间到底交易什么？
```

OpenCOAT 的判断是：

```text
LLM 推理服务是 Agent Economy 的第一个高频刚需。
```

原因：

1. 几乎所有智能体都需要推理能力。
2. 推理调用天然是高频、可计量、可定价的服务。
3. 推理服务可以用微支付结算。
4. 推理服务可以被声誉系统约束。
5. 推理服务适合从 Human-to-API 升级为 Agent-to-Agent。

所以 OpenCOAT 的目标不是做普通 AI API 中转站，而是把“推理服务”做成智能体经济中的基础交易品类。

---

# 4. 目标用户与使用场景

## 4.1 目标用户

第一类用户是个人终端用户，例如运行 OpenClaw 的用户。

他们可能是：

- 普通个人用户
- 自动化 Agent 用户
- 浏览器 Agent 用户
- 小型开发者
- 养虾用户群体
- 需要私有智能体帮自己做事的人

这些用户的共同点是：

```text
他们想运行自己的智能体，
但不想理解和管理 LLM API。
```

## 4.2 用户核心诉求

用户想要的是：

```text
我安装一个智能体，
它能马上工作，
不需要我去找 API Key，
不需要我比较模型，
不需要我理解 token 价格，
不需要我处理灰色中转站风险。
```

## 4.3 智能体核心诉求

用户的本地智能体想要的是：

```text
当我需要推理能力时，
我可以自动找到可信的推理服务智能体，
协商价格，
完成支付，
获得结果，
继续执行任务。
```

---

# 5. 当前用户痛点

## 5.1 API Key 门槛

当前大多数 Agent 第一次运行时会要求：

```text
请输入 OpenAI API Key
```

这会导致大量用户流失。

主要问题包括：

- 用户不知道去哪里申请 API Key
- 不知道该用哪个模型
- 不知道如何充值
- 不知道怎么控制成本
- 担心 key 泄露
- 使用灰色中转站存在风险
- Agent 无法自主选择推理服务

## 5.2 API 中转站的灰色问题

传统 AI API 中转站往往只是：

```text
请求转发 + 统一接口 + token 计费
```

但很多地区的中转站存在灰色地带：

- 上游 API 来源不透明
- 是否合规不清楚
- 是否模型替换不清楚
- 是否记录用户数据不清楚
- 出问题无法追责

OpenCOAT 不应走“灰色中转站”的路线，而应走：

```text
可信推理服务智能体网络
```

核心是身份、声誉、支付、审计和可追责。

---

# 6. 新用户体验：从安装到第一次推理

下面是用户首次使用 OpenCOAT 的理想流程。

## 6.1 阶段一：用户安装 OpenClaw

用户从 OpenClaw 官方或社区渠道安装本地智能体。

首次启动时，OpenClaw 检测当前没有可用推理服务。

系统提示：

```text
你的智能体需要 LLM 推理服务才能工作。
你可以手动配置 API Key，或启用 OpenCOAT 可信推理服务。
```

选项：

```text
[手动配置 API Key]
[启用 OpenCOAT]
```

如果 OpenCOAT 尚未成为 OpenClaw 官方服务商，也可以先通过插件、安装包、社区版本或文档引导的方式完成接入。

## 6.2 阶段二：用户启用 OpenCOAT

用户点击：

```text
启用 OpenCOAT
```

系统展示简短说明：

```text
OpenCOAT 可以让你的智能体自动访问可信 LLM 推理服务。
无需你管理 API Key。
推理服务按次微支付结算。
首次启用将获得免费试用额度。
```

用户点击：

```text
开始使用
```

## 6.3 阶段三：创建或绑定钱包

因为 OpenCOAT 使用 x402 或类似协议进行智能体间微支付，所以需要一个钱包。

但钱包体验必须尽量 Web2 化。

推荐使用：

- Privy
- Dynamic
- Turnkey
- Particle Network
- Coinbase Smart Wallet
- 其他 embedded wallet 方案

用户体验目标：

```text
用户不需要先理解区块链。
用户只需要用邮箱、Google、Passkey 或手机号完成登录。
钱包在后台自动创建。
```

界面文案：

```text
为你的智能体创建一个支付账户。
该账户用于小额支付 LLM 推理服务。
```

避免文案：

```text
创建链上钱包
导入助记词
配置 RPC
购买 Gas
```

## 6.4 阶段四：发放试用额度

钱包创建后，OpenCOAT 给用户发放初始试用额度。

例如：

```text
$0.10 ~ $1.00 USDC 等值额度
```

这笔额度用于让智能体立即完成前几次推理请求。

关键点：

```text
用户第一次使用时不能卡在“没有钱、不能推理”的状态。
```

## 6.5 阶段五：智能体自动发现推理服务

用户的 OpenClaw Agent 启动后，不再直接问用户要 API Key，而是向 OpenCOAT 请求可用推理服务。

流程：

```text
OpenClaw Agent
  ↓
请求 OpenCOAT Service Discovery
  ↓
获得一组可用 Inference Agents
  ↓
根据价格、延迟、能力、声誉选择服务方
```

## 6.6 阶段六：智能体间协商

OpenClaw Agent 作为消费者智能体，向一个或多个推理服务智能体发起询价。

询价内容包括：

- 任务类型
- 预计 token 数量
- 质量要求
- 延迟要求
- 最大可接受价格
- 是否需要高可信验证
- 是否允许缓存
- 是否允许多模型协作

推理服务智能体返回：

- 支持的模型
- 价格
- 预计延迟
- 当前可用性
- 声誉分数
- 服务条款
- x402 支付要求

## 6.7 阶段七：x402 微支付

当消费者智能体选定服务方后，推理服务智能体返回 HTTP 402 Payment Required 或类似支付挑战。

流程：

```text
Consumer Agent 请求推理服务
  ↓
Inference Agent 返回 402 Payment Required
  ↓
x402 Facilitator 验证支付条件
  ↓
Consumer Agent 自动完成稳定币微支付
  ↓
Inference Agent 开始执行推理
```

OpenCOAT 可以作为 x402 facilitator 或协调层，从每笔交易中收取极小比例的平台服务费。

## 6.8 阶段八：返回推理结果

推理服务智能体调用上游 LLM 或自身模型完成推理。

返回内容包括：

- 推理结果
- 使用模型
- 价格
- 延迟
- provider 信息
- 是否经过验证
- 结果摘要 hash
- 服务 Agent ID
- 可选审计记录

OpenClaw Agent 接收结果后继续执行用户任务。

## 6.9 阶段九：声誉更新

任务完成后，OpenCOAT 更新服务方声誉。

声誉来源：

- 是否成功返回
- 延迟是否达标
- 结果是否被下游 Agent 接受
- 是否有用户或 Agent 投诉
- 是否通过抽检
- 是否发生退款或争议

通过 ERC-8004 或类似机制记录 Agent 身份与声誉。

---

# 7. 冷启动设计

冷启动分为三层：用户冷启动、支付冷启动、服务方冷启动。

## 7.1 用户冷启动

问题：

```text
用户第一次安装 Agent 时，没有 API Key，也没有钱包，也没有余额。
```

解决：

```text
OpenCOAT 提供一键启用 + embedded wallet + 免费试用额度。
```

目标是让用户在 1 分钟内完成第一次推理。

## 7.2 支付冷启动

问题：

```text
智能体间微支付需要钱包和稳定币。
普通用户第一次没有这些东西。
```

解决：

1. 后台创建 embedded wallet。
2. 平台发放试用额度。
3. 额度用完前提示充值。
4. 支持信用卡、Apple Pay、Google Pay 等入口购买稳定币或充值平台余额。
5. 用户不需要直接处理 Gas。

## 7.3 推理服务方冷启动

问题：

```text
第一批推理服务智能体没有声誉。
```

解决：

- OpenCOAT 官方启动若干默认 Inference Agents
- 与合规上游 LLM 服务商合作
- 白名单早期服务方
- 要求服务方质押
- 小额任务逐步积累声誉
- 高价值任务必须通过额外验证

---

# 8. OpenCOAT 的系统角色

OpenCOAT 不是单一 API 代理，而是一个多角色协调系统。

## 8.1 Consumer Agent

消费者智能体。

例如用户本地运行的 OpenClaw Agent。

职责：

- 判断自己是否需要推理服务
- 向 OpenCOAT 查询服务方
- 发起询价
- 选择服务方
- 发起 x402 支付
- 接收推理结果
- 对服务进行反馈

## 8.2 Inference Agent

推理服务智能体。

它可以：

- 调用 OpenAI / Claude / Gemini / DeepSeek 等上游模型
- 调用本地 vLLM / Ollama / TGI 模型
- 调用第三方模型聚合服务
- 提供专业领域推理能力
- 自主报价
- 接受微支付
- 维护声誉

它不是普通 API Key 中转站，而是一个有身份、有声誉、有服务历史的推理服务主体。

## 8.3 OpenCOAT Facilitator

平台协调者。

职责：

- 服务发现
- 价格发现
- x402 支付协助
- 钱包 onboarding
- 试用额度发放
- 路由策略
- 声誉记录
- 争议处理
- 平台抽佣

## 8.4 Reputation / Identity Registry

身份与声誉注册层。

可采用 ERC-8004 或类似机制。

职责：

- 注册 Agent 身份
- 记录服务声明
- 记录历史评价
- 记录验证结果
- 支持信任发现

## 8.5 Upstream LLM Provider

上游 LLM 服务商。

包括：

- OpenAI
- Anthropic
- Google Gemini
- DeepSeek
- Mistral
- xAI
- Cohere
- Groq
- Cerebras
- 自部署模型
- 第三方合规模型服务商

---

# 9. 上游 LLM 接入策略

OpenCOAT 有两种上游接入路径。

## 9.1 官方接入路径

OpenCOAT 与 LLM 厂商或云厂商建立合规协议。

优点：

- 合规性强
- 服务稳定
- 企业客户更容易接受
- 有利于品牌信誉

缺点：

- 商务推进慢
- 早期门槛高
- 需要较强信用和体量

## 9.2 开放服务方路径

允许第三方拥有 LLM 资源的人或组织，把自己的服务封装为 Inference Agent。

他们可能拥有：

- 官方 API Key
- 企业 API 额度
- 自建 GPU 集群
- 本地模型服务
- 专业领域模型

OpenCOAT 给他们提供：

- Agent 注册
- x402 收款
- 服务发布
- 声誉系统
- 流量入口
- 审计与风控框架

优点：

- 扩展快
- 更去中心化
- 可以形成 marketplace

风险：

- 上游合规性不透明
- 模型真实性需要验证
- 可能出现灰色 API 来源
- 需要强风控和服务分层

## 9.3 推荐策略

MVP 阶段建议采用混合模式：

```text
官方默认 Inference Agents
  +
白名单第三方 Inference Agents
```

不要一开始完全开放。

先建立可信体验，再逐步放开第三方服务方。

---

# 10. 信任机制设计

## 10.1 核心信任转换

OpenCOAT 的核心信任逻辑是：

```text
不试图证明每一次推理绝对正确，
而是让可信 Agent 的长期收益大于短期作恶收益。
```

也就是说，去中心化推理的可信问题不是纯密码学问题，而是声誉经济学问题。

## 10.2 ERC-8004 的作用

ERC-8004 可用于：

- Agent Identity
- Reputation
- Validation
- Service Metadata
- 服务历史追踪

每个 Inference Agent 都应该有一个可验证身份。

## 10.3 声誉维度

建议声誉至少包括：

- 成功率
- 平均延迟
- 价格稳定性
- 退款率
- 投诉率
- 抽检通过率
- 模型真实性
- 服务连续性
- 历史交易量
- 质押金额

## 10.4 风险分层

不同任务采用不同信任策略。

低风险任务：

```text
直接基于声誉调用
```

中风险任务：

```text
随机抽检 / 多模型比对
```

高风险任务：

```text
多 Agent 共识 / 人类确认 / TEE / zkML / 更高质押
```

---

# 11. 支付与商业模式

## 11.1 支付方式

推荐采用：

```text
x402 + stablecoin micropayment
```

基本流程：

```text
请求服务
  ↓
返回 402 Payment Required
  ↓
消费者智能体支付
  ↓
服务方执行推理
  ↓
结算完成
```

## 11.2 计费单位

可支持多种计费方式：

- 按次请求
- 按 token
- 按任务类型
- 按延迟等级
- 按模型等级
- 按验证强度

## 11.3 OpenCOAT 收入模式

OpenCOAT 不直接卖 token，而是收取协调服务费。

可能方式：

```text
每笔交易抽成 0.5% ~ 3%
```

或：

```text
每次请求固定 facilitator fee
```

或：

```text
服务方上架费 / 质押费 / 高级路由费
```

## 11.4 为什么不是传统订阅

因为这里的消费者是智能体，不是人类。

智能体更适合：

```text
按请求、按任务、按结果进行微支付。
```

这比人类订阅更适合 A2A 场景。

---

# 12. MVP 产品范围

MVP 不需要一开始实现完整去中心化网络。

目标是验证一件事：

```text
一个本地 Agent 可以无需人类 API Key，
通过 OpenCOAT 发现并支付调用一个可信 Inference Agent。
```

## 12.1 MVP 必须包含

1. OpenClaw 插件或集成 SDK
2. OpenCOAT 服务发现 API
3. Embedded wallet onboarding
4. 免费试用额度
5. x402 支付流程
6. 一个官方 Inference Agent
7. 一个上游 LLM 接入
8. 基础交易记录
9. 基础声誉记录
10. 用户可查看余额与推理记录

## 12.2 MVP 暂不需要

1. 完整 ERC-8004 上链实现
2. 完整去中心化 marketplace
3. 多服务方自由上架
4. zkML 验证
5. 复杂仲裁系统
6. 完整 DAO 治理

这些可以作为后续阶段。

---

# 13. MVP 用户旅程

## 13.1 第一次使用

```text
用户安装 OpenClaw
  ↓
OpenClaw 检测没有推理服务
  ↓
提示启用 OpenCOAT
  ↓
用户用邮箱/Google 登录
  ↓
自动创建 embedded wallet
  ↓
获得 $0.10 试用额度
  ↓
OpenClaw 发起第一次推理
  ↓
OpenCOAT 自动完成 x402 支付
  ↓
Inference Agent 返回结果
  ↓
用户看到 Agent 正常工作
```

## 13.2 额度不足

```text
余额不足
  ↓
Agent 暂停高成本推理
  ↓
用户收到提示
  ↓
可以充值或继续使用低成本模型
```

提示文案：

```text
你的智能体推理余额即将用尽。
充值后它可以继续自动访问可信 LLM 推理服务。
```

## 13.3 用户查看记录

用户可以查看：

- 每次推理花费
- 使用了哪个 Inference Agent
- 使用了哪个模型
- 花费多少
- 延迟多少
- 是否成功

但默认界面不应过于技术化。

---

# 14. 技术架构初稿

## 14.1 高层架构

```text
User
  ↓
OpenClaw Local Agent
  ↓
OpenCOAT SDK / Plugin
  ↓
OpenCOAT Facilitator
  ↓
Service Discovery + Reputation
  ↓
Inference Agent
  ↓
Upstream LLM Provider
```

支付路径：

```text
Consumer Agent Wallet
  ↓
x402 Payment
  ↓
Inference Agent Wallet
  ↓
OpenCOAT Fee Split
```

声誉路径：

```text
Inference Result
  ↓
Consumer Feedback
  ↓
Validation / Audit
  ↓
Reputation Update
  ↓
ERC-8004 Registry 或内部 Reputation DB
```

## 14.2 组件列表

### OpenCOAT SDK

集成在 OpenClaw 或其他 Agent Runtime 内。

功能：

- 检测推理需求
- 请求服务发现
- 处理 x402 支付
- 管理钱包会话
- 调用 Inference Agent
- 返回结果给宿主 Agent

### Facilitator Service

OpenCOAT 后端核心服务。

功能：

- x402 facilitator
- 服务发现
- 路由策略
- 余额管理
- 试用额度管理
- 交易记录
- 平台费用结算

### Inference Agent Runtime

服务方运行的 Agent 服务。

功能：

- 服务注册
- 报价
- 接收请求
- 验证支付
- 调用上游 LLM
- 返回结果
- 上报服务状态

### Reputation Service

功能：

- Agent 身份管理
- 声誉计算
- 交易历史
- 服务质量统计
- 风险评分

### Wallet Service

功能：

- embedded wallet 创建
- 钱包绑定
- 余额查询
- 充值
- 支付签名
- gas abstraction

---

# 15. 关键 API 初稿

## 15.1 服务发现

```http
GET /v1/inference-agents
```

返回：

```json
{
  "agents": [
    {
      "agent_id": "agent_123",
      "name": "OpenCOAT Default GPT Agent",
      "models": ["gpt-5", "gpt-5-mini"],
      "price": "0.0001 USDC / 1K tokens",
      "latency_ms": 1200,
      "reputation": 0.98,
      "payment": "x402",
      "endpoint": "https://..."
    }
  ]
}
```

## 15.2 推理请求

```http
POST /v1/a2a/inference
```

请求：

```json
{
  "consumer_agent_id": "agent_consumer_001",
  "task_type": "general_reasoning",
  "input": "...",
  "max_price": "0.01 USDC",
  "quality": "standard",
  "latency": "normal"
}
```

可能返回：

```http
402 Payment Required
```

支付完成后返回：

```json
{
  "result": "...",
  "provider_agent_id": "agent_123",
  "model": "gpt-5-mini",
  "cost": "0.002 USDC",
  "latency_ms": 1340,
  "receipt": "..."
}
```

## 15.3 声誉更新

```http
POST /v1/reputation/feedback
```

请求：

```json
{
  "provider_agent_id": "agent_123",
  "consumer_agent_id": "agent_consumer_001",
  "request_id": "req_456",
  "success": true,
  "rating": 5,
  "latency_ms": 1340
}
```

---

# 16. 分阶段路线图

## Phase 0：概念验证

目标：跑通一次 A2A 推理支付。

内容：

- 一个 Consumer Agent
- 一个 Inference Agent
- 一个 OpenCOAT Facilitator
- 一个 embedded wallet
- 一次 x402 微支付
- 一个上游 LLM

## Phase 1：OpenClaw 插件

目标：让 OpenClaw 用户可以启用 OpenCOAT。

内容：

- OpenClaw 插件
- 首次启动引导
- 试用额度
- 余额面板
- 默认推理服务

## Phase 2：多 Inference Agents

目标：形成最小 marketplace。

内容：

- 多服务方注册
- 报价机制
- 路由选择
- 基础声誉分
- 服务方 dashboard

## Phase 3：ERC-8004 集成

目标：把身份与声誉上链或接入标准。

内容：

- Agent identity
- Reputation registry
- Validation records
- Service metadata

## Phase 4：可信推理增强

目标：提升高价值任务可信度。

内容：

- 随机抽检
- 多模型比对
- 争议机制
- 质押 / slashing
- 验证服务方

---

# 17. 给 Codex 的实现分析任务

可以把以下问题交给 Codex 或开发团队分析。

## 17.1 当前代码库差距分析

请分析当前 OpenCOAT / OpenCode 代码库是否已有以下能力：

1. 是否有插件机制可以集成到 OpenClaw？
2. 是否已有 API gateway / routing 逻辑？
3. 是否已有用户账户系统？
4. 是否已有钱包集成？
5. 是否已有支付或计费模块？
6. 是否已有 Agent registry？
7. 是否已有服务发现机制？
8. 是否已有模型调用抽象层？
9. 是否已有日志、审计、使用量统计？
10. 是否适合接入 x402？

## 17.2 MVP 实现建议

请给出最小实现路径：

1. Consumer Agent SDK 如何设计？
2. Inference Agent 服务端如何设计？
3. Facilitator 如何实现？
4. x402 支付如何接入？
5. embedded wallet 如何接入？
6. 免费额度如何发放与限制？
7. 推理记录如何保存？
8. 声誉系统第一版如何实现？
9. 哪些部分先不上链？
10. 哪些部分必须预留 ERC-8004 兼容接口？

## 17.3 推荐输出

请 Codex 输出：

- 当前代码库能力评估
- 需要新增的模块
- 推荐目录结构
- MVP 开发任务拆分
- 数据库 schema 初稿
- API 路由设计
- 关键风险点
- 两周内可完成的 POC 范围

---

# 18. 当前最重要的产品原则

1. 用户不应该先懂 API Key。
2. 用户不应该先懂钱包。
3. 用户不应该先懂稳定币。
4. 用户不应该先懂模型选择。
5. 用户应该看到的是：我的 Agent 可以马上工作。
6. 支付、路由、模型选择、声誉判断，应该尽量由 Agent 与 OpenCOAT 自动完成。
7. OpenCOAT 不应定位成灰色 API 中转站，而应定位成可信 A2A LLM 推理访问层。

---

# 19. 最终总结

OpenCOAT 的核心产品不是 API Gateway，而是：

```text
Agent-to-Agent trusted inference access.
```

它要把现在的人类 API 使用流程：

```text
人类申请 API Key
人类充值
人类选模型
人类控制成本
人类判断服务质量
```

升级为：

```text
智能体发现服务
智能体协商价格
智能体微支付
智能体调用推理
智能体更新声誉
```

这就是从：

```text
Human-to-API
```

到：

```text
Agent-to-Agent Inference Economy
```

的转变。

OpenCOAT 的早期 MVP 应该围绕一个最小闭环展开：

```text
OpenClaw Agent
  ↓
OpenCOAT Plugin
  ↓
Embedded Wallet + Free Credit
  ↓
x402 Micropayment
  ↓
Inference Agent
  ↓
LLM Result
  ↓
Reputation Record
```

只要这个闭环跑通，就可以开始验证 OpenCOAT 作为 Agent Economy 高频基础服务的市场价值。

