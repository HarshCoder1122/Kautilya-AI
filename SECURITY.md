# Security policy

## Reporting a vulnerability

Please report security issues **privately**. Don't open a public issue, discussion or pull request.

- **Preferred:** use GitHub's **Report a vulnerability** button under this repository's *Security* tab (private vulnerability reporting).
- **Or email:** hello@revealiq.in with the subject `SECURITY: <short summary>`.

Please include:

- the affected component (backend route, frontend page, voice worker…) and version or commit
- steps to reproduce, or a proof of concept
- the impact you believe it has

We aim to acknowledge reports within **3 working days** and to share a remediation plan within **10 working days**. We'll credit you in the release notes unless you'd rather stay anonymous.

## Supported versions

Security fixes land on the default branch. If you self-host, keep your deployment up to date with it.

## Scope

In scope: code in this repository, including the backend API, frontend, voice worker, speech engines and KautilyaClaw.

Out of scope: vulnerabilities in third-party services Kautilya connects to (report those to the vendor), findings that need a compromised device or leaked credentials, and missing hardening headers without a demonstrated impact.

## Running Kautilya securely

If you operate a Kautilya instance:

- Keep every credential in environment variables or your platform's secret store, never in the repository. `.gitignore` and `.dockerignore` block the common file names.
- Never put secrets in `REACT_APP_*` variables. They're compiled into the public bundle.
- Set `WEBHOOK_SECRET` when using telephony, and `RAZORPAY_WEBHOOK_SECRET` when using billing.
- Treat `KAUTILYA_API_KEY` as a root credential: it's unmetered and acts as `admin`.
- Restrict CORS with `ALLOWED_ORIGINS`, and keep Firebase **Authorized domains** to hosts you control.
- Restrict your Firebase web API key to your domains in Google Cloud console, and lock down Firestore with security rules.
- Operators in India should also read the [CERT-In incident response runbook](docs/compliance/cert-in-incident-response.md). Reportable incidents must be notified within 6 hours.
