# System Architecture — AI Real Estate Portfolio Analyst

## 1. High-Level Architectural Overview

The AI Real Estate Portfolio Analyst is built as an institutional-grade, two-tier system consisting of a client-facing conversational simulation interface (WhatsApp UI) and a business-facing oversight and control console.

The backend leverages a **Dual-Engine Orchestrator**:
1. **Model Gateway Tier:** Integrated with OpenRouter / OpenAI for dynamic model routing (e.g. Gemini 2.5 Flash, LLaMA 3.3 70B, GPT-4o-mini) with native tool/function calling.
2. **Autonomous Deterministic Intelligence Tier:** A zero-dependency deterministic engine providing sub-25ms response latency, deterministic financial accuracy, and 100% functionality without requiring external API keys.

```mermaid
flowchart TD
    subgraph Clients["Presentation Layer (Web Clients)"]
        WA["Simulated WhatsApp Web UI\n(HTML5, CSS3, ES6 JS)"]
        BIZ["Business Observation & Control Console\n(Executive Dashboard, Traces, Flags)"]
    end

    subgraph Gateway["Application & API Gateway (FastAPI)"]
        CORS["CORS & Static Middleware"]
        API["REST Endpoints\n/api/chat, /api/users, /api/conversations, /api/business"]
    end

    subgraph Orchestrator["Agent Orchestration Engine"]
        ContextMgr["Session & Context Manager\n(Multi-Turn Memory)"]
        Router["Model & Execution Router"]
        LLMEngine["LLM Engine\n(OpenRouter / OpenAI Tool Calling)"]
        DetEngine["Deterministic Autonomous Engine\n(Zero-Key / Sub-25ms Fallback)"]
    end

    subgraph Analytics["Deterministic Computation Engines"]
        PE["Portfolio Analytics Engine\n(Yields, AUM, Exposure %, Price/SqFt)"]
        SE["Hypothetical Scenario Sandbox\n(In-Memory What-If Simulation)"]
    end

    subgraph Storage["Persistence & Observability Tier (SQLite / SQLAlchemy)"]
        DB[(portfolio.db)]
        UsersTbl["users"]
        PropsTbl["properties"]
        ConvsTbl["conversation_sessions"]
        MsgsTbl["messages"]
        TracesTbl["tool_traces"]
        FlagsTbl["escalation_flags"]
    end

    WA -->|HTTP POST /api/chat| API
    BIZ -->|HTTP GET /api/business| API
    API --> ContextMgr
    ContextMgr --> Router
    Router -->|If API Key Present| LLMEngine
    Router -->|If No API Key / Offline| DetEngine
    LLMEngine -->|Tool Invocations| PE
    LLMEngine -->|Simulation| SE
    DetEngine -->|Tool Invocations| PE
    DetEngine -->|Simulation| SE
    PE --> Storage
    SE --> Storage
    Storage --> DB
```

---

## 2. Component Breakdown

### 2.1 Presentation Tier
- **Simulated WhatsApp Web UI (`/`)**: 
  - Authentic WhatsApp interface featuring signature dark-green header, responsive chat canvas, custom chat bubbles, timestamps, delivery checkmarks, and typing indicators.
  - Multi-user switcher enabling testing across Rahul Mehta (U001), Priya Shah (U002), Arjun Kapoor (U003), and Neha Jain (U004).
  - Quick action chips for instantaneous testing of all assignment requirements.
- **Business Team Console (`/business`)**:
  - Live KPI cards: Monitored clients, total AUM in ₹ Cr, active sessions, escalated conversations, tool activity count.
  - Master-detail session inspector with real-time transcript viewer.
  - Tool execution trace explorer with latency metrics and JSON payload inspectors.
  - Attention flag resolution workflow and single-click database reset button.

### 2.2 Orchestration Tier
- **Agent Orchestrator (`app/agent/orchestrator.py`)**:
  - Manages conversation lifecycle, session persistence, and multi-turn message history.
  - Integrates tool schema definitions adhering to OpenAI/OpenRouter tool-calling specifications.
  - Handles slot-filling for incomplete property inputs and triggers human handoff flags when boundary conditions are reached.

### 2.3 Analytics & Scenario Engine
- **Portfolio Engine (`app/analytics/portfolio_engine.py`)**:
  - Pure deterministic math module guaranteeing zero hallucination for financial aggregations.
  - Handles Indian currency formatting (`₹ Cr`, `₹ Lakh`), gross rental yield calculation (`annual_rent / value * 100`), asset class exposure, city concentration, and occupancy ratios.
- **Scenario Sandbox (`app/analytics/scenario_engine.py`)**:
  - In-memory property cloning that isolates what-if hypothetical simulations from the live database.
  - Produces before-and-after delta reports for value change, rent change, and yield shifts.

### 2.4 Data Tier (`app/core/database.py`, `models.py`)
- SQLite database (`portfolio.db`) managed via SQLAlchemy 2.0 ORM.
- Auto-seeding mechanism that populates `users.csv` and `properties.csv` on cold start and supports one-click resets.

---

## 3. Data Flow: Conversational Message Execution

```mermaid
sequenceDiagram
    autonumber
    actor Client as HNWI Client
    participant UI as WhatsApp Web UI
    participant API as FastAPI Gateway
    participant Agent as Agent Orchestrator
    participant Tool as Analytics / DB Tools
    participant DB as SQLite Database
    participant Biz as Business Console

    Client->>UI: Types "What if I exclude the Bandra property?"
    UI->>API: POST /api/chat {user_id: "U001", message: "..."}
    API->>Agent: process_message(user_id, message, session_id)
    Agent->>DB: Fetch user profile & recent conversation turns
    Agent->>Tool: tool_simulate_hypothetical(user_id, "Bandra")
    Tool->>DB: Query active properties for U001
    Tool->>Tool: Clone properties in sandbox & exclude P001
    Tool->>Tool: Compute baseline vs hypothetical deltas
    Tool-->>Agent: Return delta metrics (value diff, rent diff, yield diff)
    Agent->>DB: Persist ToolTraceORM (duration_ms, input, output)
    Agent->>DB: Persist MessageORM (sender: assistant, latency_ms)
    Agent-->>API: Return response payload with tool trace & latency
    API-->>UI: Return JSON {reply, latency_ms, tool_traces}
    UI-->>Client: Renders formatted comparison table + latency badge
    Biz-->>DB: Polls /api/business/stats (sees updated trace count)
```

---

## 4. Key Architectural Decisions
See [`DECISIONS.md`](file:///d:/Backend/DECISIONS.md) for full rationale on:
- Monolithic FastAPI vs Microservices.
- Relational SQLite vs Vector Store.
- Deterministic Math Engine vs LLM Calculation.
- In-Memory Scenario Sandbox vs Database Transactions.
- Dual-Engine Fallback Design.
