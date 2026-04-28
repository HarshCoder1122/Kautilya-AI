class DashboardStudio {
    constructor() {
        this.pages = {
            overview: {
                title: "RevealIQ Command Deck",
                description:
                    "Operate the full RevealIQ stack from one cinematic studio: intelligence, voice, campaigns, lead scoring, and developer tooling.",
                kicker: "Live Studio",
            },
            keys: {
                title: "Access Layer",
                description:
                    "Provision and rotate API credentials without leaving the studio. The visual redesign keeps the key flow intact while making it easier to scan.",
                kicker: "Security Fabric",
            },
            playground: {
                title: "Realtime Playground",
                description:
                    "Test chat, text-to-speech, and transcription against your live stack inside a cleaner, higher-contrast workbench.",
                kicker: "Build Surface",
            },
            usage: {
                title: "Signal Analytics",
                description:
                    "Track token flow, model mix, and activity patterns through a dashboard tuned for quick operational reads.",
                kicker: "Live Telemetry",
            },
            agents: {
                title: "Omni Agent Studio",
                description:
                    "Design, launch, and evaluate voice agents inside an interface that feels closer to a premium product studio than a utility admin panel.",
                kicker: "Agent Foundry",
            },
            campaigns: {
                title: "Campaign Control",
                description:
                    "Run outbound campaigns, monitor throughput, and manage dialer workflows from a higher-signal control layer.",
                kicker: "Execution Grid",
            },
            leads: {
                title: "Lead Intelligence",
                description:
                    "Review hot leads, intent signals, and operational follow-through in a streamlined analyst view.",
                kicker: "Revenue Signals",
            },
            telephony: {
                title: "Voice Infrastructure",
                description:
                    "Configure Vobiz and sync providers through a studio layout that gives telephony its own premium control room.",
                kicker: "Call Fabric",
            },
            docs: {
                title: "Launch Docs",
                description:
                    "Ship faster with polished quick-start snippets and endpoint references that still stay close to the live product surface.",
                kicker: "Developer Start",
            },
            billing: {
                title: "Financial Control",
                description:
                    "Manage your subscription, top up credits, and review billing history in a centralized workspace.",
                kicker: "Capital Management",
            },
        };
        this.trackedStats = [
            {
                id: "statTokens",
                label: "Token Flow",
                detail: "Realtime language consumption across your active workspace.",
            },
            {
                id: "statTTS",
                label: "Voice Output",
                detail: "Generated speech volume for audio surfaces and agents.",
            },
            {
                id: "statSTT",
                label: "Speech Input",
                detail: "Captured listening time and conversational intake.",
            },
            {
                id: "statKeys",
                label: "Access Keys",
                detail: "Active credentials currently powering integrations.",
            },
        ];
        this.prefersReducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
        this.sceneCanvas = null;
        this.ctx = null;
        this.particles = [];
        this.rafId = 0;
        this.mouse = { x: 0, y: 0, active: false };
    }

    init() {
        document.body.classList.add("reveliq-studio");
        this.decoratePanels();
        this.buildOverviewShell();
        this.injectPageHeaders();
        this.attachTilt();
        this.syncActivePage();
        this.patchNavigation();
        this.buildScene();
    }

    decoratePanels() {
        document
            .querySelectorAll(".ds-card, .ds-stat-card, .ds-chart-card, .tele-provider-card, .omni-panel, .ag-agent-card, .ds-code-block")
            .forEach((element, index) => {
                element.classList.add("studio-tilt");
                if (index < 8) {
                    element.dataset.studioDepth = "high";
                }
            });
    }

    buildOverviewShell() {
        const overview = document.getElementById("page-overview");
        const welcome = overview == null ? void 0 : overview.querySelector(".ds-welcome");
        if (!overview || !welcome || overview.querySelector(".studio-overview-shell")) {
            return;
        }

        const shell = document.createElement("div");
        shell.className = "studio-overview-shell";

        const brief = document.createElement("aside");
        brief.className = "studio-brief studio-tilt";
        brief.innerHTML = `
            <div class="studio-page-kicker">Studio Pulse</div>
            <h3>Operate agents, campaigns, leads, and telephony from one control surface.</h3>
            <p>Everything important stays live here: API access, playground testing, voice operations, outbound workflows, and performance signals.</p>
            <div class="studio-module-rail">
                <span class="studio-chip">Agents</span>
                <span class="studio-chip">Campaigns</span>
                <span class="studio-chip">Lead Intel</span>
                <span class="studio-chip">Telephony</span>
                <span class="studio-chip">API Playground</span>
            </div>
        `;

        const signalGrid = document.createElement("div");
        signalGrid.className = "studio-signal-grid";

        for (const trackedStat of this.trackedStats) {
            const card = document.createElement("article");
            card.className = "studio-signal-card studio-tilt";
            card.innerHTML = `
                <div class="studio-signal-row">
                    <span class="studio-signal-label">${trackedStat.label}</span>
                    <strong class="studio-signal-value" data-stat-mirror="${trackedStat.id}">--</strong>
                </div>
                <div class="studio-signal-copy">${trackedStat.detail}</div>
            `;
            signalGrid.appendChild(card);
        }

        shell.appendChild(welcome);
        shell.appendChild(brief);
        overview.prepend(shell);
        brief.appendChild(signalGrid);
        this.mirrorStats();
    }

    mirrorStats() {
        for (const trackedStat of this.trackedStats) {
            const source = document.getElementById(trackedStat.id);
            const mirror = document.querySelector(`[data-stat-mirror="${trackedStat.id}"]`);
            if (!source || !mirror) {
                continue;
            }

            const sync = () => {
                const raw = (source.textContent || "").trim() || "--";
                mirror.textContent = raw === "â€”" ? "--" : raw;
            };

            sync();
            new MutationObserver(sync).observe(source, { childList: true, characterData: true, subtree: true });
        }
    }

    injectPageHeaders() {
        document.querySelectorAll(".ds-page").forEach((page) => {
            const pageId = page.id.replace("page-", "");
            const meta = this.pages[pageId];
            if (!meta || pageId === "overview" || page.querySelector(".studio-page-header")) {
                return;
            }

            const header = document.createElement("div");
            header.className = "studio-page-header";
            header.innerHTML = `
                <div class="studio-page-kicker">${meta.kicker}</div>
                <h2>${meta.title}</h2>
            `;
            page.prepend(header);
        });
    }

    attachTilt() {
        const targets = Array.from(document.querySelectorAll(".studio-tilt"));
        if (this.prefersReducedMotion) {
            return;
        }

        for (const target of targets) {
            target.addEventListener("pointermove", (event) => {
                const rect = target.getBoundingClientRect();
                const x = (event.clientX - rect.left) / rect.width;
                const y = (event.clientY - rect.top) / rect.height;
                const rotateY = (x - 0.5) * 10;
                const rotateX = (0.5 - y) * 10;
                target.style.transform = `perspective(1200px) rotateX(${rotateX.toFixed(2)}deg) rotateY(${rotateY.toFixed(2)}deg) translateY(-2px)`;
            });

            target.addEventListener("pointerleave", () => {
                target.style.transform = "";
            });
        }
    }

    syncActivePage() {
        const active = (document.querySelector(".ds-page.active") == null ? void 0 : document.querySelector(".ds-page.active").id.replace("page-", "")) || "overview";
        document.body.dataset.activePage = active;
    }

    patchNavigation() {
        const existingSwitch = window.switchPage;
        if (typeof existingSwitch !== "function") {
            return;
        }

        window.switchPage = (page, btn) => {
            existingSwitch(page, btn);
            document.body.dataset.activePage = page;
        };
    }

    buildScene() {
        this.sceneCanvas = document.getElementById("studioCanvas");
        if (!this.sceneCanvas) {
            return;
        }

        this.ctx = this.sceneCanvas.getContext("2d");
        if (!this.ctx) {
            return;
        }

        this.resizeScene();
        this.seedParticles();

        window.addEventListener("resize", () => {
            this.resizeScene();
            this.seedParticles();
        });

        window.addEventListener("pointermove", (event) => {
            this.mouse.x = event.clientX;
            this.mouse.y = event.clientY;
            this.mouse.active = true;
        });

        window.addEventListener("pointerleave", () => {
            this.mouse.active = false;
        });

        if (!this.prefersReducedMotion) {
            this.animateScene();
        } else {
            this.drawScene();
        }
    }

    resizeScene() {
        if (!this.sceneCanvas) {
            return;
        }

        const ratio = window.devicePixelRatio || 1;
        this.sceneCanvas.width = Math.floor(window.innerWidth * ratio);
        this.sceneCanvas.height = Math.floor(window.innerHeight * ratio);
        this.sceneCanvas.style.width = `${window.innerWidth}px`;
        this.sceneCanvas.style.height = `${window.innerHeight}px`;
        this.ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
    }

    seedParticles() {
        const count = Math.max(42, Math.round(window.innerWidth / 28));
        this.particles = Array.from({ length: count }, () => ({
            x: Math.random() * window.innerWidth,
            y: Math.random() * window.innerHeight,
            z: 0.25 + Math.random() * 1.3,
            vx: (Math.random() - 0.5) * 0.28,
            vy: (Math.random() - 0.5) * 0.28,
        }));
    }

    updateHeader(page) {
        const info = this.pages[page] || this.pages.overview;
        const header = document.getElementById("dsPageHeader");
        if (!header) return;

        header.innerHTML = `
            <div class="ds-kicker">${info.kicker}</div>
            <h1 class="ds-title">${info.title}</h1>
            <p class="ds-description">${info.description}</p>
        `;

        // Update active nav item
        document.querySelectorAll(".ds-nav-item").forEach((n) => {
            n.classList.toggle("active", n.dataset.page === page);
        });
    }

    async refreshBillingStats() {
        const tierEl = document.getElementById("billingCurrentTier");
        const balanceEl = document.getElementById("billingCurrentBalance");
        if (tierEl) tierEl.textContent = "Loading...";
        if (balanceEl) balanceEl.textContent = "Loading...";

        try {
            const token = typeof window.getToken === 'function' ? await window.getToken() : null;
            const headers = token ? { Authorization: `Bearer ${token}` } : {};
            
            const res = await fetch("/api/billing/config", { headers });
            const data = await res.json();
            if (data) {
                if (tierEl) tierEl.textContent = data.is_pro ? "PRO TIER" : "FREE TIER";
                if (balanceEl) balanceEl.textContent = `₹${(data.credits || 0).toFixed(2)}`;

                // Update upgrade button
                const proBtn = document.getElementById("proUpgradeBtn");
                if (proBtn) {
                    if (data.is_pro) {
                        proBtn.textContent = "Current Plan";
                        proBtn.disabled = true;
                        proBtn.classList.add("ds-btn-ghost");
                        proBtn.classList.remove("ds-btn-primary");
                    } else {
                        proBtn.textContent = "Upgrade to Pro";
                        proBtn.disabled = false;
                        proBtn.classList.add("ds-btn-primary");
                        proBtn.classList.remove("ds-btn-ghost");
                    }
                }
                
                this.loadTransactions();
            }
        } catch (e) {
            console.error("Failed to refresh billing stats", e);
        }
    }

    async loadTransactions() {
        const tbody = document.getElementById("transactions-tbody");
        if (!tbody) return;

        try {
            const token = typeof window.getToken === 'function' ? await window.getToken() : null;
            if (!token) return;

            const res = await fetch("/api/billing/transactions", {
                headers: { Authorization: `Bearer ${token}` },
            });
            const data = await res.json();
            const txs = data.transactions || [];

            if (txs.length === 0) {
                tbody.innerHTML = `
                    <tr>
                        <td colspan="5" style="text-align: center; padding: 40px; color: var(--text-muted);">
                            <span class="material-icons-round" style="font-size: 48px; opacity: 0.3; display: block; margin-bottom: 10px;">receipt_long</span>
                            No transactions found.
                        </td>
                    </tr>
                `;
                return;
            }

            tbody.innerHTML = txs
                .map(
                    (tx) => `
                <tr>
                    <td>
                        <div style="font-size: 0.85rem; font-weight: 500;">${tx.date}</div>
                        <div style="font-size: 0.7rem; color: var(--text-muted);">${new Date(
                            tx.timestamp * 1000
                        ).toLocaleTimeString()}</div>
                    </td>
                    <td>
                        <span class="ds-tag" style="background: ${
                            tx.plan_type === "pro" ? "rgba(77, 112, 232, 0.1)" : "rgba(155, 114, 203, 0.1)"
                        }; color: ${tx.plan_type === "pro" ? "var(--accent)" : "var(--purple)"};">
                            ${tx.plan_type === "pro" ? "PRO UPGRADE" : "CREDIT RECHARGE"}
                        </span>
                    </td>
                    <td style="font-weight: 600; color: var(--text-primary);">₹${tx.amount}</td>
                    <td style="font-family: monospace; font-size: 0.75rem; color: var(--text-muted);">${tx.order_id}</td>
                    <td>
                        <span style="display: inline-flex; align-items: center; gap: 4px; color: var(--success); font-size: 0.8rem; font-weight: 500;">
                            <span class="material-icons-round" style="font-size: 14px;">check_circle</span> Success
                        </span>
                    </td>
                </tr>
            `
                )
                .join("");
        } catch (e) {
            console.error("Failed to load transactions", e);
        }
    }

    async initiatePayment(plan, amount) {
        const btn = event.target;
        const originalContent = btn.innerHTML;
        btn.disabled = true;
        btn.innerHTML = `<span class="material-icons-round spin" style="font-size: 16px;">sync</span> Processing...`;

        try {
            const token = await window.getToken();
            // 1. Create Order
            const orderResp = await fetch("/api/billing/create-order", {
                method: "POST",
                headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
                body: JSON.stringify({ amount: amount, plan_type: plan }),
            });
            const order = await orderResp.json();

            if (order.error) throw new Error(order.error);

            // 2. Fetch Razorpay Config
            const configResp = await fetch("/api/billing/config");
            const config = await configResp.json();

            const options = {
                key: config.razorpay_key_id,
                amount: order.amount,
                currency: order.currency,
                name: "Kautilya AI",
                description: plan === "pro" ? "Upgrade to Pro Tier" : "Add Credits",
                order_id: order.id,
                handler: async (response) => {
                    const verifyResp = await fetch("/api/billing/verify-payment", {
                        method: "POST",
                        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
                        body: JSON.stringify({
                            razorpay_order_id: response.razorpay_order_id,
                            razorpay_payment_id: response.razorpay_payment_id,
                            razorpay_signature: response.razorpay_signature,
                            plan_type: plan,
                            amount: amount,
                        }),
                    });
                    const result = await verifyResp.json();
                    if (result.success) {
                        alert(result.message);
                        this.refreshBillingStats();
                    } else {
                        alert("Payment verification failed: " + result.error);
                    }
                    btn.disabled = false;
                    btn.innerHTML = originalContent;
                },
                prefill: {
                    name: "", // Will be filled by user in checkout
                    email: "",
                },
                theme: { color: "#4D70E8" },
            };

            const rzp = new Razorpay(options);
            rzp.open();
        } catch (e) {
            alert("Error: " + e.message);
            btn.disabled = false;
            btn.innerHTML = originalContent;
        }
    }

    animateScene() {
        this.drawScene();
        this.rafId = window.requestAnimationFrame(() => this.animateScene());
    }

    drawScene() {
        if (!this.ctx) {
            return;
        }

        const ctx = this.ctx;
        ctx.clearRect(0, 0, window.innerWidth, window.innerHeight);

        for (const particle of this.particles) {
            const pullX = this.mouse.active ? (this.mouse.x - particle.x) * 0.00008 * particle.z : 0;
            const pullY = this.mouse.active ? (this.mouse.y - particle.y) * 0.00008 * particle.z : 0;
            particle.x += particle.vx + pullX;
            particle.y += particle.vy + pullY;

            if (particle.x < -20) particle.x = window.innerWidth + 20;
            if (particle.x > window.innerWidth + 20) particle.x = -20;
            if (particle.y < -20) particle.y = window.innerHeight + 20;
            if (particle.y > window.innerHeight + 20) particle.y = -20;
        }

        for (let i = 0; i < this.particles.length; i += 1) {
            const particle = this.particles[i];
            const radius = 1.1 + particle.z * 1.6;
            ctx.beginPath();
            ctx.fillStyle = `rgba(151, 180, 255, ${0.22 + particle.z * 0.26})`;
            ctx.arc(particle.x, particle.y, radius, 0, Math.PI * 2);
            ctx.fill();

            for (let j = i + 1; j < this.particles.length; j += 1) {
                const other = this.particles[j];
                const dx = particle.x - other.x;
                const dy = particle.y - other.y;
                const distance = Math.sqrt(dx * dx + dy * dy);

                if (distance < 140) {
                    ctx.beginPath();
                    ctx.strokeStyle = `rgba(77, 112, 232, ${(1 - distance / 140) * 0.22})`;
                    ctx.lineWidth = 1;
                    ctx.moveTo(particle.x, particle.y);
                    ctx.lineTo(other.x, other.y);
                    ctx.stroke();
                }
            }
        }
    }
}

// Global functions for Issue handling
window.raiseIssue = () => {
    const modal = document.getElementById("issueModal");
    if (modal) modal.style.display = "flex";
};
window.closeIssueModal = () => {
    const modal = document.getElementById("issueModal");
    if (modal) modal.style.display = "none";
};
window.submitIssue = async () => {
    const type = document.getElementById("issueType").value;
    const txId = document.getElementById("issueTxId").value;
    const desc = document.getElementById("issueDesc").value;

    if (!desc) {
        alert("Please describe your issue");
        return;
    }

    alert("Issue reported successfully. Our team will contact you soon.");
    window.closeIssueModal();
    document.getElementById("issueTxId").value = "";
    document.getElementById("issueDesc").value = "";
};

document.addEventListener("DOMContentLoaded", () => {
    window.studio = new DashboardStudio();
    window.studio.init();
    window.initiatePayment = (plan, amt) => window.studio.initiatePayment(plan, amt);
});
