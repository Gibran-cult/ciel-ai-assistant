# Release Checklist

## Pre-Release

- [x] Working tree clean
- [x] Local tests pass
- [x] GitHub Actions passes
- [x] Flow JSON validation passes
- [x] Previous release snapshot remains unchanged
- [x] CHANGELOG updated
- [x] Release version verified

## Release

- [x] Create release commit
- [x] Create annotated Git tag
- [x] Push main branch
- [x] Push release tag
- [ ] Verify GitHub Release

## Post-Release

- [x] Tag points to the intended release commit
- [x] Working tree clean
- [x] Release notes match CHANGELOG
- [ ] Verify the latest GitHub Actions run is green after the final documentation commits

## Current Baseline

- Current production baseline: `v1.0.0`
- Current feature release: `v1.1.0`
- Current release commit: `1a4772a`
- Current branch: `main`

## Notes

- Git tag `v1.0.0` is preserved as the production baseline.
- Git tag `v1.1.0` is the current feature release.
- GitHub Release verification is intentionally left unchecked until the release page is confirmed.
- The latest offline regression suite passed 16/16 locally.
