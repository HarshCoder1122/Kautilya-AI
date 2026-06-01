# Kautilya — Integrations ENV reference

How it works (one-tap model):
- For **OAuth** integrations the operator registers ONE app per provider and puts
  its `*_CLIENT_ID` / `*_CLIENT_SECRET` here. End-users then just click **Connect**
  — no keys, no forms. (Users *may* still paste their own app creds in the UI,
  which override env.)
- For **API-key** integrations there is nothing to put in env — each user pastes
  their key once in the Integrations page (stored encrypted per-user in Firestore).
- Redirect URL for every provider:  `https://<CENTRAL_DOMAIN>/api/integrations/<id>/callback`

## Global (required once)
```
CENTRAL_DOMAIN=ai.revealiq.in          # or OAUTH_REDIRECT_DOMAIN — used to build OAuth redirect URIs
```

## OAuth redirect / callback URLs — paste these into each provider's console
Every redirect URI is `https://ai.revealiq.in/api/integrations/<id>/callback`.
For a **shared app** (Google / Microsoft / Zoho / Facebook) register *all* of that
family's URLs in the one OAuth app (each child id has its own callback path).

### Google app (one OAuth client — add ALL of these as Authorized redirect URIs)
```
https://ai.revealiq.in/api/integrations/gmail/callback
https://ai.revealiq.in/api/integrations/google_calendar/callback
https://ai.revealiq.in/api/integrations/google_drive/callback
https://ai.revealiq.in/api/integrations/google_sheets/callback
https://ai.revealiq.in/api/integrations/google_tasks/callback
https://ai.revealiq.in/api/integrations/google_docs/callback
https://ai.revealiq.in/api/integrations/google_contacts/callback
https://ai.revealiq.in/api/integrations/youtube/callback
https://ai.revealiq.in/api/integrations/google_analytics/callback
https://ai.revealiq.in/api/integrations/google_ads/callback
```

### Microsoft app (one Azure AD app — add ALL)
```
https://ai.revealiq.in/api/integrations/outlook/callback
https://ai.revealiq.in/api/integrations/onedrive/callback
https://ai.revealiq.in/api/integrations/microsoft_teams/callback
```

### Zoho app (one client — add ALL)
```
https://ai.revealiq.in/api/integrations/zoho/callback
https://ai.revealiq.in/api/integrations/zoho_books/callback
https://ai.revealiq.in/api/integrations/zoho_inventory/callback
```

### Facebook app (one app — add ALL)
```
https://ai.revealiq.in/api/integrations/facebook/callback
https://ai.revealiq.in/api/integrations/instagram/callback
```

### Per-provider apps (one redirect URI each)
```
https://ai.revealiq.in/api/integrations/hubspot/callback
https://ai.revealiq.in/api/integrations/salesforce/callback
https://ai.revealiq.in/api/integrations/github/callback
https://ai.revealiq.in/api/integrations/notion/callback
https://ai.revealiq.in/api/integrations/airtable/callback
https://ai.revealiq.in/api/integrations/asana/callback
https://ai.revealiq.in/api/integrations/linear/callback
https://ai.revealiq.in/api/integrations/jira/callback
https://ai.revealiq.in/api/integrations/gitlab/callback
https://ai.revealiq.in/api/integrations/dropbox/callback
https://ai.revealiq.in/api/integrations/box/callback
https://ai.revealiq.in/api/integrations/razorpay/callback
https://ai.revealiq.in/api/integrations/stripe/callback
https://ai.revealiq.in/api/integrations/quickbooks/callback
https://ai.revealiq.in/api/integrations/xero/callback
https://ai.revealiq.in/api/integrations/pipedrive/callback
https://ai.revealiq.in/api/integrations/intercom/callback
https://ai.revealiq.in/api/integrations/zoom/callback
https://ai.revealiq.in/api/integrations/calendly/callback
https://ai.revealiq.in/api/integrations/mailchimp/callback
https://ai.revealiq.in/api/integrations/linkedin/callback
https://ai.revealiq.in/api/integrations/twitter/callback
https://ai.revealiq.in/api/integrations/discord/callback
```

## Shared-app families (one app powers several integrations)
```
GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET          # gmail, google_calendar, google_drive, google_sheets,
                                                 # google_tasks, google_docs, google_contacts, youtube,
                                                 # google_analytics, google_ads
MICROSOFT_CLIENT_ID / MICROSOFT_CLIENT_SECRET    # outlook, onedrive, microsoft_teams
ZOHO_CLIENT_ID / ZOHO_CLIENT_SECRET              # zoho, zoho_books, zoho_inventory
FACEBOOK_CLIENT_ID / FACEBOOK_CLIENT_SECRET      # facebook, instagram
```

## Per-provider OAuth (id → env vars)
Each needs `<ID>_CLIENT_ID` and `<ID>_CLIENT_SECRET` (UPPER-CASE id):
```
HUBSPOT_CLIENT_ID / HUBSPOT_CLIENT_SECRET
SALESFORCE_CLIENT_ID / SALESFORCE_CLIENT_SECRET
GITHUB_CLIENT_ID / GITHUB_CLIENT_SECRET
NOTION_CLIENT_ID / NOTION_CLIENT_SECRET
AIRTABLE_CLIENT_ID / AIRTABLE_CLIENT_SECRET
ASANA_CLIENT_ID / ASANA_CLIENT_SECRET
LINEAR_CLIENT_ID / LINEAR_CLIENT_SECRET
JIRA_CLIENT_ID / JIRA_CLIENT_SECRET              # Atlassian app
GITLAB_CLIENT_ID / GITLAB_CLIENT_SECRET
DROPBOX_CLIENT_ID / DROPBOX_CLIENT_SECRET
BOX_CLIENT_ID / BOX_CLIENT_SECRET
RAZORPAY_CLIENT_ID / RAZORPAY_CLIENT_SECRET       # 🇮🇳 needs Razorpay partner approval
STRIPE_CLIENT_ID / STRIPE_CLIENT_SECRET           # Stripe Connect
QUICKBOOKS_CLIENT_ID / QUICKBOOKS_CLIENT_SECRET
XERO_CLIENT_ID / XERO_CLIENT_SECRET
PIPEDRIVE_CLIENT_ID / PIPEDRIVE_CLIENT_SECRET
INTERCOM_CLIENT_ID / INTERCOM_CLIENT_SECRET
ZOOM_CLIENT_ID / ZOOM_CLIENT_SECRET
CALENDLY_CLIENT_ID / CALENDLY_CLIENT_SECRET
MAILCHIMP_CLIENT_ID / MAILCHIMP_CLIENT_SECRET
LINKEDIN_CLIENT_ID / LINKEDIN_CLIENT_SECRET
TWITTER_CLIENT_ID / TWITTER_CLIENT_SECRET
DISCORD_CLIENT_ID / DISCORD_CLIENT_SECRET
```

## API-key integrations (NO env — user pastes in UI)
whatsapp, slack, zapier, twilio, sendgrid, mailgun, telegram, shopify,
tally 🇮🇳, vyapar 🇮🇳, shiprocket 🇮🇳, delhivery 🇮🇳, cleartax_gst 🇮🇳,
gupshup 🇮🇳, interakt 🇮🇳, msg91 🇮🇳, razorpayx 🇮🇳, keka 🇮🇳

> Note: catalog + connect/save/OAuth wiring is live. The *action layer* (each
> provider's send/read tool the agent calls) is added per-provider in
> `services/integration_tools.py` as you roll them out.
