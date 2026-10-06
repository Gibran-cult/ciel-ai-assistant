# Ciel AI Master � Change Log

## Flow Snapshot Baseline

### v1.0.0
- Baseline snapshot stored at low/v1.0.0/Ciel_AI_Long-Term_Memory_Master.json
- Snapshot is tracked in the current main repository history.
- Snapshot is currently identical to the working-tree version.
- No production-flow changes are introduced by this versioning step.

### Git History Note
The Git tag 1.0.0 points to commit 318c1e from the previous repository lineage.
The current repository's flow snapshot exists in the current main lineage.
These two histories are intentionally preserved rather than force-merged.

## Future Changes

### v1.1.0
Record changes to:
- Flow structure
- Prompts
- Models
- Tools
- Memory behavior
- Agent configuration
- Performance-related configuration
- Security-related configuration

Each future flow revision should:
1. Preserve the previous version snapshot.
2. Create a new version directory.
3. Document the reason for the change.
4. Record affected components.
5. Record validation or regression-test results.

### v1.1.0
- Optimized Ciel Memory Search output for lower agent context usage.
- Kept Memory Search Top K at 5.
- Removed query, distance, and metadata from the agent-facing memory output.
- Preserved the retrieved memory contents and ranking order.
- Multi-query recall benchmark achieved 100% recall with Top K = 5.
- Compact output benchmark reduced memory-context size by approximately 60.7% at Top K = 5.
- No change was made to the v1.0.0 baseline snapshot.
