export {};

type PageId =
    | "overview"
    | "keys"
    | "playground"
    | "usage"
    | "agents"
    | "campaigns"
    | "leads"
    | "telephony"
    | "docs";

type PageMeta = {
    title: string;
    description: string;
    kicker: string;
};

type TrackedStat = {
    id: string;
    label: string;
    detail: string;
};

declare global {
    interface Window {
        switchPage?: (page: string, btn?: HTMLElement | null) => void;
    }
}

class DashboardStudio {
    private readonly pages: Record<string, PageMeta> = {
        overview: {
            title: "RevealIQ Command Deck",
            description: "Operate the full RevealIQ stack from one cinematic studio: intelligence, voice, campaigns, lead scoring, and developer tooling.",
            kicker: "Live Studio",
        },
        keys: {
            title: "Access Layer",
            description: "Provision and rotate API credentials without leaving the studio. The visual redesign keeps the key flow intact while making it easier to scan.",
            kicker: "Security Fabric",
        },
        playground: {
            title: "Realtime Playground",
            description: "Test chat, text-to-speech, and transcription against your live stack inside a cleaner, higher-contrast workbench.",
            kicker: "Build Surface",
        },
        usage: {
            title: "Signal Analytics",
            description: "Track token flow, model mix, and activity patterns through a dashboard tuned for quick operational reads.",
            kicker: "Live Telemetry",
        },
        agents: {
            title: "Omni Agent Studio",
            description: "Design, launch, and evaluate voice agents inside an interface that feels closer to a premium product studio than a utility admin panel.",
            kicker: "Agent Foundry",
        },
        campaigns: {
            title: "Campaign Control",
            description: "Run outbound campaigns, monitor throughput, and manage dialer workflows from a higher-signal control layer.",
            kicker: "Execution Grid",
        },
        leads: {
            title: "Lead Intelligence",
            description: "Review hot leads, intent signals, and operational follow-through in a streamlined analyst view.",
            kicker: "Revenue Signals",
        },
        telephony: {
            title: "Voice Infrastructure",
            description: "Configure Vobiz and sync providers through a studio layout that gives telephony its own premium control room.",
            kicker: "Call Fabric",
        },
        docs: {
            title: "Launch Docs",
            description: "Ship faster with polished quick-start snippets and endpoint references that still stay close to the live product surface.",
            kicker: "Developer Start",
        },
    };

    private readonly trackedStats: TrackedStat[] = [
        { id: "statTokens", label: "Token Flow", detail: "Realtime language consumption across your active workspace." },
        { id: "statTTS", label: "Voice Output", detail: "Generated speech volume for audio surfaces and agents." },
        { id: "statSTT", label: "Speech Input", detail: "Captured listening time and conversational intake." },
        { id: "statKeys", label: "Access Keys", detail: "Active credentials currently powering integrations." },
    ];

    private readonly prefersReducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    private sceneCanvas: HTMLCanvasElement | null = null;
    private ctx: CanvasRenderingContext2D | null = null;
    private particles: Array<{ x: number; y: number; z: number; vx: number; vy: number }> = [];
    private rafId = 0;
    private mouse = { x: 0, y: 0, active: false };

    init(): void {
        document.body.classList.add("reveliq-studio");
        this.decoratePanels();
        this.buildOverviewShell();
        this.injectPageHeaders();
        this.attachTilt();
        this.syncActivePage();
        this.patchNavigation();
        this.buildScene();
    }

    private decoratePanels(): void {
        document
            .querySelectorAll<HTMLElement>(".ds-card, .ds-stat-card, .ds-chart-card, .tele-provider-card, .omni-panel, .ag-agent-card, .ds-code-block")
            .forEach((element, index) => {
                element.classList.add("studio-tilt");
                if (index < 8) {
                    element.dataset.studioDepth = "high";
                }
            });
    }

    private buildOverviewShell(): void {
        const overview = document.getElementById("page-overview");
        const welcome = overview?.querySelector<HTMLElement>(".ds-welcome");
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

    private mirrorStats(): void {
        for (const trackedStat of this.trackedStats) {
            const source = document.getElementById(trackedStat.id);
            const mirror = document.querySelector<HTMLElement>(`[data-stat-mirror="${trackedStat.id}"]`);
            if (!source || !mirror) {
                continue;
            }

            const sync = () => {
                const raw = source.textContent?.trim() || "--";
                mirror.textContent = raw === "â€”" ? "--" : raw;
            };

            sync();
            new MutationObserver(sync).observe(source, { childList: true, characterData: true, subtree: true });
        }
    }

    private injectPageHeaders(): void {
        document.querySelectorAll<HTMLElement>(".ds-page").forEach((page) => {
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
                <p>${meta.description}</p>
            `;
            page.prepend(header);
        });
    }

    private attachTilt(): void {
        const targets = Array.from(document.querySelectorAll<HTMLElement>(".studio-tilt"));
        if (this.prefersReducedMotion) {
            return;
        }

        for (const target of targets) {
            target.addEventListener("pointermove", (event: PointerEvent) => {
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

    private syncActivePage(): void {
        const active = document.querySelector<HTMLElement>(".ds-page.active")?.id.replace("page-", "") || "overview";
        document.body.dataset.activePage = active;
    }

    private patchNavigation(): void {
        const studioWindow = window as Window & {
            switchPage?: (page: string, btn?: HTMLElement | null) => void;
        };
        const existingSwitch = studioWindow.switchPage;
        if (typeof existingSwitch !== "function") {
            return;
        }

        studioWindow.switchPage = (page: string, btn?: HTMLElement | null) => {
            existingSwitch(page, btn);
            document.body.dataset.activePage = page;
        };
    }

    private buildScene(): void {
        this.sceneCanvas = document.getElementById("studioCanvas") as HTMLCanvasElement | null;
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

    private resizeScene(): void {
        if (!this.sceneCanvas) {
            return;
        }

        const ratio = window.devicePixelRatio || 1;
        this.sceneCanvas.width = Math.floor(window.innerWidth * ratio);
        this.sceneCanvas.height = Math.floor(window.innerHeight * ratio);
        this.sceneCanvas.style.width = `${window.innerWidth}px`;
        this.sceneCanvas.style.height = `${window.innerHeight}px`;
        this.ctx?.setTransform(ratio, 0, 0, ratio, 0, 0);
    }

    private seedParticles(): void {
        const count = Math.max(42, Math.round(window.innerWidth / 28));
        this.particles = Array.from({ length: count }, () => ({
            x: Math.random() * window.innerWidth,
            y: Math.random() * window.innerHeight,
            z: 0.25 + Math.random() * 1.3,
            vx: (Math.random() - 0.5) * 0.28,
            vy: (Math.random() - 0.5) * 0.28,
        }));
    }

    private animateScene(): void {
        this.drawScene();
        this.rafId = window.requestAnimationFrame(() => this.animateScene());
    }

    private drawScene(): void {
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

document.addEventListener("DOMContentLoaded", () => {
    new DashboardStudio().init();
});
