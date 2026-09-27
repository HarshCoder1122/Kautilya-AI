# Kautilya AI: frontend

The React 19 single-page app for [Kautilya AI](../README.md): chat, canvas, Kautilya Computer panel and the dashboard. It's built with Create React App + CRACO, Tailwind CSS and shadcn/ui (Radix).

## Run locally

```bash
npm install --legacy-peer-deps
cp .env.example .env      # Firebase web config + REACT_APP_API_URL
npm run dev               # http://localhost:3000 (hot reload)
```

The backend should be running on `http://localhost:5000`. See [docs/getting-started.md](../docs/getting-started.md).

## Scripts

| Command | What it does |
|---|---|
| `npm run dev` | Development server with hot reload (`craco start`) |
| `npm run build` | Production build into `build/`, then copies it to `../backend/static/` so Flask can serve it |
| `npm start` | Production Express server (`server.js`): serves `build/` and proxies `/api/*` to `BACKEND_URL` |
| `npm test` | Test runner (`craco test`) |

## Layout

| Path | What |
|---|---|
| `src/App.js` | Routing, auth state, token refresh, consent modal |
| `src/pages/` | `ChatPage`, `DashboardPage`, `LoginPage`, `SharedChatPage` |
| `src/components/chat/` | Streaming chat, Markdown rendering, canvas, Mermaid/SVG diagrams, voice, Computer panel |
| `src/components/dashboard/` | Agent Studio, Leads, Campaigns, Analytics, Integrations, TTS/STT Studio, Billing… |
| `src/components/ui/` | shadcn/ui primitives |
| `src/lib/` | API client (axios + SSE), Firebase, artifact parsing, deck export, PWA |
| `server.js` | Production server and API proxy |

> [!WARNING]
> Every `REACT_APP_*` variable is compiled into the public bundle. Never put secrets in them. See [configuration.md](../docs/configuration.md#frontend-variables).
