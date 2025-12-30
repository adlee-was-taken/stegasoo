# CI/CD Primer for Stegasoo

## What is CI/CD?

**CI** = Continuous Integration
**CD** = Continuous Deployment

Think of it as a robot assistant that automatically:
1. **Tests your code** every time you push
2. **Checks formatting** so code stays consistent
3. **Publishes releases** when you tag a version

```
You push code → GitHub runs workflows → You get ✓ or ✗
```

---

## How It Works

### The Trigger

When you `git push` or create a Pull Request, GitHub looks for workflow files in:
```
.github/workflows/*.yml
```

Each `.yml` file defines a workflow - a series of steps to run.

### The Runners

GitHub provides free Linux/Mac/Windows VMs that:
1. Clone your repo
2. Set up Python
3. Run your commands
4. Report success/failure

You don't manage servers - GitHub does.

---

## Your Workflows

### 1. `test.yml` - Run Tests on Every Push

**When it runs:** Every push, every PR

**What it does:**
```
1. Spins up Ubuntu VM
2. Installs Python 3.10, 3.11, 3.12
3. Installs your package + dependencies
4. Runs pytest
5. Reports pass/fail
```

**You'll see:** Green ✓ or red ✗ on your commits

### 2. `lint.yml` - Check Code Style

**When it runs:** Every push, every PR

**What it does:**
```
1. Runs ruff (fast Python linter)
2. Checks black formatting
3. Fails if code isn't formatted
```

**Why:** Keeps code consistent, catches common bugs

### 3. `release.yml` - Publish to PyPI

**When it runs:** Only when you create a version tag

**What it does:**
```
1. Builds the package (wheel + sdist)
2. Uploads to PyPI
```

**You trigger it by:**
```bash
git tag v2.2.0
git push origin v2.2.0
```

---

## Day-to-Day Usage

### Normal Development

```bash
# Make changes
git add .
git commit -m "Add new feature"
git push
```

Then check GitHub → Actions tab → See if tests pass.

### If Tests Fail

1. Click the failed workflow
2. Click the failed job
3. Read the error log
4. Fix locally, push again

### Making a Release

```bash
# 1. Update version in pyproject.toml and constants.py
# 2. Commit the version bump
git add .
git commit -m "Bump version to 2.2.1"
git push

# 3. Create and push a tag
git tag v2.2.1
git push origin v2.2.1

# 4. GitHub automatically publishes to PyPI
```

---

## Reading the GitHub UI

### Actions Tab

```
Repository → Actions → [List of workflow runs]
```

Each run shows:
- ✓ Green checkmark = passed
- ✗ Red X = failed
- 🟡 Yellow dot = running

### Pull Request Checks

When you open a PR, you'll see:
```
┌─────────────────────────────────────────┐
│ All checks have passed                  │
│ ✓ test (3.10) — 45s                     │
│ ✓ test (3.11) — 42s                     │
│ ✓ test (3.12) — 44s                     │
│ ✓ lint — 12s                            │
└─────────────────────────────────────────┘
```

---

## Setting Up PyPI Publishing

For `release.yml` to work, you need to add a PyPI API token:

### One-Time Setup

1. **Create PyPI account** at https://pypi.org/account/register/

2. **Generate API token:**
   - PyPI → Account Settings → API tokens
   - Create token (scope: entire account or just stegasoo)
   - Copy the token (starts with `pypi-`)

3. **Add to GitHub:**
   - GitHub repo → Settings → Secrets and variables → Actions
   - New repository secret
   - Name: `PYPI_API_TOKEN`
   - Value: paste the token

Now `release.yml` can publish automatically.

---

## Common Scenarios

### "Tests pass locally but fail in CI"

Usually means:
- Missing dependency in `pyproject.toml`
- Hardcoded path that doesn't exist in CI
- Test relies on local file

### "Lint is failing"

Run locally to see/fix:
```bash
# Check issues
ruff check src/

# Auto-fix what's possible
ruff check --fix src/

# Format code
black src/
```

### "I want to skip CI for a commit"

Add `[skip ci]` to commit message:
```bash
git commit -m "Update README [skip ci]"
```

---

## Costs

GitHub Actions is **free** for public repos.

For private repos: 2,000 minutes/month free, then paid.

---

## Summary

| Action | What Happens |
|--------|--------------|
| `git push` | Tests + lint run automatically |
| Open PR | Tests must pass before merge |
| `git tag v*` | Publishes to PyPI |
| Check results | GitHub → Actions tab |

That's it! Push code, check for green checkmarks.
