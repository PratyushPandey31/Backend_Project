# Known Limitations & External Dependencies

This document provides a transparent overview of the known operational boundaries, assumptions, and external dependencies of the **AI Real Estate Portfolio Analyst**, as requested in the engineering evaluation rubric.

---

## 1. Known Limitations

### 1.1 Historical Cost & Capital Appreciation (Seed Dataset Boundary)
- **Constraint:** The provided seed dataset intentionally has blank `purchase_price_inr` values and contains no acquisition dates or timestamps.
- **System Behavior:** The agent refuses to hallucinate historical appreciation percentages, CAGR, or IRR. Instead, it explains that acquisition data is currently unrecorded and prompts the client to supply the purchase year and cost before computing capital gains.

### 1.2 Valuation Sourcing (Internal Records vs. Live Market Comps)
- **Constraint:** Current valuations are derived from `current_estimated_value_inr` stored in the client database.
- **System Behavior:** The system does not currently scrape real-time circle rates, municipal guidance values, or stamp duty registry feeds (e.g., IGR Maharashtra). Dynamic market re-evaluations must be inputted by the client or updated via external feeds.

### 1.3 WhatsApp Simulation vs. Meta WhatsApp Cloud API
- **Constraint:** Section 1 of the assignment explicitly states: *"You do not need to integrate the WhatsApp API. The chat interface is only a simulation of the WhatsApp experience."*
- **System Behavior:** The client interface is a high-fidelity web simulation of WhatsApp Web built with native HTML5, CSS3, and ES6 JavaScript. In a future production phase, the backend webhook handler (`/api/chat`) can be mapped directly to the Meta Graph API / Twilio WhatsApp webhook with zero changes to the underlying agent orchestrator.

### 1.4 Single-Node SQLite Storage at Extreme Scale
- **Constraint:** The current deployment utilizes local SQLite (`portfolio.db`) with Write-Ahead Logging (WAL) and SQLAlchemy ORM.
- **System Behavior:** Ideal for low-latency (< 30ms) single-process execution and local evaluation. For enterprise production exceeding 100,000 concurrent writes, the persistence layer should be migrated to PostgreSQL with connection pooling (`pgbouncer`), as detailed in [`PERFORMANCE.md`](PERFORMANCE.md).

---

## 2. External Dependencies

The system is engineered to have zero proprietary, closed-source, or paid dependencies. It can run 100% offline out-of-the-box using the built-in Autonomous Deterministic Engine.

### 2.1 Core Backend & Web Framework
| Dependency | Version Spec | Purpose |
| :--- | :--- | :--- |
| **`fastapi`** | `>=0.115.0` | High-performance asynchronous REST API framework |
| **`uvicorn[standard]`** | `>=0.30.0` | Production ASGI web server |
| **`pydantic`** | `>=2.0.0` | Request/response data validation and typing |
| **`sqlalchemy`** | `>=2.0.0` | Relational ORM for SQLite database management |
| **`python-dotenv`** | `>=1.0.0` | Environment variable configuration loader |

### 2.2 Model Gateway & Networking
| Dependency | Version Spec | Purpose |
| :--- | :--- | :--- |
| **`openai`** | `>=1.50.0` | Universal client for OpenRouter, OpenAI, and Gemini function calling |
| **`httpx`** | `>=0.27.0` | Asynchronous HTTP client for model gateways |
| **`requests`** | `>=2.31.0` | Synchronous networking and test utilities |

### 2.3 Frontend Presentation
- **Vanilla ES6 JavaScript, HTML5 & CSS3:** Zero bulky frontend frameworks (no React/Node build steps required; single-command startup).
- **FontAwesome 6.4.0 (CDN):** Vector iconography for WhatsApp and business console interfaces.
