# 5–10 Minute Presentation Walkthrough Script

> 📹 **Recorded Video Demo**: [`docs/walkthrough_demo.webm`](https://github.com/PratyushPandey31/Backend_Project/blob/main/docs/walkthrough_demo.webm?raw=true)  
> Direct Video Link: [Watch / Download Video](https://github.com/PratyushPandey31/Backend_Project/raw/main/docs/walkthrough_demo.webm)

Use this structured walkthrough to demonstrate the **AI Real Estate Portfolio Analyst** during your interview presentation.

---

## Presentation Agenda (Time: 7–8 Minutes)

1. **Introduction & System Philosophy** (1 min)
2. **WhatsApp Simulated Chat Demonstration** (3.5 mins)
3. **Business Team Observation & Control Console** (2 mins)
4. **Engineering Architecture, Trade-Offs & Edge Cases** (1.5 mins)

---

## Step-by-Step Walkthrough Guide

### Part 1: System Philosophy & Overview (1 Minute)
> *"Hello! Today I'm excited to present EstateIntel, a two-way AI Real Estate Portfolio Analyst designed for High-Net-Worth Individuals. Rather than treating this purely as a chatbot or a static CRM, we designed it around three core engineering principles:*
> 1. *Zero-hallucination deterministic financial analytics: all yields and portfolio totals are calculated in Python, never inside LLM context math.*
> 2. *Dual-interface architecture: an authentic WhatsApp Web client simulation for the investor, paired with a real-time Business Observation and Control interface for the wealth team.*
> 3. *Dual-engine resilience: capable of running dynamically through OpenRouter model gateways, with an autonomous deterministic engine ensuring instant sub-25ms responsiveness without external API dependencies."*

---

### Part 2: Live WhatsApp Client Demonstration (3.5 Minutes)

#### Demo Step 1: Client Selection & Baseline Portfolio Summary
- Open `http://localhost:8000`
- Click on **Rahul Mehta (U001)** on the left sidebar.
- Click the chip: **"What does my portfolio look like?"**
- **Point out to interviewer:**
  - Notice the instant response showing total portfolio value (**₹29.70 Cr**), annual rent (**₹1.32 Cr**), gross yield (**4.44%**), and asset allocation (71% Retail, 29% Commercial Office).
  - Show the latency pill (`⚡ 15ms`) and tool tag (`get_portfolio_summary`).

#### Demo Step 2: Filtering & Query Capabilities (Sample Requests R001 & R002)
- Click the chip: **"Show me my retail properties"**
  - Shows Bandra West (₹12 Cr) and Lower Parel (₹9.2 Cr).
- Click the chip: **"Which of my properties are above ₹10 crore?"**
  - Correctly filters for Bandra West (₹12 Cr).

#### Demo Step 3: Highest Rent & Yield Analysis (Sample Request R004)
- Switch to **Arjun Kapoor (U003)** in the sidebar.
- Click the chip: **"Which property gives me the highest annual rent?"**
  - Returns Golf Course Road, Gurugram generating **₹1.68 Cr/year** at a **7.0% gross yield**.

#### Demo Step 4: Contextual Multi-Turn Conversation & Hypothetical Scenarios
- Switch back to **Rahul Mehta (U001)**.
- Query: *"Tell me about my retail properties."*
- Follow-up: *"Which one is performing better?"*
  - The agent identifies Lower Parel as the superior performer (6.52% yield vs 6.0% for Bandra).
- Follow-up: **"What if I exclude the Bandra property?"**
  - Point out the **Hypothetical What-If Sandbox**:
  - Highlights side-by-side comparison table: portfolio value drops by ₹12 Cr, rent drops by ₹72 Lakh, and yield increases from 4.44% to 5.85%.
  - Emphasize: *Notice the warning: live portfolio data is unaffected.*

#### Demo Step 5: Data Mutation & Action (Sample Requests R005 & R006)
- Send message: *"Change my Bandra retail property value to ₹12.5 crore"*
  - Agent updates P001 in SQLite and confirms new valuation.
- Switch to **Neha Jain (U004)**.
- Send message: *"Add a 3000 sq ft retail property in Indiranagar worth ₹4.2 crore"*
  - Agent extracts entities, generates new property ID `P013`, and persists it to the database.

#### Demo Step 6: Honest Handling of Missing Data (Section 6.2)
- Click the chip: **"What is my appreciation since purchase?"**
  - Point out to interviewer: *The agent does NOT hallucinate a return number. It honestly explains that historical purchase price is unrecorded in the dataset and invites the user to provide it.*

---

### Part 3: Business Observation & Control Interface (2 Minutes)

- Open `http://localhost:8000/business` in a new tab.
- **Showcase KPI Cards:**
  - Active HNWI Clients (4), Total AUM Monitored (₹111.50 Cr+), Total Conversations, Requiring Attention.
- **Inspect Conversation:**
  - Click on Rahul Mehta's conversation session.
  - **Tab 1 (Transcript):** Shows exact message transcript, sender badges, and execution latencies.
  - **Tab 2 (Agent & Tool Traces):** Click **Inspect** on any trace to reveal exact input parameters JSON and raw output JSON.
  - **Tab 3 (Live Portfolio Snapshot):** Displays real-time database state of the client's properties.
- **Demonstrate Human Escalation / Attention Workflow:**
  - Go back to WhatsApp chat and type: *"I am frustrated with this, let me speak to a human advisor."*
  - Refresh the Business Console: the conversation immediately lights up with a pulsing **⚠️ ATTENTION** badge.
  - Click **Resolve Attention Flag**, enter resolution notes, and resolve the escalation.

---

### Part 4: Technical Decisions & Q&A Summary (1.5 Minutes)

Conclude by addressing the key architectural questions:
1. **Agent Framework:** Unified FastAPI orchestrator supporting both OpenRouter dynamic model routing (Gemini, LLaMA, GPT-4o-mini) and deterministic autonomous execution.
2. **Deterministic Integrity:** All financial computations (gross yield, exposure %, rate/sqft) run through `PortfolioEngine` in Python, eliminating LLM arithmetic errors.
3. **Hypothetical Sandboxing:** Scenario modeling runs via in-memory property cloning (`ScenarioEngine`), completely isolating what-if queries from production data.
4. **Latency Profile:** Sub-30ms in deterministic mode; 400-800ms in OpenRouter streaming mode.
