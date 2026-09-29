# Releasing mtg-archetypes

This document outlines the release process and versioning strategy for `mtg-archetypes`.

---

## 1. Versioning Strategy (CalVer)

`mtg-archetypes` uses **[Calendar Versioning (CalVer)](https://calver.org/)** in the format:

$$\textbf{YYYY.M.PATCH}$$

For example:
* `2026.9.0` — First release in September 2026.
* `2026.9.1` — Subsequent fix or rule adjustment within September 2026.
* `2026.10.0` — First release in October 2026 (patch resets to `0`).

### PEP 440 Rule: No Leading Zeros
Under Python packaging standards ([PEP 440](https://peps.python.org/pep-0440/)), version segments cannot have leading zeros. Always use `2026.9.0`, never `2026.09.0`.

---

## 2. Pre-Release Checklist

Before cutting a release, make sure all archetype definitions, tests, and formatting pass.

### 1. Validate Archetype Rules against Scryfall
Confirm that all YAML rules are syntactically valid and all card names exist in Scryfall Oracle data:
```bash
uv run python scripts/validate_archetypes.py --check-cards
```

### 2. Run Pre-Commit Checks
Ensure ruff linting, code formatting, and yaml checkers pass:
```bash
uv run pre-commit run --all-files
```

### 3. Run Test Suite
Confirm all unit tests and offline guards pass:
```bash
uv run pytest
```

---

## 3. Release Process

### Step 1: Update Version Strings
Bump the version in **two** locations:

1. **`pyproject.toml`**:
   ```toml
   [project]
   name = "mtg-archetypes"
   version = "2026.9.0"  # <-- Update here
   ```

2. **`src/mtg_archetypes/__init__.py`**:
   ```python
   __version__ = "2026.9.0"  # <-- Update here
   ```

3. **Update Lockfile** (if dependencies changed):
   ```bash
   uv lock
   ```

### Step 2: Commit and Tag
```bash
export VERSION=YYYY.M.P  # 2026.9.0
git checkout -b release-$VERSION
git add pyproject.toml src/mtg_archetypes/__init__.py uv.lock
git commit -m "Release $VERSION"
git push origin release-$VERSION

# Create and merge PR on GitHub, then:
git checkout main
git pull origin main
git tag $VERSION
git push origin $VERSION
```

### Step 3: Create GitHub Release
1. Navigate to [GitHub releases](https://github.com/davidfischer/mtg-archetypes/releases/new).
2. Select tag `$VERSION` (e.g. `2026.9.0`).
3. Provide release notes listing updated archetype classifications or other changes.
4. Click **Publish release**.

### Step 4: Automated PyPI Publication
Publishing to PyPI is automated via GitHub Actions and **PyPI Trusted Publishing (OIDC)**:
* Creating the GitHub release triggers [`.github/workflows/release.yml`](.github/workflows/release.yml).
* The workflow builds the package artifacts (`uv build`) and publishes to PyPI (`uv publish`) using OIDC authentication.
* You can monitor the deployment progress under the repository's **Actions** tab.
