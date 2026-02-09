# Publishing Agent VCR to PyPI and npm

This guide covers publishing the **Python** package to PyPI and the **TypeScript** package to npm. Both can be released independently; they share the same version number for clarity.

---

## Prerequisites

- **PyPI:** [pypi.org](https://pypi.org) account. Create an API token under Account → API tokens.
- **npm:** [npmjs.com](https://www.npmjs.com) account. Create an access token (Automation or Publish) under Access Tokens.
- **Version:** Bump version in both places before publishing (see below).

---

## 1. Publish Python package to PyPI

### One-time setup

- Install tools: `pip install build twine`
- PyPI token: create at pypi.org → Account → API tokens. Use as `TWINE_PASSWORD` (username: `__token__`).

### Release steps

From the **repository root**:

```bash
cd python

# 1. Bump version in pyproject.toml (e.g. 0.1.0 → 0.1.1)
# 2. Optional: update CHANGELOG.md

# 3. Build
python -m build

# 4. Check artifacts
twine check dist/*

# 5. Upload (first time or test: use --repository testpypi and TWINE_REPOSITORY_URL=https://test.pypi.org/legacy/)
twine upload dist/*
```

When prompted, use username `__token__` and password = your PyPI API token. Or set env vars:

```bash
export TWINE_USERNAME=__token__
export TWINE_PASSWORD=pypi-YourTokenHere
twine upload dist/*
```

After a successful upload, users can install with:

```bash
pip install agent-vcr
```

---

## 2. Publish TypeScript package to npm

### One-time setup

- npm account and login: `npm login` (or set `NPM_TOKEN` for CI).
- Scoped package `@agent-vcr/core` requires **public** access for free orgs.

### Release steps

From the **repository root**:

```bash
cd typescript

# 1. Bump version in package.json (e.g. "0.1.0" → "0.1.1")
# 2. Optional: update CHANGELOG.md

# 3. Build (prepublishOnly runs this automatically, but good to verify)
npm run build

# 4. See what will be published
npm pack --dry-run

# 5. Publish (scoped package → --access public)
npm publish --access public
```

After a successful publish, users can install with:

```bash
npm install @agent-vcr/core
```

---

## 3. Releasing both (same version)

1. Bump version in **both** `python/pyproject.toml` and `typescript/package.json`.
2. Update **CHANGELOG.md** (move items from [Unreleased] to a new version section).
3. Commit: `git commit -am "chore: release v0.1.1"`.
4. Tag: `git tag v0.1.1`.
5. Push branch and tag: `git push origin main && git push origin v0.1.1`.
6. If using GitHub Actions (see below), workflows will publish on tag push. Otherwise run the PyPI and npm steps above manually.

---

## 4. GitHub Actions (optional)

Workflows are provided to publish on **tag push** (e.g. `v0.1.0`):

- **Python → PyPI:** `.github/workflows/publish-python.yml`  
  - Requires secret: `PYPI_API_TOKEN` (PyPI API token).
- **TypeScript → npm:** `.github/workflows/publish-npm.yml`  
  - Requires secret: `NPM_TOKEN` (npm access token).

Add the secrets in the repo: **Settings → Secrets and variables → Actions**, then push a version tag to trigger the run.

---

## 5. Checklist before first publish

- [ ] Tests pass: `cd python && uv run pytest tests/ -v` and `cd typescript && npm run build && npm test`
- [ ] Version bumped in `python/pyproject.toml` and `typescript/package.json`
- [ ] CHANGELOG.md updated
- [ ] No secrets or local paths in the built artifacts
