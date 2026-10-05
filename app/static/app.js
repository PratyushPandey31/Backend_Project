// State
let activeUserId = "U001";
let activeUserName = "Rahul Mehta";
let currentConversationId = null;
let usersData = [];

// DOM Elements
const userListContainer = document.getElementById("userListContainer");
const activeClientName = document.getElementById("activeClientName");
const chatTitle = document.getElementById("chatTitle");
const messagesContainer = document.getElementById("messagesContainer");
const userInput = document.getElementById("userInput");
const btnSend = document.getElementById("btnSend");
const btnClearChat = document.getElementById("btnClearChat");
const promptChips = document.getElementById("promptChips");
const btnMobileBack = document.getElementById("btnMobileBack");
const btnMobileCloseSidebar = document.getElementById("btnMobileCloseSidebar");
const waWindow = document.querySelector(".wa-window");

// Settings Modal Elements
const btnSettings = document.getElementById("btnSettings");
const settingsModal = document.getElementById("settingsModal");
const btnCloseModal = document.getElementById("btnCloseModal");
const btnSaveSettings = document.getElementById("btnSaveSettings");
const cfgApiKey = document.getElementById("cfgApiKey");
const cfgModel = document.getElementById("cfgModel");

// Initialization
document.addEventListener("DOMContentLoaded", () => {
    loadSettings();
    fetchUsers();
    setupEventListeners();
});

function loadSettings() {
    const savedKey = localStorage.getItem("openrouter_api_key");
    const savedModel = localStorage.getItem("selected_model");
    if (savedKey) cfgApiKey.value = savedKey;
    if (savedModel) cfgModel.value = savedModel;
}

function setupEventListeners() {
    btnSend.addEventListener("click", sendMessage);
    userInput.addEventListener("keydown", (e) => {
        if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    });

    btnClearChat.addEventListener("click", () => {
        currentConversationId = null;
        messagesContainer.innerHTML = `
            <div class="wa-encryption-badge">
                <i class="fa-solid fa-lock"></i> Chat reset. New session started for ${activeUserName}.
            </div>
        `;
        sendInitialGreeting();
    });

    // Quick prompt chips
    promptChips.addEventListener("click", (e) => {
        if (e.target.classList.contains("chip")) {
            const prompt = e.target.getAttribute("data-prompt");
            userInput.value = prompt;
            sendMessage();
        }
    });

    // Modal
    btnSettings.addEventListener("click", () => settingsModal.classList.remove("hidden"));
    btnCloseModal.addEventListener("click", () => settingsModal.classList.add("hidden"));
    btnSaveSettings.addEventListener("click", () => {
        localStorage.setItem("openrouter_api_key", cfgApiKey.value.trim());
        localStorage.setItem("selected_model", cfgModel.value);
        settingsModal.classList.add("hidden");
        alert("Settings saved successfully!");
    });

    // Mobile Navigation Controls
    if (btnMobileBack && waWindow) {
        btnMobileBack.addEventListener("click", () => {
            waWindow.classList.add("mobile-show-sidebar");
        });
    }
    if (btnMobileCloseSidebar && waWindow) {
        btnMobileCloseSidebar.addEventListener("click", () => {
            waWindow.classList.remove("mobile-show-sidebar");
        });
    }
}

async function fetchUsers() {
    try {
        const res = await fetch("/api/users");
        usersData = await res.json();
        renderUserList();
        selectUser(usersData[0]);
    } catch (err) {
        console.error("Failed to fetch users:", err);
    }
}

function renderUserList() {
    userListContainer.innerHTML = "";
    usersData.forEach((u) => {
        const div = document.createElement("div");
        div.className = `chat-item ${u.user_id === activeUserId ? "active" : ""}`;
        div.dataset.userId = u.user_id;

        const initials = u.name.split(" ").map(n => n[0]).join("");
        div.innerHTML = `
            <div class="chat-item-avatar">${initials}</div>
            <div class="chat-item-body">
                <div class="chat-item-row-top">
                    <span class="chat-item-name">${u.name}</span>
                    <span class="chat-item-val">${u.total_value_formatted}</span>
                </div>
                <div class="chat-item-preview">${u.total_properties} properties • ${u.preferences || u.city}</div>
            </div>
        `;

        div.addEventListener("click", () => selectUser(u));
        userListContainer.appendChild(div);
    });
}

function selectUser(user) {
    activeUserId = user.user_id;
    activeUserName = user.name;
    currentConversationId = null;

    activeClientName.textContent = `${user.name} (${user.user_id})`;
    chatTitle.textContent = `${user.name} Portfolio`;

    document.querySelectorAll(".chat-item").forEach(item => {
        item.classList.toggle("active", item.dataset.userId === user.user_id);
    });

    messagesContainer.innerHTML = `
        <div class="wa-encryption-badge">
            <i class="fa-solid fa-lock"></i> Chat connected to ${user.name}'s real estate portfolio (${user.total_properties} properties in ${user.city}).
        </div>
    `;

    sendInitialGreeting();
    
    // On mobile screens, automatically show the chat window
    if (waWindow) {
        waWindow.classList.remove("mobile-show-sidebar");
    }
}

