"""
Kautilya AI — Canonical Tool Specification (single source of truth).

WHY THIS FILE EXISTS
====================
The model can only call tools correctly if the prompt that teaches it the
syntax matches the parser that executes it. Before this file, the tool
instructions lived in TWO hand-maintained strings in `system_prompts.py`
while the parser lived in `agent_loop_service.py` — and they drifted
(e.g. [GST_INVOICE:] was executable but undocumented for Pro/Coder, so the
model either never used it or hallucinated its own syntax).

Now every bracket-token tool is declared ONCE in `TOOLS` below, and the
prompt blocks are GENERATED from it:

    render_tool_instructions("full")   → Pro / Coder overlay
    render_tool_instructions("daily")  → compact Daily overlay

RULES FOR ADDING A TOOL
=======================
1. Add the regex handler in `agent_loop_service._parse_actions`.
2. Add the entry here with exact token syntax + when/when-NOT guidance.
That's it — both prompt tiers pick it up automatically and can't drift.

[INTEGRATION:] and MCP tools are NOT listed here: their availability is
per-user, so `agent_loop_service` injects them dynamically at request time
with the user's actual connected tool names.
"""

# ── Universal anti-hallucination contract ─────────────────────────────────
# Prepended to every tier's tool block. Each rule targets a real failure
# mode we've observed: invented tokens, placeholder args, fabricated
# observations, repeated identical calls, tool-calling for meta-questions.
UNIVERSAL_TOOL_RULES = """\
### ABSOLUTE TOOL RULES (violating ANY of these is hallucination):
1. ONLY the bracket tokens listed below exist. NEVER invent a token, tool
   name, or variant — if a token is not in this list, it does not exist.
2. Copy token syntax EXACTLY: same brackets, same colon, same `|` separators.
3. Use REAL values from the user's request — never placeholders like
   "query", "recipient@example.com", "title here". If a required value is
   missing, ASK the user instead of calling the tool.
4. Emit ONE tool call per response, then STOP. The system executes it and
   sends back a line starting with OBSERVATION. NEVER write "OBSERVATION:"
   yourself and NEVER invent or predict a tool's result.
5. After OBSERVATION arrives, answer from its data only. If it reports an
   error or is empty, say so honestly — do not pretend it succeeded.
6. Never repeat the same tool call with the same arguments in one task.
7. If NO tool matches the request, answer directly from your knowledge —
   calling a "close enough" wrong tool is worse than no tool.
8. Capability questions ("what can you do?", "kya kya kar sakte ho?") are
   answered in PLAIN TEXT — never by calling a tool.
"""

