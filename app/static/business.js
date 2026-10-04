// Business Console State
let allConversations = [];
let currentFilter = "all";
let selectedConversationId = null;

document.addEventListener("DOMContentLoaded", () => {
    fetchStats();
    fetchConversations();
    setupEventListeners();
    // Poll stats every 10 seconds for real-time dashboard updates
    setInterval(fetchStats, 10000);
});

function setupEventListeners() {
    // Filter Pills
    document.querySelectorAll(".filter-pill").forEach(pill => {
        pill.addEventListener("click", () => {
            document.querySelectorAll(".filter-pill").forEach(p => p.classList.remove("active"));
            pill.classList.add("active");
            currentFilter = pill.dataset.filter;
            renderConversationsList();
        });
    });

    // Tabs
    document.querySelectorAll(".biz-tab").forEach(tab => {
        tab.addEventListener("click", () => {
            document.querySelectorAll(".biz-tab").forEach(t => t.classList.remove("active"));
            document.querySelectorAll(".biz-tab-content").forEach(c => c.classList.remove("active"));
            tab.classList.add("active");
            document.getElementById(tab.dataset.tab).classList.add("active");
        });
    });

    // Reset DB
    document.getElementById("btnResetDB").addEventListener("click", async () => {
        if (!confirm("Are you sure you want to reset the portfolio database to initial CSV seed data?")) return;
        try {
            const res = await fetch("/api/reset-database", { method: "POST" });
            const data = await res.json();
            alert(data.message);
            fetchStats();
            fetchConversations();
        } catch (err) {
            alert("Failed to reset database: " + err.message);
        }
    });

    // Resolve Flag
    document.getElementById("btnResolveFlag").addEventListener("click", async () => {
        if (!selectedConversationId) return;
        const notes = prompt("Enter resolution notes:", "Reviewed and addressed by senior wealth analyst.");
        if (notes === null) return;

        try {
            const res = await fetch(`/api/conversations/${selectedConversationId}/resolve-flag`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ notes: notes })
            });
            const data = await res.json();
            alert(data.message);
            fetchStats();
            fetchConversations();
            selectConversation(selectedConversationId);
        } catch (err) {
            alert("Error resolving flag: " + err.message);
        }
    });
}

async function fetchStats() {
    try {
        const res = await fetch("/api/business/stats");
        const data = await res.json();
        document.getElementById("kpiUsers").textContent = data.total_users;
        document.getElementById("kpiAUM").textContent = data.total_aum_formatted;
        document.getElementById("kpiConvs").textContent = data.total_conversations;
        document.getElementById("kpiFlagged").textContent = data.flagged_conversations;
        document.getElementById("kpiTools").textContent = data.total_tool_executions;
    } catch (err) {
        console.error("Failed to load business stats:", err);
    }
}

async function fetchConversations() {
    try {
        const res = await fetch("/api/conversations");
        allConversations = await res.json();
        renderConversationsList();
        if (allConversations.length > 0 && !selectedConversationId) {
            selectConversation(allConversations[0].id);
        }
    } catch (err) {
        console.error("Failed to load conversations:", err);
    }
}

function renderConversationsList() {
    const container = document.getElementById("bizConvList");
    container.innerHTML = "";

    const filtered = allConversations.filter(c => {
        if (currentFilter === "flagged") return c.is_flagged;
        return true;
    });

    if (filtered.length === 0) {
        container.innerHTML = `<p class="placeholder-text">No conversations match the current filter.</p>`;
        return;
    }

    filtered.forEach(c => {
        const card = document.createElement("div");
        card.className = `biz-conv-card ${c.id === selectedConversationId ? "active" : ""} ${c.is_flagged ? "flagged" : ""}`;
        card.dataset.id = c.id;

        const timeStr = c.updated_at ? new Date(c.updated_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : "";

        card.innerHTML = `
            <div class="conv-top-row">
                <span class="conv-client-name">${c.user_name} (${c.user_id})</span>
                ${c.is_flagged ? `<span class="attention-badge">⚠️ ATTENTION</span>` : `<span class="conv-time">${timeStr}</span>`}
            </div>
            <div class="conv-preview">${c.last_message || 'New session'}</div>
            <div class="conv-time">${c.message_count} messages • ${c.title}</div>
        `;

        card.addEventListener("click", () => selectConversation(c.id));
        container.appendChild(card);
    });
}

async function selectConversation(convId) {
    selectedConversationId = convId;

    document.querySelectorAll(".biz-conv-card").forEach(c => {
        c.classList.toggle("active", c.dataset.id === convId);
    });

    try {
        const res = await fetch(`/api/conversations/${convId}`);
        const data = await res.json();

        // Update Header
        document.getElementById("currentConvTitle").textContent = data.session.title;
        document.getElementById("currentConvUser").textContent = `Client: ${data.session.user_name} (${data.session.user_id})`;

        // Attention Banner & Resolve Button
        const flagBanner = document.getElementById("flagNoticeBanner");
        const resolveBtn = document.getElementById("btnResolveFlag");
        const actionsDiv = document.getElementById("detailActions");

        actionsDiv.style.display = "block";
        if (data.session.is_flagged) {
            flagBanner.style.display = "flex";
            document.getElementById("flagNoticeText").textContent = data.session.flag_reason || "Escalated for human wealth advisor review.";
            resolveBtn.style.display = "inline-flex";
        } else {
            flagBanner.style.display = "none";
            resolveBtn.style.display = "none";
        }

        // Render Tab 1: Messages
        renderTranscript(data.messages);

        // Render Tab 2: Traces
        renderTraces(data.tool_traces);

        // Render Tab 3: Live Portfolio Snapshot
        fetchAndRenderPortfolio(data.session.user_id);

    } catch (err) {
        console.error("Failed to load conversation details:", err);
    }
}

function renderTranscript(messages) {
    const container = document.getElementById("transcriptMessages");
    if (!messages || messages.length === 0) {
        container.innerHTML = `<p class="placeholder-text">No messages recorded yet in this conversation.</p>`;
        return;
    }

    container.innerHTML = "";
    messages.forEach(m => {
        const div = document.createElement("div");
        div.className = `transcript-bubble ${m.sender}`;
        const timeStr = new Date(m.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });

        div.innerHTML = `
            <strong>${m.sender === "user" ? "Client" : "EstateIntel AI"}</strong>
            <div style="margin-top: 4px; white-space: pre-wrap;">${m.content}</div>
            <div class="transcript-bubble-meta">
                <span>🕒 ${timeStr}</span>
                ${m.latency_ms ? `<span>⚡ Latency: ${m.latency_ms}ms</span>` : ""}
            </div>
        `;
        container.appendChild(div);
    });
}

