# Integrations & MCP

Kautilya agents can act in 59 third-party apps, and in anything else that speaks the [Model Context Protocol](https://modelcontextprotocol.io). Chat uses them through tool calls; voice agents use them mid-call, for example to book a meeting or create a CRM contact.

## How connecting works

There are two kinds of provider:

| Kind | Operator setup | End-user experience |
|---|---|---|
| **OAuth** (41 providers) | Register **one** OAuth app per provider and set `<PROVIDER>_CLIENT_ID` / `<PROVIDER>_CLIENT_SECRET` | Click **Connect**, approve, done |
| **API key** (18 providers, 🔑 below) | Nothing | Paste their own key once. It's stored per user in Firestore. |

Until an operator configures an OAuth provider, the UI shows it as **"Beta · Available soon"**. Users may also paste their own OAuth app credentials, which override the operator's.

### OAuth callback URL

Set `CENTRAL_DOMAIN` (or `OAUTH_REDIRECT_DOMAIN`) to your public backend host. Every provider then uses:

```text
https://<CENTRAL_DOMAIN>/api/integrations/<provider_id>/callback
```

Some providers share one app per family. Register **all** of the family's callback URLs in that single app:

| Env prefix | Covers |
|---|---|
| `GOOGLE_` | `gmail`, `google_calendar`, `google_drive`, `google_sheets`, `google_tasks`, `google_docs`, `google_contacts`, `youtube`, `google_analytics`, `google_ads` |
| `MICROSOFT_` | `outlook`, `onedrive`, `microsoft_teams` |
| `ZOHO_` | `zoho` (CRM), `zoho_books`, `zoho_inventory` |
| `FACEBOOK_` | `facebook`, `instagram` |

A provider-specific pair such as `GMAIL_CLIENT_ID` takes precedence over the family pair.

## Provider catalog

| Category | Providers |
|---|---|
| 🇮🇳 India business stack | Tally Prime 🔑, Vyapar 🔑, ClearTax GST 🔑, Gupshup WhatsApp 🔑, Interakt 🔑, MSG91 🔑 |
| CRM & sales | HubSpot, Salesforce, Zoho CRM, Pipedrive |
| Messaging | WhatsApp Business 🔑, Slack 🔑, Microsoft Teams, Discord, Twilio (SMS/Voice) 🔑, Telegram Bot 🔑 |
| Email | Gmail, Outlook & Calendar, SendGrid 🔑, Mailgun 🔑 |
| Calendar & meetings | Google Calendar, Zoom, Calendly |
| Automation | Zapier 🔑 |
| Developer tools | GitHub, Linear, Jira & Confluence, GitLab |
| Productivity & docs | Google Tasks, Google Contacts, YouTube, Notion, Airtable, Asana |
| Cloud storage | Google Drive, Google Sheets, Google Docs, OneDrive, Dropbox, Box |
| Payments | Razorpay, Stripe |
| Accounting | QuickBooks, Xero, Zoho Books |
| E-commerce | Zoho Inventory, Shopify 🔑 |
| Marketing | Mailchimp, Facebook Pages, Instagram, Google Ads |
| Logistics & shipping | Shiprocket 🔑, Delhivery 🔑 |
| HR & payroll | RazorpayX Payroll 🔑, Keka HR 🔑 |
| Support desk | Intercom |
| Analytics | Google Analytics |
| Social | LinkedIn, X (Twitter) |

The catalog lives in `PROVIDERS` in [`backend/routes/integrations_routes.py`](../backend/routes/integrations_routes.py). Tool implementations are in [`backend/services/integration_tools.py`](../backend/services/integration_tools.py).

### Adding a provider

1. Add an entry to `PROVIDERS` with a `label` and `category`, plus its OAuth endpoints and scopes, or `api_manual: True` with the credential `fields` users should paste.
2. Add its logo domain to `_DOMAINS` (and to `_INDIA` if it belongs in the India stack).
3. Implement the actions in `services/integration_tools.py` and expose them to the agent loop.
4. Document any new env vars in `backend/.env.example`.

## MCP servers

At startup the backend spawns the MCP servers enabled in [`backend/mcp_config.json`](../backend/mcp_config.json) over stdio and registers their tools with the agent loop as `mcp_<server>_<tool>`.

| Server | On by default | Needs |
|---|---|---|
| `fetch` | ✅ | nothing |
| `sequential_thinking` | ✅ | nothing |
| `time` | ✅ | nothing |
| `google_drive` | ✅ | `GDRIVE_CREDENTIALS_PATH` |
| `filesystem` | | `MCP_FS_ROOT` |
| `brave_search` | | `BRAVE_API_KEY` |
| `github` | | `GITHUB_PERSONAL_ACCESS_TOKEN` |
| `memory` | | nothing |
| `slack` | | `SLACK_BOT_TOKEN`, `SLACK_TEAM_ID` |
| `postgres` | | `POSTGRES_URL` |
| `puppeteer` | | nothing |

A server is skipped when a variable in its `env_required` list is missing. Useful controls:

```ini
MCP_DISABLED=true                     # skip MCP entirely
MCP_ENABLED_SERVERS=fetch,time        # allowlist
MCP_SKIP_SERVERS=google_drive         # blocklist
```

To add a server, append an entry with `command`, `args`, `env_required` and `"enabled": true`. Anything launchable with `npx`, `uvx` or a binary works.

### Custom MCP servers per user

Under **Dashboard → Integrations → Custom MCP servers**, users can register their own remote MCP endpoints (SSE transport). They're stored in `users/{uid}/mcp_servers` and only available to that user's agents.

## KautilyaClaw: personal agents on Telegram & WhatsApp

[`kautilyaclaw/`](../kautilyaclaw) wraps [OpenClaw](https://docs.openclaw.ai) so a personal agent lives in Telegram or WhatsApp and thinks with Kautilya models through the OpenAI-compatible API. Users set it up from **Dashboard → KautilyaClaw**; the backend side lives in `routes/claw_routes.py`. See the [KautilyaClaw README](../kautilyaclaw/README.md) for self-hosting it with Docker Compose or on a Hugging Face Space.
