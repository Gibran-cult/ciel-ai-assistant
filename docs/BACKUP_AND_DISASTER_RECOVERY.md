# Ciel AI Master - Backup and Disaster Recovery

## Purpose

This document defines the backup and recovery procedure for Ciel AI Master.

The goal is to make the project recoverable after accidental file loss, local environment failure, repository corruption, or loss of the development machine.

## Recovery Sources

The primary recovery source is the GitHub repository.

The repository currently contains:

- Main branch: `main`
- Production baseline tag: `v1.0.0`
- Feature release tag: `v1.1.0`
- Versioned Langflow flow snapshots under `flow/`

The `v1.0.0` tag is preserved as the production baseline.

The `v1.1.0` tag represents the memory context optimization release.

## What Must Be Backed Up

### Source Repository

The GitHub repository is the authoritative source for tracked application code, tests, documentation, CI configuration, and versioned flow snapshots.

### Flow Snapshots

The versioned flow snapshots are stored under:

```text
flow/
+-- v1.0.0/
|   +-- Ciel_AI_Long-Term_Memory_Master.json
|
+-- v1.1.0/
    +-- Ciel_AI_Long-Term_Memory_Master.json
```

These snapshots should be preserved as release artifacts.

### Runtime Secrets

Production secrets are intentionally not stored in Git.

Recovery therefore requires restoring runtime configuration separately.

Examples of sensitive runtime configuration include:

- `NGROK_URL`
- `NGROK_USER`
- `NGROK_PASSWORD`
- `LANGFLOW_API_KEY`
- `FLOW_ID`

Do not place the real values in the repository, documentation, issue tracker, or public backup.

## Recovery Procedure

### 1. Clone the Repository

From a new or repaired machine:

```powershell
git clone https://github.com/Gibran-cult/ciel-ai-assistant
cd ciel-ai-assistant
```

### 2. Verify Repository State

```powershell
git status
git branch
git tag -n
```

Confirm that the expected branch and release tags are available.

### 3. Select the Required Release

For recovery to the production baseline:

```powershell
git checkout v1.0.0
```

For the current feature release:

```powershell
git checkout v1.1.0
```

For continued development on the latest main branch:

```powershell
git checkout main
git pull origin main
```

### 4. Restore Python Dependencies

Install the dependencies defined by the repository:

```powershell
python -m pip install -r requirements.txt
```

The runtime environment must also provide the external services required by the flow.

### 5. Restore Runtime Configuration

Recreate the required environment configuration from a secure secret store or other protected backup.

Do not recover secrets by copying them into Git-tracked files.

### 6. Restore Langflow Flow

Import or restore the appropriate versioned Langflow flow snapshot from:

```text
flow/v1.0.0/Ciel_AI_Long-Term_Memory_Master.json
```

or:

```text
flow/v1.1.0/Ciel_AI_Long-Term_Memory_Master.json
```

Use the release that matches the intended recovery target.

### 7. Restore Supporting Runtime Services

The production flow depends on runtime services such as Langflow and Ollama.

Long-term memory also uses a local Chroma database and the configured Ollama embedding service.

These runtime services and their required local data must be restored separately from Git.

## Post-Recovery Verification

Run basic repository checks:

```powershell
git status
git log --oneline --decorate -8
git tag -n
```

Run the deterministic offline CI-equivalent tests:

```powershell
python -m unittest -v tests.test_memory_v110_contract tests.test_resilience tests.test_performance_snapshot
```

Verify that the application can start with the restored runtime configuration.

Verify the health-check path.

Verify normal assistant behavior.

Verify long-term memory search and store behavior.

Verify specialist routing for the supported task categories.

## Recovery Validation

A recovery should not be considered complete until:

- the intended Git release or branch is restored,
- dependencies are installed,
- runtime secrets are restored securely,
- the Langflow flow snapshot is restored,
- required runtime services are available,
- deterministic tests pass,
- health checks pass,
- normal application behavior is verified.

## Backup Policy

GitHub provides the primary repository-level recovery path.

Release tags provide immutable version references for released flow states.

Important runtime data that is not tracked by Git must have a separate protected backup strategy.

This includes runtime secrets and local long-term memory data when that data is required for continuity.

## Disaster Scenarios

### Local Working Copy Lost

Recovery:

1. Clone the GitHub repository.
2. Select the required branch or release tag.
3. Reinstall dependencies.
4. Restore runtime configuration.
5. Restore required services and local data.
6. Run verification tests.

### Main Branch Accidentally Modified

Recovery:

1. Inspect the Git history.
2. Identify the intended release tag.
3. Restore or branch from the known-good tag.
4. Re-run validation before deployment.

### Production Configuration Lost

Recovery:

1. Obtain credentials from the protected secret source.
2. Recreate environment configuration.
3. Do not commit the recovered values.
4. Run health and integration checks.

### Local Long-Term Memory Data Lost

Recovery depends on whether the Chroma data has been backed up separately.

Git does not contain the local memory database.

If no separate backup exists, the application can still be restored from the repository, but previously stored local memory cannot be reconstructed from Git alone.

## Recovery Principle

The repository and release tags restore the software state.

Protected runtime backups restore the environment state.

Both are required for a complete production recovery.
