# Publishing Guide

> **Current status:** Python is ready to publish to PyPI. TypeScript has 72 unit tests, full CLI, and is ready to publish to npm. Recording mode in test integrations is not yet implemented, but the package is otherwise complete.

This guide covers how to publish Agent VCR to PyPI (Python) and npm (TypeScript).

## Publishing Strategy

Agent VCR uses a **dual-language monorepo** structure with independent releases:

- **Python**: Published to PyPI as `agent-vcr`
- **TypeScript**: Published to npm as `@agent-vcr/core`

Both packages share the same version number for clarity, but can be released independently.

## Version Management

We use **semantic versioning** (semver):

- **Major (X.0.0)**: Breaking changes to the `.vcr` format or public API
- **Minor (0.X.0)**: New features, backward-compatible
- **Patch (0.0.X)**: Bug fixes, no new features

**Important:** Since both implementations share the `.vcr` format, format-breaking changes require a major version bump for BOTH languages.

## Pre-Release Checklist

Before releasing either implementation:

- [ ] All tests pass (`pytest` for Python, `npm test` for TypeScript)
- [ ] Type checking passes (`mypy --strict` for Python, `tsc --noEmit` for TypeScript)
- [ ] Linting passes (`ruff check` for Python, `npm run lint` for TypeScript)
- [ ] Documentation is up to date (README.md, [architecture.md](architecture.md), examples)
- [ ] [CHANGELOG.md](../CHANGELOG.md) updated with release notes
- [ ] Version bumped in:
  - `python/pyproject.toml` (Python)
  - `typescript/package.json` (TypeScript)
- [ ] Cross-language compatibility tested (record with one, replay with other)

## Publishing Python to PyPI

### Setup (One-time)

```bash
# Install build tools
pip install build twine

# Configure PyPI token
# Create token at https://pypi.org/manage/account/token/
# Add to ~/.pypirc:
[pypi]
username = __token__
password = pypi-AgEIcHlwaS5vcmc...
```

### Release Steps

```bash
cd python

# 1. Update version in pyproject.toml
# version = "0.2.0"

# 2. Build distribution
python -m build

# 3. Check the built package
twine check dist/*

# 4. Upload to Test PyPI first (recommended)
twine upload --repository testpypi dist/*

# 5. Test installation from Test PyPI
pip install --index-url https://test.pypi.org/simple/ agent-vcr

# 6. If all looks good, upload to real PyPI
twine upload dist/*

# 7. Verify on PyPI
# Visit https://pypi.org/project/agent-vcr/

# 8. Test installation
pip install agent-vcr
agent-vcr --version

# 9. Create git tag
git tag -a python-v0.2.0 -m "Python v0.2.0"
git push origin python-v0.2.0
```

### Automated Publishing (GitHub Actions)

Create `.github/workflows/publish-python.yml`:

```yaml
name: Publish Python Package

on:
  push:
    tags:
      - 'python-v*'

jobs:
  publish:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.10'
      - name: Install dependencies
        run: |
          pip install build twine
      - name: Build package
        run: |
          cd python
          python -m build
      - name: Publish to PyPI
        env:
          TWINE_USERNAME: __token__
          TWINE_PASSWORD: ${{ secrets.PYPI_TOKEN }}
        run: |
          cd python
          twine upload dist/*
```

## Publishing TypeScript to npm

### Setup (One-time)

```bash
# Login to npm
npm login

# Or use token (for CI)
npm config set //registry.npmjs.org/:_authToken YOUR_TOKEN
```

### Release Steps

```bash
cd typescript

# 1. Update version in package.json
# "version": "0.2.0"

# 2. Run all checks
npm run typecheck
npm run lint
npm test
npm run build

# 3. Check what will be published
npm pack --dry-run

# 4. Publish to npm (with 2FA if enabled)
npm publish --access public

# If you have 2FA, you'll be prompted for your code

# 5. Verify on npm
# Visit https://www.npmjs.com/package/@agent-vcr/core

# 6. Test installation
npm install @agent-vcr/core
npx agent-vcr --version

# 7. Create git tag
git tag -a typescript-v0.2.0 -m "TypeScript v0.2.0"
git push origin typescript-v0.2.0
```

