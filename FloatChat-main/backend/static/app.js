// app.js
// Frontend controller for the FloatChat dashboard interface

document.addEventListener("DOMContentLoaded", () => {
    // DOM Elements
    const floatList = document.getElementById("floatList");
    const floatSearch = document.getElementById("floatSearch");
    const filterBadges = document.querySelectorAll(".filter-badge");
    const chatMessages = document.getElementById("chatMessages");
    const chatForm = document.getElementById("chatForm");
    const userInput = document.getElementById("userInput");
    const typingIndicator = document.getElementById("typingIndicator");
    const clearChatBtn = document.getElementById("clearChatBtn");

    // Viewport & Tab Elements
    const mapTabBtn = document.getElementById("mapTabBtn");
    const plotTabBtn = document.getElementById("plotTabBtn");
    const mapViewport = document.getElementById("mapViewport");
    const plotViewport = document.getElementById("plotViewport");
    const mapIframe = document.getElementById("mapIframe");
    const plotImage = document.getElementById("plotImage");

    // Nav & Modal Elements
    const navItems = document.querySelectorAll(".nav-links li");
    const coordModal   = document.getElementById("coordModal");
    const statusModal  = document.getElementById("statusModal");

    let allFloats = [];
    let currentFilter = "all";

    // ==========================================================================
    // API Calls & Dashboard Population
    // ==========================================================================

    // Fetch and populate float cards from the backend
    async function loadFloats() {
        try {
            const response = await fetch("/api/floats");
            if (!response.ok) throw new Error("Failed to fetch float list.");
            allFloats = await response.json();
            renderFloatList();
        } catch (error) {
            console.error("Error loading floats:", error);
            if (floatList) {
                floatList.innerHTML = `<div class="empty-state"><i class="fa-solid fa-triangle-exclamation" style="color:var(--neon-coral);"></i><p>Failed to load explorer</p><span>Check backend console logs.</span></div>`;
            }
        }
    }

    function getGeographicRegion(lat, lon) {
        if (!lat || !lon) return "Indian Ocean";
        if (lat >= 0 && lat <= 25) {
            if (lon >= 50 && lon <= 77.5) {
                // Arabian Sea
                if (lat >= 16 && lat <= 21 && lon >= 68 && lon <= 74) {
                    return "Arabian Sea (Off Mumbai)";
                } else if (lat >= 11 && lat < 16 && lon >= 69 && lon <= 75) {
                    return "Arabian Sea (Off Goa Coast)";
                } else if (lat >= 8 && lat < 11 && lon >= 68 && lon <= 76) {
                    return "Arabian Sea (Off Kochi)";
                } else if (lat >= 15) {
                    return "Arabian Sea (North)";
                } else if (lat >= 8) {
                    return "Arabian Sea (Central)";
                } else {
                    return "Arabian Sea (South)";
                }
            } else if (lon > 77.5 && lon <= 100) {
                // Bay of Bengal
                if (lat >= 11 && lat <= 15 && lon >= 80 && lon <= 85) {
                    return "Bay of Bengal (Off Chennai)";
                } else if (lat >= 16) {
                    return "Bay of Bengal (North)";
                } else if (lat >= 8 && lat < 16) {
                    return "Bay of Bengal (Central)";
                } else {
                    return "Bay of Bengal (South)";
                }
            }
        }
        return "Indian Ocean (Equatorial)";
    }

    function renderFloatList() {
        if (!floatList) return;
        floatList.innerHTML = "";
        const searchVal = floatSearch.value.toLowerCase().trim();
        
        const filtered = allFloats.filter(f => {
            const regionName = getGeographicRegion(f.latest_lat, f.latest_lon).toLowerCase();
            // Text search matches both platform number and region name
            const matchesSearch = f.platform_number.toLowerCase().includes(searchVal) ||
                                  regionName.includes(searchVal);
            // Type toggle filter
            const matchesType = currentFilter === "all" || 
                                (currentFilter === "bgc" && f.float_type === "BGC") || 
                                (currentFilter === "core" && f.float_type === "CORE");
            return matchesSearch && matchesType;
        });

        if (filtered.length === 0) {
            floatList.innerHTML = `<div class="empty-state"><i class="fa-solid fa-circle-question"></i><p>No floats found</p><span>Try searching for another ID or region.</span></div>`;
            return;
        }

        filtered.forEach(f => {
            const card = document.createElement("div");
            card.className = "float-card";
            card.dataset.id = f.platform_number;
            
            const region = getGeographicRegion(f.latest_lat, f.latest_lon);
            
            card.innerHTML = `
                <div class="card-header">
                    <span class="float-id" style="font-size: 13px; font-weight: 700; color: var(--neon-cyan);">${region}</span>
                    <span class="type-badge ${f.float_type.toLowerCase()}">${f.float_type}</span>
                </div>
                <div class="card-body">
                    <div class="card-row">
                        <span>Float ID:</span>
                        <span style="font-weight: 600;">#${f.platform_number}</span>
                    </div>
                    <div class="card-row">
                        <span>Latest Cycle:</span>
                        <span>${f.cycles_count}</span>
                    </div>
                    <div class="card-row">
                        <span>Report Date:</span>
                        <span>${f.latest_date}</span>
                    </div>
                    <div class="card-row">
                        <span>Coordinates:</span>
                        <span>${f.latest_lat ? f.latest_lat.toFixed(2) : "N/A"}°N, ${f.latest_lon ? f.latest_lon.toFixed(2) : "N/A"}°E</span>
                    </div>
                </div>
            `;

// What happens when you click a Float Card on the left
            card.addEventListener("click", () => {
                // Highlight card
                document.querySelectorAll(".float-card").forEach(c => c.classList.remove("selected"));
                card.classList.add("selected");
                
                // Update Middle SaaS Details Panel
                document.getElementById("detailFloatId").textContent = f.platform_number;
                document.getElementById("detailRegion").innerHTML = `📍 ${region}`;
                document.getElementById("detailLat").textContent = f.latest_lat ? `${f.latest_lat.toFixed(2)}° N` : 'N/A';
                document.getElementById("detailLon").textContent = f.latest_lon ? `${f.latest_lon.toFixed(2)}° E` : 'N/A';
                document.getElementById("detailCycle").textContent = f.cycles_count;
                document.getElementById("detailDate").textContent = f.latest_date;
                document.getElementById("detailType").textContent = f.float_type;
                
                // Set color for type
                document.getElementById("detailType").style.color = f.float_type === "BGC" ? "var(--neon-green)" : "var(--accent-blue)";

                // Wire up the new panel buttons to trigger Python AI Visuals
                document.getElementById("btnMap").onclick = () => submitQuestion(`PLOT: trajectory, float=${f.platform_number}`);
                document.getElementById("btnPlot").onclick = () => submitQuestion(`PLOT: profile, float=${f.platform_number}, cycle=${f.cycles_count}, param=temperature`);
                
                // Trigger the map automatically
                submitQuestion(`PLOT: trajectory, float=${f.platform_number}`);
            });

            floatList.appendChild(card);
        });
    }

    // ==========================================================================
    // Event Listeners (Search & Filters)
    // ==========================================================================

    if (floatSearch) {
        floatSearch.addEventListener("input", renderFloatList);
    }

    filterBadges.forEach(badge => {
        badge.addEventListener("click", () => {
            filterBadges.forEach(b => b.classList.remove("active"));
            badge.classList.add("active");
            currentFilter = badge.textContent.toLowerCase();
            renderFloatList();
        });
    });

    // ==========================================================================
    // Media Viewports & Tab Toggles
    // ==========================================================================

    if (mapTabBtn) mapTabBtn.addEventListener("click", () => switchTab("map"));
    if (plotTabBtn) plotTabBtn.addEventListener("click", () => switchTab("plot"));

    function switchTab(tab) {
        if (tab === "map") {
            if (mapTabBtn) mapTabBtn.classList.add("active");
            if (plotTabBtn) plotTabBtn.classList.remove("active");
            if (mapViewport) mapViewport.classList.add("active");
            if (plotViewport) plotViewport.classList.remove("active");
        } else {
            if (plotTabBtn) plotTabBtn.classList.add("active");
            if (mapTabBtn) mapTabBtn.classList.remove("active");
            if (plotViewport) plotViewport.classList.add("active");
            if (mapViewport) mapViewport.classList.remove("active");
        }
    }

    function loadMap(mapUrl) {
        if (!mapViewport || !mapIframe) return;
        const emptyState = mapViewport.querySelector(".empty-state");
        if (emptyState) emptyState.style.display = "none";
        
        mapIframe.src = mapUrl;
        mapIframe.style.display = "block";
        mapIframe.style.width = "100%";
        mapIframe.style.height = "100%";
        mapIframe.style.border = "none";
        mapIframe.style.borderRadius = "14px";
        
        switchTab("map");
    }

    function loadPlot(plotUrl) {
        if (!plotViewport || !plotImage) return;
        const emptyState = plotViewport.querySelector(".empty-state");
        if (emptyState) emptyState.style.display = "none";
        
        plotImage.src = plotUrl;
        plotImage.style.display = "block";
        switchTab("plot");
    }

    // ==========================================================================
    // Chat Message Processing
    // ==========================================================================

    if (chatForm) {
        chatForm.addEventListener("submit", (e) => {
            e.preventDefault();
            const text = userInput.value.trim();
            if (!text) return;
            
            submitQuestion(text);
            userInput.value = "";
        });
    }

    document.addEventListener("click", (e) => {
        if (e.target && e.target.classList.contains("suggestion-chip")) {
            submitQuestion(e.target.textContent);
        }
    });

    if (clearChatBtn) {
        clearChatBtn.addEventListener("click", () => {
            if (chatMessages) {
                chatMessages.innerHTML = `
                    <div class="message bot-message fade-in-up">
                        <div class="message-content">
                            <p>Chat history cleared. How can I help you query Argo data?</p>
                        </div>
                    </div>
                `;
            }
        });
    }

    // ── Markdown Renderer ────────────────────────────────────────────────────
    function parseMarkdownTable(tableLines) {
        // tableLines is an array of raw '| col | col |' strings
        const rows = tableLines.map(line =>
            line.split("|").map(c => c.trim()).filter((_, i, a) => i > 0 && i < a.length - 1)
        );
        if (rows.length < 2) return null;

        const [headerRow, , ...bodyRows] = rows; // skip separator row (index 1)
        const actualBodyRows = tableLines.length >= 2 ? rows.slice(2) : [];

        let html = `<div class="data-table-wrapper"><table class="data-table"><thead><tr>`;
        headerRow.forEach(h => { html += `<th>${escapeHtml(h)}</th>`; });
        html += `</tr></thead><tbody>`;
        actualBodyRows.forEach(row => {
            html += `<tr>`;
            row.forEach(cell => { html += `<td>${escapeHtml(cell === "—" ? "—" : cell)}</td>`; });
            html += `</tr>`;
        });
        html += `</tbody></table></div>`;
        return html;
    }

    function escapeHtml(str) {
        return String(str)
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;");
    }

    function renderMarkdown(text) {
        // Process block by block: detect markdown table sections vs plain text
        const lines = text.split("\n");
        let html = "";
        let tableBuffer = [];
        let inTable = false;

        const flushTable = () => {
            if (tableBuffer.length >= 2) {
                const rendered = parseMarkdownTable(tableBuffer);
                if (rendered) html += rendered;
                else html += tableBuffer.map(l => `<p>${escapeHtml(l)}</p>`).join("");
            }
            tableBuffer = [];
            inTable = false;
        };

        lines.forEach(line => {
            const isTableRow = /^\s*\|/.test(line);
            if (isTableRow) {
                inTable = true;
                tableBuffer.push(line);
            } else {
                if (inTable) flushTable();
                if (line.trim() === "") {
                    html += "<br>";
                } else {
                    // Render **bold** and *italic*
                    let l = escapeHtml(line)
                        .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
                        .replace(/\*(.+?)\*/g, "<em>$1</em>");
                    html += `<p>${l}</p>`;
                }
            }
        });
        if (inTable) flushTable();
        return html;
    }

    function appendMessage(sender, text) {
        const msgDiv = document.createElement("div");
        msgDiv.className = `message ${sender}-message fade-in-up`;

        let contentHtml = "";


// Auto-inject Ocean Region names after float IDs in chat messages
formattedText = formattedText.replace(/float\s*(#?\d+)/gi, (match, floatId) => {
    // Find the float in our loaded data array
    const foundFloat = allFloats.find(f => f.platform_number.toString() === floatId.toString());
    if (foundFloat) {
        const region = getOceanRegion(foundFloat.latest_lat, foundFloat.latest_lon);
        return `float <strong>#${floatId}</strong> (<span style="color:var(--neon-cyan); font-weight:600;">📍 ${region}</span>)`;
    }
    return match;
});

        if (sender === "bot") {
            // Strip leftover markdown image/link artifacts
            let cleaned = text
                .replace(/!\[.*?\]\(.*?\)/g, "")
                .replace(/\*\(Click to open:.*?\)\*/g, "");

            contentHtml = renderMarkdown(cleaned);
        } else {
            contentHtml = `<p>${escapeHtml(text)}</p>`;
        }

        msgDiv.innerHTML = `<div class="message-content">${contentHtml}</div>`;
        chatMessages.appendChild(msgDiv);
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }


    async function submitQuestion(question) {
        // Append user's text bubble
        appendMessage("user", question);
        
        // Show compiling SQL/typing loading dots
        typingIndicator.style.display = "flex";
        chatMessages.scrollTop = chatMessages.scrollHeight;

async function submitQuestion(question) {
    if (isProcessing) return; // Ignore clicks if a request is already running!
    isProcessing = true;

    appendMessage("user", question);
    if (typingIndicator) typingIndicator.style.display = "flex";

    try {
        const response = await fetch("/api/chat", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ message: question })
        });

        if (!response.ok) throw new Error("Agent API Error.");
        const data = await response.json();

        if (typingIndicator) typingIndicator.style.display = "none";
        appendMessage("bot", data.response);

        if (data.map_url) loadMap(data.map_url);
        if (data.plot_url) loadPlot(data.plot_url);

    } catch (error) {
        if (typingIndicator) typingIndicator.style.display = "none";
        appendMessage("bot", "Please wait a moment before sending another query (Rate Limit Protection).");
    } finally {
        isProcessing = false; // Reset flag when done
    }
}

    // ==========================================================================
    // Sidebar Navigation View Switcher
    // ==========================================================================
    document.querySelectorAll(".sidebar-nav .nav-links li, .nav-links li").forEach(button => {
        button.addEventListener("click", (e) => {
            document.querySelectorAll(".nav-links li").forEach(el => el.classList.remove("active"));
            const clicked = e.currentTarget;
            clicked.classList.add("active");

            const view = clicked.getAttribute("data-view");

            const trackingPanel = document.querySelector(".float-explorer");
            const chatPanel = document.querySelector(".chat-container");
            const mapPanel = document.querySelector(".media-panel");

            if (view === "tracking" || view === "explorer") {
                if (trackingPanel) trackingPanel.style.display = "flex";
                if (chatPanel) chatPanel.style.display = "flex";
                if (mapPanel) mapPanel.style.display = "flex";
            } else if (view === "chat") {
                if (trackingPanel) trackingPanel.style.display = "none";
                if (chatPanel) chatPanel.style.display = "flex";
                if (mapPanel) mapPanel.style.display = "none";
            } else if (view === "map") {
                if (trackingPanel) trackingPanel.style.display = "none";
                if (chatPanel) chatPanel.style.display = "none";
                if (mapPanel) mapPanel.style.display = "flex";
            }
        });
    });

    // ==========================================================================
    // Nav Sidebar Button Handlers
    // ==========================================================================

    navItems.forEach(item => {
        item.addEventListener("click", () => {
            const nav = item.dataset.nav;

            // Active highlight (only for chat which stays active)
            if (nav === "chat") {
                navItems.forEach(n => n.classList.remove("active"));
                item.classList.add("active");
                userInput.focus();
                return;
            }

            if (nav === "coords") {
                coordModal.style.display = "flex";
                return;
            }

            if (nav === "docs") {
                window.open("https://argo.ucsd.edu/data/", "_blank");
                return;
            }

            if (nav === "export") {
                // Build CSV from allFloats and download it
                if (!allFloats.length) {
                    alert("No float data loaded to export.");
                    return;
                }
                const headers = ["platform_number","float_type","deployment_date","cycles_count","latest_date","latest_lat","latest_lon","status"];
                const rows = allFloats.map(f =>
                    headers.map(h => JSON.stringify(f[h] ?? "")).join(",")
                );
                const csv = [headers.join(","), ...rows].join("\n");
                const blob = new Blob([csv], { type: "text/csv" });
                const url  = URL.createObjectURL(blob);
                const a    = document.createElement("a");
                a.href     = url;
                a.download = "floatchat_floats_export.csv";
                a.click();
                URL.revokeObjectURL(url);
                return;
            }

            if (nav === "settings") {
                statusModal.style.display = "flex";
                return;
            }
        });
    });

    // Close modals
    document.getElementById("coordModalClose").addEventListener("click",  () => coordModal.style.display  = "none");
    document.getElementById("statusModalClose").addEventListener("click", () => statusModal.style.display = "none");
    // Click outside modal to close
    [coordModal, statusModal].forEach(m => {
        m.addEventListener("click", e => { if (e.target === m) m.style.display = "none"; });
    });

    // Coordinate Search → auto-submit to chat
    document.getElementById("coordSearchBtn").addEventListener("click", () => {
        const lat    = parseFloat(document.getElementById("coordLat").value);
        const lon    = parseFloat(document.getElementById("coordLon").value);
        const radius = parseFloat(document.getElementById("coordRadius").value) || 3;
        if (isNaN(lat) || isNaN(lon)) {
            alert("Please enter valid latitude and longitude values.");
            return;
        }
        coordModal.style.display = "none";
        const query = `Show me temperature and salinity measurements near latitude ${lat}°N, longitude ${lon}°E within ${radius} degrees`;
        submitQuestion(query);
    });

    // Initialize Page
    loadFloats();
});