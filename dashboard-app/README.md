# Kautilya RevealIQ Studio — Dashboard v2

Modern Vue 3 + Vite + Pinia + Tailwind rebuild of the dashboard.

## Why a rebuild?

The legacy `static/dashboard.html` is a single 5,700+ line file that's
hard to maintain, glitchy on mobile, and slow to iterate on. v2 splits
it into proper modules with a real router, state store, and design
system.

## Stack

- **Vue 3** (script setup, composition API)
- **Vite 5** for build & HMR
- **Vue Router 4** with `/dashboard/...` history mode
- **Pinia** for state (`auth`, `agents`)
- **Tailwind CSS 3** with a custom design-token layer in `src/style.css`
- **Lucide** for icons
- **Firebase JS SDK v10** for auth (same project as legacy dashboard)

## Layout

```
dashboard-app/
├─ index.html
├─ vite.config.js          # base = /static/dashboard-v2/, outDir = ../static/dashboard-v2
├─ tailwind.config.js
├─ src/
│  ├─ main.js              # app bootstrap
│  ├─ App.vue              # auth-aware shell wrapper
│  ├─ style.css            # tokens + tailwind layers
│  ├─ router/index.js
│  ├─ stores/{auth,agents}.js
│  ├─ lib/{firebase,api,format}.js
│  ├─ components/
│  │  ├─ layout/AppShell.vue       # sidebar + topbar + bottom-nav
│  │  └─ agents/AgentCreateModal.vue
│  └─ views/
│     ├─ LoginView.vue
│     ├─ OverviewView.vue
│     ├─ AgentsView.vue
│     ├─ AgentDetailView.vue       # studio (config, knowledge, calls, settings)
│     ├─ CallsView.vue             # global call log + drawer detail
│     └─ PlaceholderView.vue       # for not-yet-migrated routes
```

## Getting started

```bash
# from dashboard-app/
npm install
npm run dev          # http://localhost:5173 (proxies /api -> :5000)
```

For production:

```bash
npm run build        # outputs to ../static/dashboard-v2/
```

Flask's `routes/static_routes.py` will then serve:

- `/dashboard`           → the new SPA (any sub-path falls through to Vue Router)
- `/dashboard-legacy`    → the old `static/dashboard.html` (kept until parity)

If `static/dashboard-v2/index.html` doesn't exist (e.g. you forgot to
build), `/dashboard` automatically falls back to the legacy view.

## Migration status

| Page              | Status        |
|-------------------|---------------|
| Login             | ✅ Done       |
| Overview          | ✅ Done       |
| Agents (list)     | ✅ Done       |
| Agent Studio      | 🟡 Core fields done; KB upload + voice preview pending |
| Recent Calls      | ✅ Done (per-agent + global, drawer detail) |
| Telephony config  | 🔜 Placeholder |
| Billing           | 🔜 Placeholder |
| Campaigns         | 🔜 Placeholder |
| Leads CRM         | 🔜 Placeholder |
| Voice playground  | 🔜 Placeholder |
| API keys          | 🔜 Placeholder |

See `progress.txt` at the repo root for the migration backlog.

## Design system

- **Color**: single accent `#00E6CC` (teal) — everything else is greys.
- **Type**: Inter (UI), JetBrains Mono (numerals/IDs).
- **Spacing**: dense (4/8/12/16) within cards, breathable between sections.
- **Radii**: `8/12/14/16` — rounded-xl2 (14px) is the canonical card.
- **Mobile**: drawer sidebar < 768px + bottom-nav.
- **Motion**: 150-250ms ease-out for state changes; reduced-motion respected.
- **Empty states & skeletons** are first-class — never blank screens.

## Dev tips

- Tailwind classes are aware of the design tokens in `tailwind.config.js`
  (`bg-bg-card`, `text-ink-muted`, `border-line`, etc.).
- Component primitives live in `src/style.css` under `@layer components`
  (`.card`, `.btn`, `.pill`, `.input`, `.nav-item`, …).
- API helpers in `src/lib/api.js` automatically attach the Firebase ID
  token. Add new endpoints there.