function renderTraces(traces) {
    const tbody = document.getElementById("tracesTableBody");
    const badge = document.getElementById("traceCountBadge");
    badge.textContent = traces ? traces.length : 0;

    if (!traces || traces.length === 0) {
        tbody.innerHTML = `<tr><td colspan="5" class="placeholder-text">No agent tool activity recorded yet in this session.</td></tr>`;
        document.getElementById("traceDetailViewer").style.display = "none";
        return;
    }

    tbody.innerHTML = "";
    traces.forEach(t => {
        const tr = document.createElement("tr");
        const timeStr = new Date(t.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });

        tr.innerHTML = `
            <td>${timeStr}</td>
            <td><strong style="color: #38bdf8;"><i class="fa-solid fa-bolt"></i> ${t.tool_name}</strong></td>
            <td><span class="latency-pill">${t.execution_time_ms} ms</span></td>
            <td><span style="color: ${t.success ? '#10b981' : '#ef4444'}; font-weight: 600;">${t.success ? 'Success' : 'Error'}</span></td>
            <td><button class="action-btn btn-success inspect-btn" style="padding: 4px 8px; font-size: 0.75rem;">Inspect</button></td>
        `;

        tr.querySelector(".inspect-btn").addEventListener("click", () => {
            const viewer = document.getElementById("traceDetailViewer");
            viewer.style.display = "block";
            document.getElementById("traceToolTitle").textContent = t.tool_name;
            try {
                document.getElementById("traceInputJson").textContent = JSON.stringify(JSON.parse(t.input), null, 2);
            } catch {
                document.getElementById("traceInputJson").textContent = t.input;
            }
            try {
                document.getElementById("traceOutputJson").textContent = JSON.stringify(JSON.parse(t.output), null, 2);
            } catch {
                document.getElementById("traceOutputJson").textContent = t.output;
            }
        });

        tbody.appendChild(tr);
    });
}

async function fetchAndRenderPortfolio(userId) {
    const container = document.getElementById("clientPortfolioView");
    try {
        const res = await fetch(`/api/users/${userId}/portfolio`);
        const p = await res.json();

        let propsRows = p.properties.map(item => `
            <tr>
                <td><code>${item.property_id}</code></td>
                <td><strong>${item.location}</strong></td>
                <td>${item.property_type} (${item.sub_type || '-'})</td>
                <td>${item.area_sqft.toLocaleString()} sq ft</td>
                <td><strong>${item.current_estimated_value_formatted}</strong></td>
                <td>${item.annual_rent_formatted}</td>
                <td><span style="color: #10b981; font-weight: 600;">${item.rental_yield_pct}%</span></td>
                <td>${item.occupancy_status}</td>
            </tr>
        `).join("");

        container.innerHTML = `
            <div style="margin-bottom: 16px; display: flex; gap: 20px;">
                <div>Total Valuation: <strong style="color: #38bdf8;">${p.total_portfolio_value_formatted}</strong></div>
                <div>Annual Rental Income: <strong style="color: #10b981;">${p.total_annual_rent_formatted}</strong></div>
                <div>Overall Gross Yield: <strong>${p.overall_rental_yield_pct}%</strong></div>
                <div>Occupancy Rate: <strong>${p.occupancy_rate_pct}%</strong></div>
            </div>
            <div class="traces-table-wrap">
                <table class="traces-table">
                    <thead>
                        <tr>
                            <th>ID</th>
                            <th>Location</th>
                            <th>Asset Type</th>
                            <th>Area</th>
                            <th>Valuation</th>
                            <th>Annual Rent</th>
                            <th>Yield</th>
                            <th>Occupancy</th>
                        </tr>
                    </thead>
                    <tbody>${propsRows}</tbody>
                </table>
            </div>
        `;
    } catch (err) {
        container.innerHTML = `<p class="placeholder-text">Error loading client portfolio: ${err.message}</p>`;
    }
}