function sendInitialGreeting() {
    appendMessage(
        "assistant",
        `Hello **${activeUserName}**! 👋\n\nI am your **AI Real Estate Portfolio Analyst**. ` +
        `I am monitoring your active properties in ${usersData.find(u => u.user_id === activeUserId)?.city || 'India'}.\n\n` +
        `Feel free to ask for your portfolio summary, retail vs commercial exposure, rental yields, ` +
        `simulate what-if scenarios (e.g. *What if I exclude a property?*), or update valuations.`,
        null,
        15
    );
}

async function sendMessage() {
    const text = userInput.value.trim();
    if (!text) return;

    userInput.value = "";
    appendMessage("user", text);

    // Show Typing Indicator
    const typingIndicatorId = showTypingIndicator();

    const apiKey = localStorage.getItem("openrouter_api_key") || null;
    const model = localStorage.getItem("selected_model") || null;

    try {
        const payload = {
            user_id: activeUserId,
            message: text,
            conversation_id: currentConversationId,
            api_key_override: apiKey,
            model_override: model
        };

        const res = await fetch("/api/chat", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload)
        });

        removeTypingIndicator(typingIndicatorId);

        if (!res.ok) {
            appendMessage("assistant", "⚠️ Error: Unable to process request at this moment.", null, 0);
            return;
        }

        const data = await res.json();
        currentConversationId = data.conversation_id;

        const toolName = data.tool_traces && data.tool_traces.length > 0 ? data.tool_traces[0].tool_name : null;
        appendMessage("assistant", data.reply, toolName, data.latency_ms);

    } catch (err) {
        removeTypingIndicator(typingIndicatorId);
        appendMessage("assistant", `⚠️ Network error: ${err.message}`, null, 0);
    }
}

function showTypingIndicator() {
    const id = "typing_" + Date.now();
    const div = document.createElement("div");
    div.id = id;
    div.className = "message-bubble assistant typing-bubble";
    div.innerHTML = `<em><i class="fa-solid fa-spinner fa-spin"></i> Analyzing portfolio metrics...</em>`;
    messagesContainer.appendChild(div);
    messagesContainer.scrollTop = messagesContainer.scrollHeight;
    return id;
}

function removeTypingIndicator(id) {
    const el = document.getElementById(id);
    if (el) el.remove();
}

function appendMessage(sender, content, toolName = null, latencyMs = null) {
    const bubble = document.createElement("div");
    bubble.className = `message-bubble ${sender}`;

    const now = new Date();
    const timeStr = now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

    let bodyHtml = renderMarkdown(content);

    let metaHtml = `<div class="bubble-meta">`;
    if (toolName) {
        metaHtml += `<span class="tool-badge-pill"><i class="fa-solid fa-bolt"></i> ${toolName}</span>`;
    }
    if (latencyMs) {
        metaHtml += `<span class="latency-pill">${latencyMs}ms</span>`;
    }
    metaHtml += `<span>${timeStr}</span>`;
    if (sender === "user") {
        metaHtml += `<i class="fa-solid fa-check-double blue-ticks"></i>`;
    }
    metaHtml += `</div>`;

    bubble.innerHTML = bodyHtml + metaHtml;
    messagesContainer.appendChild(bubble);
    messagesContainer.scrollTop = messagesContainer.scrollHeight;
}

function renderMarkdown(text) {
    if (!text) return "";
    let html = text
        .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;") // sanitize
        .replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>") // bold
        .replace(/\*(.*?)\*/g, "<em>$1</em>") // italics
        .replace(/`([^`]+)`/g, "<code>$1</code>"); // inline code

    // Handle Markdown tables
    if (html.includes("|")) {
        const lines = html.split("\n");
        let inTable = false;
        let tableHtml = "<table>";
        let newLines = [];

        for (let line of lines) {
            if (line.trim().startsWith("|") && line.trim().endsWith("|")) {
                if (line.includes("---")) continue; // separator
                if (!inTable) {
                    inTable = true;
                    tableHtml = "<table><thead><tr>";
                    const cells = line.split("|").slice(1, -1);
                    cells.forEach(c => tableHtml += `<th>${c.trim()}</th>`);
                    tableHtml += "</tr></thead><tbody>";
                } else {
                    tableHtml += "<tr>";
                    const cells = line.split("|").slice(1, -1);
                    cells.forEach(c => tableHtml += `<td>${c.trim()}</td>`);
                    tableHtml += "</tr>";
                }
            } else {
                if (inTable) {
                    inTable = false;
                    tableHtml += "</tbody></table>";
                    newLines.push(tableHtml);
                }
                newLines.push(line);
            }
        }
        if (inTable) {
            tableHtml += "</tbody></table>";
            newLines.push(tableHtml);
        }
        html = newLines.join("\n");
    }

    // Convert newlines to paragraphs/breaks
    const paras = html.split("\n\n").map(p => {
        if (p.startsWith("<table>")) return p;
        return `<p>${p.replace(/\n/g, "<br>")}</p>`;
    }).join("");

    return paras;
}
