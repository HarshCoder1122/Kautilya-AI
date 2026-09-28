# CERT-In Incident Response Runbook
## Kautilya AI (ai.revealiq.in) — Operated by Harsh Vardhan (RevealIQ)

> **Legal basis:** CERT-In Cybersecurity Directions 2022 issued under Section 70B of the IT Act, 2000.
> **Mandatory reporting window:** Within **6 hours** of becoming aware of a cyber incident.
> **Report to:** incident@cert-in.org.in | Fax: 1800-11-4949 | Portal: https://www.cert-in.org.in

---

## Quick Reference

| What | Contact / URL |
|------|---------------|
| CERT-In email | incident@cert-in.org.in |
| CERT-In hotline | 1800-11-4949 (toll-free) |
| CERT-In portal | https://www.cert-in.org.in |
| DPBI notification (72h) | https://www.dpboard.gov.in (when operational) |
| Internal POC | Harsh Vardhan — hello@revealiq.in |
| Firebase console | https://console.firebase.google.com |
| HuggingFace Space | https://huggingface.co/spaces/[your-space] |
| Resend (email) | https://resend.com/emails |
| Razorpay | https://dashboard.razorpay.com |

---

## 1. Incident Classification

### 1.1 CERT-In Mandatory Reportable Incidents (6-hour window)
All of the following must be reported to CERT-In within 6 hours:

1. Targeted scanning/probing of critical networks/systems
2. Compromise of critical systems/information
3. Unauthorised access to IT systems and data
4. **Data breach or theft** — any personal data leaked
5. Defacement of websites
6. Malicious code attacks (ransomware, malware, trojans, bots)
7. Attacks on servers (database, mail, DNS)
8. Identity theft / fraud
9. DDoS attacks
10. DNS/BGP hijacking
11. Attacks on Internet-of-Things (IoT) devices
12. Incidents affecting Digital Payment Systems
13. Fake mobile apps
14. Unauthorised access to social media accounts
15. Attacks/incidents against cloud infrastructure
16. Incidents detected by SIEM/SOC
17. Phishing attacks targeting the organisation
18. Rogue/malicious apps
19. Supply chain attacks
20. Cyber espionage

### 1.2 Severity Levels

| Level | Description | Response SLA |
|-------|-------------|-------------|
| **P1 — Critical** | Active breach with data exfiltration; ransomware; complete system compromise | 0–1 hour internal, 6 hours CERT-In |
| **P2 — High** | Suspected breach; DDoS; credential stuffing with confirmed account takeovers | 1–2 hours internal, 6 hours CERT-In |
| **P3 — Medium** | Suspicious activity; failed brute force; anomalous API usage; single account compromise | 2–4 hours internal, report if escalates |
| **P4 — Low** | Security config drift; dependency vulnerability; isolated bot traffic | 24 hours internal investigation |

---

## 2. Incident Response Steps

### Phase 1 — DETECT & ASSESS (0–30 minutes)

- [ ] Identify the type of incident from Section 1.1 above
- [ ] Determine which systems are affected:
  - HuggingFace Space (Flask backend + ML inference)
  - Google Firestore (user data, chat history, API keys)
  - Firebase Auth (user accounts)
  - Resend (email delivery)
  - Razorpay (billing)
- [ ] Estimate scope: how many users affected? What data categories?
- [ ] Record: **exact time of discovery** (this starts the 6-hour CERT-In clock)
- [ ] Screenshot / preserve all evidence (logs, error messages, requests)

### Phase 2 — CONTAIN (30–90 minutes)

- [ ] **If HuggingFace Space is compromised:**
  - Pause/restart the Space from the HuggingFace dashboard
  - Change HuggingFace API token and Space secrets
  - Rotate all API keys stored in Space secrets (Anthropic, LLM providers, Resend, etc.)
- [ ] **If Firebase/Firestore is compromised:**
  - Revoke all Firebase service account credentials from Google Cloud Console
  - Disable the compromised Firebase project temporarily if needed
  - Review Firebase Auth → "Users" panel for unauthorized accounts
- [ ] **If API keys are leaked:**
  - Revoke all api_keys documents in Firestore
  - Rotate the WEBHOOK_SECRET env var
  - Rotate RESEND_API_KEY, ANTHROPIC_API_KEY, and all other secrets
- [ ] **If user accounts are compromised:**
  - Use Firebase Admin SDK to revoke all refresh tokens: `auth.revoke_refresh_tokens(uid)`
  - Force re-authentication for all users
- [ ] **Block the attack vector** (firewall rule, rate limit, IP block if applicable)

### Phase 3 — REPORT TO CERT-In (within 6 hours of discovery)

**Send email to: incident@cert-in.org.in**

**Subject:** `Cyber Incident Report — Kautilya AI (ai.revealiq.in) — [Date] — [Incident Type]`

