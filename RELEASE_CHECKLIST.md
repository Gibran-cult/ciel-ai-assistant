# Release Checklist

## Pre-Release

- [ ] Work happens on a branch from the latest `main`; one pull request per change.
- [ ] Offline suite passes locally (command in `README.md`) and in GitHub Actions.
- [ ] A changed main flow gets a new snapshot `flow/vX.Y.Z/` and a contract test `tests/test_flow_vXYZ_contract.py`; earlier snapshots stay unchanged.
- [ ] Custom components are edited in `flow/components/`, and the snapshot embeds the same code (checked by the contract tests).
- [ ] Component inputs do not reuse Langflow `Component` attribute names such as `user_id` (checked by `tests/test_flow_v141_contract.py`).
- [ ] App changes that touch rendering are checked in a browser or with Streamlit's `AppTest`.
- [ ] Prompt or flow changes are tried on a separate test flow in Langflow first (import a copy without its `id`), never on the production flow.
- [ ] A live quality run (`python tests/collect_quality.py`) shows no regression in response quality, and failed cases are explained.
- [ ] `CHANGELOG.md` describes the change and its measurements.

## Deploying a Flow Change to Langflow

The production flow is updated in place, so `FLOW_ID` and the app's secrets stay the same.

1. Merge the pull request and wait for CI to pass.
2. Confirm `main` matches the tested snapshot (`git diff origin/main <tested commit> -- flow/vX.Y.Z app.py`).
3. Back up the live production flow to `~/.ciel_ai/flow_backups/` on the Langflow host.
4. Replace only the flow's `data` with the snapshot (`PATCH /api/v1/flows/<FLOW_ID>`), keeping id, name and endpoint.
5. Verify the live graph equals the snapshot, then send real requests through the ngrok tunnel (the path the public app uses) for the changed behavior and for anonymous memory isolation (memory count must not change).
6. If anything fails, restore the backup with the same `PATCH`.

Sub-flows (Math Tutor Agent, Verified Data Analyst, Knowledge Retriever, Web Research Assistant) are not in this repository. Back them up the same way before changing them, record the change in `CHANGELOG.md`, and verify through ngrok.

## Release

- [ ] Create an annotated tag on the release commit on `main` (`git tag -a vX.Y.Z <commit> -m "..."`).
- [ ] Push the tag (`git push origin vX.Y.Z`).
- [ ] Optionally publish a GitHub Release with the CHANGELOG section.

## Post-Release

- [ ] The tag points at the intended commit.
- [ ] GitHub Actions is green on `main`.
- [ ] The public app answers a test message.

## Release Tags

| Tag | Commit on `main` | Contents |
|---|---|---|
| `v1.0.0` | `a318c1e` | Production baseline |
| `v1.1.0` | `1a4772a` | Memory context optimization |
| `v1.2.0` | `b549d56` (merge of #4) | Vision router, pricing page, workspace UI |
| `v1.3.0` | `b87882c` (from #5) | Session per chat, per-user memory, rate limits |
| `v1.4.0` | `7bbe3f2` (merge of #5) | Ciel identity |
| `v1.4.1` | `28fa30c` (merge of #6) | Fix per-user memory isolation |
| `v1.5.0` | `7b57755` (merge of #7) | Ciel Table Analyst |
| `v1.5.1` | `688e5c3` (merge of #8) | Clean answers, number format, project context |
| `v1.5.2` | merge of the documentation PR | Session-isolated live tests, safe errors, cleanup, docs, Langflow operations |

`v1.3.0` points at its commit inside #5 because #5 merged v1.3.0 and v1.4.0 together; that commit passes its own tests.

## Current Release

- Current release: `v1.5.2` (main flow snapshot `flow/v1.5.1`).
- Production baseline: `v1.0.0`.
- Latest live quality run: 2026-10-14, response quality 9/9, automated checks 5/5, healthy.
