# Contributing to Kautilya AI

Thanks for helping build an open AI workspace for India. Bug reports, fixes, new integrations, Indian-language voices, docs and tests are all welcome.

## Ways to help

- **Report a bug:** open an issue with steps to reproduce, what you expected, and what happened. Screenshots and browser console or server logs help a lot.
- **Suggest a feature:** open an issue describing the problem first. Agreeing on the approach before a large PR saves everyone time.
- **Pick something up:** issues labelled `good first issue` or `help wanted` are ready to take. Comment on one to claim it.
- **Security issues:** please **don't** file a public issue. Follow [SECURITY.md](SECURITY.md).

## Development setup

Follow [docs/getting-started.md](docs/getting-started.md). In short:

```bash
# backend
cd backend && python3.11 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt && cp .env.example .env && python app.py

# frontend (another terminal)
cd frontend && npm install --legacy-peer-deps && cp .env.example .env && npm run dev
```

You don't need every provider key. Features without a key switch themselves off.

## Making a change

1. Fork the repo and branch from the default branch: `git checkout -b fix/short-description`.
2. Keep each PR to one concern. Unrelated refactors are easier to review separately.
3. Match the surrounding style:
   - **Python:** Flask blueprints in `routes/`, business logic in `services/`, configuration only through `config.py` and env vars
   - **React:** function components with hooks, Tailwind classes, shadcn/ui primitives from `components/ui/`
   - Comment the *why*, not the *what*
4. **Never commit secrets.** Add new variables to `backend/.env.example` or `frontend/.env.example` with a short comment, and to [docs/configuration.md](docs/configuration.md). Remember that `REACT_APP_*` values are public.
5. Check your change runs:

   ```bash
   cd frontend && npm run build        # must compile without errors
   cd backend && python -c "import app"   # must import cleanly
   ```

   Then try the feature by hand in the browser. If you add tests, `pytest` for the backend and `npm test` for the frontend are the expected runners.
6. Update the docs if behaviour or configuration changed.
7. Open a pull request using the template. Explain what changed, why, and how you tested it.

## Commit messages

We loosely follow [Conventional Commits](https://www.conventionalcommits.org):

```text
feat(agents): add Tamil voice to Agent Studio
fix(chat): stop Mermaid diagrams making the chat jump while streaming
docs: explain SIP trunk setup for Exotel
```

## Adding an integration

See [docs/integrations.md → Adding a provider](docs/integrations.md#adding-a-provider). Include the provider's logo domain, the scopes you request and why, and a short note in the PR on how you tested the OAuth flow.

## Code of Conduct

This project follows our [Code of Conduct](CODE_OF_CONDUCT.md). By participating you agree to uphold it.

## License

By contributing, you agree that your contributions will be licensed under the [MIT License](LICENSE).