**Mandatory fields in the report:**
```
1. Organisation name: RevealIQ / Kautilya AI
2. Organisation type: Individual developer / SaaS platform
3. Website: https://ai.revealiq.in
4. Contact name: Harsh Vardhan
5. Contact email: hello@revealiq.in
6. Contact phone: [your phone]
7. Incident type: [from the 20 categories in Section 1.1]
8. Date and time of incident (IST):
9. Date and time of detection (IST):
10. Affected systems:
11. Estimated number of affected users:
12. Nature of data affected (if breach): [name, email, chat history, etc.]
13. Steps taken so far to contain:
14. Root cause (if known):
15. Additional details / logs:
```

### Phase 4 — NOTIFY DATA PRINCIPALS (DPDP Act, within 72 hours)

If personal data was breached:

- [ ] Draft notification email to affected users with:
  - What happened (plain language)
  - What data was affected
  - When it happened
  - What we have done to contain it
  - What users should do (change passwords, watch for phishing, etc.)
  - Contact: hello@revealiq.in / hello@revealiq.in
- [ ] Send via Resend (or bulk email if Resend is compromised)
- [ ] File notification with DPBI at https://www.dpboard.gov.in (once portal is operational)
- [ ] If DPBI portal not yet operational: document the notification attempt + send to hello@revealiq.in for record-keeping

### Phase 5 — ERADICATE & RECOVER

- [ ] Patch or remove the vulnerability
- [ ] Restore from last known-good backup (Firestore export / HuggingFace code snapshot)
- [ ] Re-enable services gradually with enhanced monitoring
- [ ] Verify all rotated credentials are working
- [ ] Confirm no backdoors remain (review recent code commits, Space file changes)

### Phase 6 — POST-INCIDENT (within 7 days)

- [ ] Write an internal incident report:
  - Timeline (discovery → containment → CERT-In report → user notification → recovery)
  - Root cause analysis
  - What controls failed
  - What worked well
  - Action items to prevent recurrence
- [ ] Update this runbook if gaps were found
- [ ] File 30-day follow-up report with CERT-In if initially requested

---

## 3. Log Retention Requirements (CERT-In 2022)

| Log Type | Retention Period | Storage Location |
|----------|-----------------|------------------|
| Application logs (Flask/gunicorn) | 180 days | HuggingFace Space (+ forward to India-region GCS Mumbai if possible) |
| Firebase Auth logs | 180 days | Google Cloud (retained automatically) |
| Firestore access logs | 180 days | Google Cloud Audit Logs |
| API request logs | 180 days | Application logs |
| User subscriber records | 5 years | Firestore (soft-delete, not hard-delete) |
| Billing records | 7 years | Razorpay + Firestore (GST compliance) |

**Action:** Set up log export to a persistent store. HuggingFace Space logs are ephemeral — they disappear when the Space restarts. Use the following to forward logs:
- Flask `logging` → write to a file persisted in Space storage, or
- Forward to Google Cloud Logging (GCP project) → set retention to 180 days

---

## 4. NTP Synchronization (CERT-In Requirement)

All servers must sync time with NIC (National Informatics Centre) servers:
- `time.nic.in`
- `samay.nic.in`

**HuggingFace Spaces:** NTP is managed by the host (Docker container). You cannot directly configure NTP on HuggingFace. Document this limitation and use UTC timestamps from the system (which HuggingFace syncs via their infrastructure).

**Self-managed servers (if any):** Configure `/etc/ntp.conf` or `chronyd.conf`:
```
server time.nic.in iburst
server samay.nic.in iburst
```

---

## 5. Contact Directory

| Role | Name | Contact |
|------|------|---------|
| Developer / Security POC | Harsh Vardhan | scatterpieanalytics17@gmail.com |
| Grievance Officer | Harsh Vardhan | hello@revealiq.in |
| General support | — | hello@revealiq.in |
| CERT-In | — | incident@cert-in.org.in |
| CERT-In hotline | — | 1800-11-4949 |
| CERT-In portal | — | https://www.cert-in.org.in |
| Firebase support | Google | https://console.firebase.google.com |
| HuggingFace support | — | https://discuss.huggingface.co |
| Razorpay support | — | https://dashboard.razorpay.com/support |

---

## 6. Pre-Incident Checklist (Review Monthly)

- [ ] All HuggingFace Space secrets rotated in the last 90 days
- [ ] Firebase service account credentials reviewed
- [ ] No hardcoded secrets in the codebase (`git grep -r "sk-" .` etc.)
- [ ] Firestore security rules reviewed — users can only access their own data
- [ ] All npm/pip dependencies up to date (`npm audit` / `pip-audit`)
- [ ] Webhook secrets are set (`WEBHOOK_SECRET` env var)
- [ ] iframe `sandbox` attributes do not include `allow-same-origin` with `allow-scripts`
- [ ] CERT-In email (incident@cert-in.org.in) is in address book and not spam-filtered

---

*Last updated: May 29, 2026 — Harsh Vardhan (RevealIQ)*