# ── Tool registry ─────────────────────────────────────────────────────────
# Each entry:
#   group      — section heading in the rendered prompt
#   syntax     — exact token form(s), shown verbatim to the model
#   guide      — full guidance (Pro/Coder tier)
#   daily      — one/two-line compact guidance (Daily tier); falls back to
#                guide's first sentence when omitted
TOOLS = [
    {
        "group": "Search & Math",
        "syntax": ["[SEARCH: query text here]"],
        "guide": ("Live web search. Use for time-sensitive or post-cutoff facts "
                  "(news, prices, versions, 'who won X'). One focused query per call. "
                  "After OBSERVATION, answer using the findings — do NOT call [SEARCH:] again "
                  "for the same question."),
        "daily": "Live web search for time-sensitive info.",
    },
    {
        "group": "Search & Math",
        "syntax": ["[CALCULATE: math expression here]"],
        "guide": ("Deterministic math evaluation (arithmetic, sqrt, log, trig). Use for any "
                  "non-trivial number work instead of computing in your head."),
        "daily": "Exact math evaluation.",
    },
    {
        "group": "Google Calendar",
        "syntax": [
            "[CALENDAR_LIST: 7]",
            "[CALENDAR_CREATE: Event Title | 2026-05-20T14:00:00 | 2026-05-20T15:00:00 | Optional description]",
            "[CALENDAR_DELETE: title or keyword of the event to delete]",
        ],
        "guide": ("LIST takes days ahead (default 7). CREATE takes title | ISO start | ISO end | "
                  "optional description — compute concrete ISO datetimes from the user's words "
                  "('tomorrow 3pm' → actual date). DELETE takes a title keyword. Events render as "
                  "cards in the UI — after OBSERVATION give a one-line summary, don't re-list them."),
        "daily": ("LIST takes days ahead; CREATE needs concrete ISO datetimes computed from the "
                  "user's words ('tomorrow 3pm' → actual date). Events render as cards — summarize "
                  "in one line."),
    },
    {
        "group": "Gmail",
        "syntax": [
            "[GMAIL_LIST: 10]",
            "[GMAIL_LIST: 10 | from:boss@company.com is:unread]",
            "[GMAIL_SEND: recipient@example.com | Subject line here | Body text here]",
        ],
        "guide": ("LIST takes max count and an optional Gmail search query (from:, is:unread, "
                  "subject:). SEND takes recipient | subject | body — use the real recipient the "
                  "user named; if no address is known, ask. Inbox renders as cards — summarize in "
                  "one line after OBSERVATION."),
        "daily": ("LIST takes max count + optional Gmail query (from:, is:unread). For SEND use the "
                  "real recipient the user named; if unknown, ask first."),
    },
    {
        "group": "Messaging & CRM",
        "syntax": [
            "[WHATSAPP_SEND: +919876543210 | Your message text here]",
            "[SLACK_POST: Your message text here]",
            "[HUBSPOT_CREATE_CONTACT: email@example.com | FirstName | LastName | Company | +91phone]",
        ],
        "guide": ("WhatsApp needs the full international number with country code. HubSpot fields "
                  "beyond email are optional — pass what the user gave, leave the rest empty. "
                  "Confirm the result to the user in one short message after OBSERVATION."),
        "daily": ("WhatsApp needs the full number with country code. HubSpot fields beyond email "
                  "are optional. Confirm the result in one short message."),
    },
    {
        "group": "Python Sandbox — data analysis & charts (pandas / numpy / matplotlib)",
        "syntax": [
            "[RUN_PYTHON: ```python\n"
            "import pandas as pd\n"
            "import matplotlib.pyplot as plt\n"
            "df = pd.DataFrame({'x': [1,2,3,4,5], 'y': [4,1,7,8,3]})\n"
            "df.plot(x='x', y='y', kind='bar', title='Demo Chart')\n"
            "plt.tight_layout()\n"
            "print(df.describe())\n"
            "```]",
        ],
        "guide": ("Use for calculations, data exploration, CSV summaries, or charts. "
                  "pandas / numpy / matplotlib / scipy are pre-installed; matplotlib runs headless — "
                  "open figures are auto-captured as PNGs and shown to the user. No network. Runs "
                  "inside THIS session's Computer workspace (see below) — files written earlier via "
                  "[FILE_WRITE:] (this turn or an earlier one) are on disk and can be read with "
                  "normal relative paths (`pd.read_csv('data.csv')`); anything this run writes stays "
                  "there for later turns too. Keep runs under 15 seconds. The UI shows the code, "
                  "stdout, and charts as cards — do NOT re-paste them; give a one-sentence "
                  "interpretation only."),
        "daily": ("Analysis, math, charts (matplotlib pre-installed, headless, no network). Files "
                  "persist in the session workspace across turns. Do not copy python output back "
                  "into your reply; give a brief one-sentence interpretation."),
    },
    {
        "group": "Kautilya Computer — persistent files (this session's sandboxed workspace)",
        "syntax": [
            "[FILE_WRITE: report.md | ```\nfile contents here\n```]",
            "[FILE_READ: report.md]",
            "[FILE_LIST:]",
        ],
        "guide": ("A real, persistent workspace scoped to THIS chat session — files survive across "
                  "turns (unlike RUN_PYTHON's transient stdout). Use FILE_WRITE for anything the user "
                  "wants built as an actual file (multi-file projects, scripts, data, configs) instead "
                  "of pasting the whole thing inline every turn: name is a relative path (subfolders "
                  "OK, e.g. `src/app.py`), content goes inside a fenced block. FILE_READ pulls a "
                  "file's current content back (e.g. to see one you wrote earlier, or one the user "
                  "uploaded that was staged into the workspace) — use this before editing a file "
                  "instead of guessing its contents. FILE_LIST shows everything in the workspace so "
                  "far. For iterative coding: WRITE the file, RUN_PYTHON to execute/test it, READ back "
                  "any error, then WRITE the fix and rerun — do not re-paste entire files in prose "
                  "just to show a change. No shell access; this is files + Python only. 5MB per file, "
                  "50MB per session."),
        "daily": ("Persistent per-session file workspace: FILE_WRITE (name | fenced content) to save "
                  "a file, FILE_READ (name) to pull it back, FILE_LIST to see what's there. Files "
                  "persist across turns and are visible to RUN_PYTHON. No shell access."),
    },
    {
        "group": "GST Invoice 🇮🇳 — server computes CGST/SGST/IGST deterministically",
        "syntax": [
            "[GST_INVOICE: ```json\n"
            '{"invoice_no":"INV-1","date":"01 Jun 2026","seller":{"name":"","gstin":"","state":""},'
            '"buyer":{"name":"","gstin":"","state":""},'
            '"items":[{"description":"","hsn":"","qty":1,"rate":0,"gst_rate":18}]}\n'
            "```]",
        ],
        "guide": ("Use when the user asks to create/generate a GST invoice or bill. Pass only what "
                  "they gave you (omit unknown fields). You must NOT do the tax maths — the server "
                  "computes all amounts. The tool returns the finished, priced invoice: output its "
                  "<artifact> block VERBATIM, never changing a number."),
        "daily": ("Use for 'GST invoice/bill banao'. Pass only known fields; the server does ALL tax "
                  "maths. Output the returned <artifact> block VERBATIM."),
    },
    {
        "group": "Nearby Maps 🗺️ — renders a LIVE interactive map inside the chat (markers + routes)",
        "syntax": ["[MAP_SEARCH: restaurant]"],
        "guide": ("Use when the user wants nearby places: food/restaurants ('bhookh lagi hai', "
                  "'khana', 'nearby restaurants'), cafe, atm, pharmacy/medical, fuel/petrol, "
                  "hospital, hotel, supermarket, gym, etc. The keyword is the place TYPE in English. "
                  "The platform asks the user for their location and draws the map itself — you do "
                  "NOT have or need their location and must NOT list places yourself. Emit ONLY the "
                  "token; after OBSERVATION give a one-line friendly intro in the user's language."),
        "daily": ("Keyword = place TYPE in English (restaurant, cafe, atm, pharmacy, fuel, hospital, "
                  "hotel…). The platform locates the user and draws the map — never list places "
                  "yourself; give a one-line intro after OBSERVATION."),
    },
    {
        "group": "Journey / Route planner 🧭 — draws a route on the in-chat map (distance + ETA)",
        "syntax": [
            "[ROUTE_PLAN: origin | destination]",
            "[ROUTE_PLAN: destination]   (routes FROM the user's live location)",
        ],
        "guide": ("Use for directions / route / trip planning between places ('route to X', 'how do "
                  "I get to Y', 'Delhi se Jaipur ka rasta'). Use real place names; omit origin to "
                  "start from the user's current location. The platform geocodes both ends and draws "
                  "the journey — emit ONLY the token; after OBSERVATION give a one-line intro, do "
                  "NOT recite turn-by-turn steps."),
        "daily": ("Real place names; omit origin to start from the user's location. Never recite "
                  "turn-by-turn steps."),
    },
]


