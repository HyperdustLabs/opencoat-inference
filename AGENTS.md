# Agent Instructions

This repository is a separate product surface from OpenCOAT Runtime.

Follow these boundaries:

- Keep inference access, ledger, x402, wallet, service discovery, and reputation
  code in this repository.
- Do not vendor OpenCOAT Runtime internals here.
- Integration with OpenCOAT Runtime should happen through stable public protocols
  or optional adapters.
- Prefer small PRs with tests.
- Do not push directly to `main`; use branch + PR.

