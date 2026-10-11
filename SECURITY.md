# Security

OpsPilot is a portfolio and research project that acts only on a local simulator. It is not hardened for production use.

## Security model in one paragraph

The language model can read through a fixed set of READ tools and can *propose* one action. Deterministic server code decides whether that action may run:
- the policy engine (role, server-assigned risk, environment, customer scope);
- a durable human approval from someone other than the requester;
- verification against the simulator's ground truth.

Retrieved documents, logs, and the request itself are treated as untrusted data. Security does not depend on the model obeying its prompt.

The full threat model, with the enforcement point and test for each threat, is in [docs/threat-model.md](docs/threat-model.md).

## Running it safely

- Keep `backend/.env` out of version control. It is gitignored, and only `.env.example` is committed.
- The built-in accounts (`viewer`, `operator`, `admin` with matching passwords) and the default `JWT_SECRET` exist for local development only. With any `ENVIRONMENT` other than `development`, the backend refuses to start until both are replaced.
- Do not expose the backend publicly as-is. The simulator read endpoints are unauthenticated, tokens are kept in browser `localStorage`, and there is no login rate limiting (see the known gaps in the threat model).

## Reporting a vulnerability

Please open a GitHub issue without exploit details, or contact the repository owner through their GitHub profile, and allow reasonable time for a fix before disclosure.