def _full_block():
    lines = [
        "## ══════════════════════════════════════════════════",
        "## CRITICAL OVERRIDE — AGENTIC TOOL EXECUTION SYSTEM",
        "## ══════════════════════════════════════════════════",
        "",
        "YOU ARE OPERATING INSIDE AN AGENTIC EXECUTION ENVIRONMENT.",
        "This platform intercepts special tokens in your output and executes real actions.",
        "",
        "- You MUST use tools when the user asks for an action you have a tool for.",
        "- You MUST NOT say \"I'm just an LLM\" or \"I don't have access to your accounts\".",
        "- You DO have access to the user's connected integrations. USE THEM.",
        "",
        UNIVERSAL_TOOL_RULES,
        "### TOOL TOKENS — copy format exactly:",
        "",
    ]
    prev_group = None
    for t in TOOLS:
        if t["group"] != prev_group:
            lines.append(f"**{t['group']}**")
            prev_group = t["group"]
        for s in t["syntax"]:
            lines.append(s)
        lines.append(t["guide"])
        lines.append("")
    lines += [
        "### HOW IT WORKS — Example:",
        "",
        "User: \"What's on my calendar this week?\"",
        "You output (the ENTIRE response — nothing else):",
        "[CALENDAR_LIST: 7]",
        "",
        "System returns: OBSERVATION: CALENDAR EVENTS (next 7 days): - Team Standup at 2026-05-16T09:00:00 ...",
        "",
        "You then output the final answer using the observation data.",
        "",
        "---",
        "User: \"Schedule a meeting with Ravi tomorrow at 3pm\"",
        "You output (the ENTIRE response — nothing else):",
        "[CALENDAR_CREATE: Meeting with Ravi | 2026-05-16T15:00:00 | 2026-05-16T16:00:00 | ]",
        "",
        "System returns: OBSERVATION: CALENDAR: Event 'Meeting with Ravi' created successfully.",
        "",
        "You then confirm to the user.",
        "",
        "### If NOT connected:",
        "If OBSERVATION says \"not connected\", tell the user: \"Please connect [service] in Dashboard → Integrations.\"",
    ]
    return "\n".join(lines)


def _daily_block():
    lines = [
        "## AGENTIC TOOL EXECUTION",
        "You operate inside an agentic environment. You DO have access to user accounts. Use tools when asked.",
        "",
        UNIVERSAL_TOOL_RULES,
        "If a service is not connected, return: \"Please connect [service] in Dashboard → Integrations.\"",
        "",
        "Tool token syntax (copy exactly):",
    ]
    for t in TOOLS:
        title = t["group"].split(" — ")[0]
        daily = t.get("daily") or t["guide"]
        one_liners = [s for s in t["syntax"] if "\n" not in s]
        if one_liners:
            lines.append(f"- {title}: " + " | ".join(f"`{s}`" for s in one_liners))
        else:
            # Multi-line token (python / invoice JSON) — show it indented.
            lines.append(f"- {title}:")
            for s in t["syntax"]:
                lines.append("  " + s.replace("\n", "\n  "))
        lines.append(f"  {daily}")
    return "\n".join(lines)


def render_tool_instructions(tier="full"):
    """Generate the tool-instruction prompt block for a tier.
    tier="full"  → Pro / Coder (detailed, with worked examples)
    tier="daily" → Daily (compact)"""
    return "\n" + (_daily_block() if tier == "daily" else _full_block()) + "\n"