### Automated Publishing (GitHub Actions)

Create `.github/workflows/publish-typescript.yml`:

```yaml
name: Publish TypeScript Package

on:
  push:
    tags:
      - 'typescript-v*'

jobs:
  publish:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: '18'
          registry-url: 'https://registry.npmjs.org'
      - name: Install dependencies
        run: |
          cd typescript
          npm ci
      - name: Build
        run: |
          cd typescript
          npm run build
      - name: Publish to npm
        run: |
          cd typescript
          npm publish --access public
        env:
          NODE_AUTH_TOKEN: ${{ secrets.NPM_TOKEN }}
```

## Release Workflow

### For a Minor/Patch Release (Backward-Compatible)

1. **Choose which implementation to release**
   - Can release Python and TypeScript independently
   - Only update the package that has changes

2. **Update version number**
   - Python: `python/pyproject.toml`
   - TypeScript: `typescript/package.json`

3. **Update [CHANGELOG.md](../CHANGELOG.md)**
   - Document new features, bug fixes, breaking changes
   - Separate sections for Python and TypeScript if needed

4. **Run tests and checks**
   ```bash
   # Python
   cd python && pytest && mypy --strict src/

   # TypeScript
   cd typescript && npm test && npm run typecheck
   ```

5. **Test cross-language compatibility**
   ```bash
   # Record with Python
   cd python
   agent-vcr record --server-command "node ../../demo/servers/calculator_v1.js" -o test.vcr

   # Replay with TypeScript
   cd ../typescript
   npx agent-vcr replay -i ../python/test.vcr
   ```

6. **Publish**
   - Follow platform-specific steps above
   - Create git tags

7. **Announce**
   - GitHub Releases (one per language)
   - Update main [README.md](../README.md) if needed

### For a Major Release (Breaking Changes)

1. **Update BOTH implementations**
   - Even if only one has breaking changes, bump both major versions
   - Keep format compatibility in sync

2. **Migration guide**
   - Document what changed and how to upgrade
   - Provide before/after examples

3. **Deprecation period** (if possible)
   - Warn users in v0.X.0 release notes
   - Remove deprecated features in v(X+1).0.0

## Post-Release

After publishing:

1. **Verify installations**
   ```bash
   # Python
   pip install --upgrade agent-vcr
   agent-vcr --version

   # TypeScript
   npm install @agent-vcr/core@latest
   npx agent-vcr --version
   ```

2. **Update documentation**
   - Ensure README badges show correct version
   - Update any version-specific documentation

3. **Monitor for issues**
   - Watch GitHub issues for bug reports
   - Check npm/PyPI download stats

4. **Announce on social media / community channels**
   - MCP community Discord
   - Twitter/X
   - Relevant forums

## Rollback Procedure

If a release has critical bugs:

### Python (PyPI)

PyPI does not allow deleting packages, but you can:

```bash
# Yank the broken version (hides it but allows existing installs)
twine yank agent-vcr --version 0.2.0 --reason "Critical bug in X"

# Publish a patch release immediately
# Bump to 0.2.1 with fix, follow release steps
```

### TypeScript (npm)

```bash
# Deprecate the broken version
npm deprecate @agent-vcr/core@0.2.0 "Critical bug, use 0.2.1+"

# Publish a patch release
# Bump to 0.2.1 with fix, follow release steps
```

## Security Updates

For security-sensitive releases:

1. **Do NOT pre-announce** the vulnerability
2. **Prepare fix in private** (use a private branch)
3. **Test thoroughly**
4. **Publish both languages simultaneously** if the issue affects the format
5. **Coordinate disclosure** with security mailing lists
6. **File CVE** if applicable

## Questions?

If you're unsure about any release step:

- Check with project maintainers
- Review previous release PRs
- Test on Test PyPI / npm first
- When in doubt, don't publish — better to delay than to ship broken code
