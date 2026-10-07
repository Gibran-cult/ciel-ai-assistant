# Release Checklist

## Pre-Release

- [ ] Working tree clean
- [ ] Local tests pass
- [ ] GitHub Actions passes
- [ ] Flow JSON validation passes
- [ ] Previous release snapshot remains unchanged
- [ ] CHANGELOG updated
- [ ] Release version verified

## Release

- [ ] Create release commit
- [ ] Create annotated Git tag
- [ ] Push main branch
- [ ] Push release tag
- [ ] Verify GitHub release

## Post-Release

- [ ] GitHub Actions remains green
- [ ] Tag points to the intended release commit
- [ ] Working tree clean
- [ ] Release notes match CHANGELOG

## Current Baseline

- Current production baseline: `v1.0.0`
- Current feature release: `v1.1.0`
- Current release commit: `1a4772a`
- Current branch: `main`