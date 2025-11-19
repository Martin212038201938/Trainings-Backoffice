# Branch Protection Configuration

This document provides recommended branch protection rules for the Trainings-Backoffice repository.

## Overview

Branch protection rules help maintain code quality and prevent accidental changes to important branches.

## Recommended Configuration

### Main Branch (`main`)

The main branch should have the strictest protection rules as it represents production code.

#### Required Settings:

1. **Require a pull request before merging** ✅
   - Required approvals: **1** (minimum)
   - Recommended approvals: **2** (for production)
   - Dismiss stale pull request approvals when new commits are pushed ✅
   - Require review from Code Owners (optional, if CODEOWNERS file exists)

2. **Require status checks to pass before merging** ✅
   - Require branches to be up to date before merging ✅
   - Required status checks:
     - `lint` (Lint & Format Check)
     - `test / Test (Python 3.11)` (Unit Tests)
     - `test / Test (Python 3.12)` (Unit Tests)
     - `integration-tests` (Integration Tests)
     - `security-check` (Security Scan)
     - `build-check` (Build Check)
     - `status-check` (All Tests Passed)

3. **Require conversation resolution before merging** ✅
   - All conversations must be resolved before merge

4. **Require signed commits** (Recommended) ⚠️
   - All commits must be signed with GPG key
   - Helps verify commit authenticity

5. **Require linear history** (Optional) ⭐
   - Prevents merge commits
   - Enforces rebase or squash merging
   - Keeps Git history clean

6. **Include administrators** ✅
   - Rules apply to administrators too
   - No one can bypass protection rules

7. **Restrict pushes** ✅
   - No direct pushes to main
   - Only allow pushes via pull requests

8. **Allow force pushes** ❌
   - Disabled (never allow force push to main)

9. **Allow deletions** ❌
   - Disabled (prevent accidental branch deletion)

---

### Develop Branch (`develop`) (Optional)

If you use a develop branch for pre-production testing:

#### Recommended Settings:

1. **Require a pull request before merging** ✅
   - Required approvals: **1**
   - Dismiss stale reviews: ✅

2. **Require status checks to pass** ✅
   - Same checks as main branch
   - Don't require branch to be up to date (more flexible)

3. **Allow force pushes** ❌
   - Disabled for stability

4. **Include administrators** ✅

---

### Feature Branches (`feature/*`, `bugfix/*`, etc.)

Feature branches typically don't need protection rules, but you can add:

#### Optional Settings:

1. **Require status checks to pass** ✅
   - Run tests on all branches
   - No approval required

2. **Allow force pushes** ✅
   - Developers can rewrite their feature branch history

---

## Implementation Steps

### 1. Via GitHub Web Interface

1. Go to: **Repository → Settings → Branches**

2. Click "**Add rule**" or "**Add classic branch protection rule**"

3. **Branch name pattern**: `main`

4. Configure settings as described above

5. Click "**Create**" or "**Save changes**"

6. Repeat for other branches (develop, etc.)

### 2. Via GitHub API (Automated)

```bash
# Set branch protection for main
curl -X PUT \
  -H "Accept: application/vnd.github+json" \
  -H "Authorization: Bearer YOUR_GITHUB_TOKEN" \
  https://api.github.com/repos/Martin212038201938/Trainings-Backoffice/branches/main/protection \
  -d '{
    "required_status_checks": {
      "strict": true,
      "contexts": [
        "lint",
        "test / Test (Python 3.11)",
        "test / Test (Python 3.12)",
        "integration-tests",
        "security-check",
        "build-check",
        "status-check"
      ]
    },
    "enforce_admins": true,
    "required_pull_request_reviews": {
      "required_approving_review_count": 1,
      "dismiss_stale_reviews": true
    },
    "restrictions": null,
    "allow_force_pushes": false,
    "allow_deletions": false,
    "required_conversation_resolution": true
  }'
```

---

## CODEOWNERS File (Optional)

Create `.github/CODEOWNERS` to automatically request reviews from specific people:

```
# Backend code
/backend/**/*.py @your-team/backend-team

# CI/CD workflows
/.github/workflows/** @your-team/devops-team

# Documentation
*.md @your-team/docs-team

# Security-related files
/backend/app/core/security.py @your-team/security-team
/backend/app/core/deps.py @your-team/security-team

# Database migrations
/backend/alembic/** @your-team/database-team
```

---

## Workflow Integration

### How Protection Rules Work with CI/CD:

1. **Developer creates feature branch**:
   ```bash
   git checkout -b feature/new-feature
   # Make changes
   git push origin feature/new-feature
   ```

2. **Tests run automatically** (via `.github/workflows/test.yml`):
   - Lint checks
   - Unit tests
   - Integration tests
   - Security scans

3. **Developer opens Pull Request** to `main`:
   - GitHub requires all status checks to pass
   - At least 1 approval required
   - All conversations must be resolved

4. **After approval and passing checks**:
   - Developer can merge PR
   - Deployment workflow triggers automatically

5. **Production deployment** (via `.github/workflows/deploy.yml`):
   - Code is deployed to AlwaysData
   - Health checks verify deployment
   - Rollback on failure

---

## Best Practices

### For Developers:

1. **Always create feature branches**:
   ```bash
   git checkout -b feature/my-feature
   ```

2. **Keep branches up to date**:
   ```bash
   git fetch origin main
   git rebase origin/main
   ```

3. **Write good commit messages**:
   ```
   Add user authentication endpoints

   - Implement JWT token generation
   - Add login and registration routes
   - Add role-based access control tests
   ```

4. **Request reviews early**:
   - Open draft PR for early feedback
   - Convert to ready when tests pass

5. **Respond to review comments**:
   - Address all feedback
   - Mark conversations as resolved

### For Reviewers:

1. **Review checklist**:
   - [ ] Code follows project style
   - [ ] Tests are comprehensive
   - [ ] No security vulnerabilities
   - [ ] Documentation is updated
   - [ ] No breaking changes (or properly documented)

2. **Use GitHub review features**:
   - Comment on specific lines
   - Request changes if needed
   - Approve when satisfied

3. **Don't rubber-stamp**:
   - Actually review the code
   - Test locally if needed
   - Ask questions

---

## Emergency Procedures

### Hotfix to Production:

If you need to deploy urgent fixes to production:

1. **Create hotfix branch from main**:
   ```bash
   git checkout main
   git pull origin main
   git checkout -b hotfix/urgent-fix
   ```

2. **Make minimal changes**:
   - Fix only the critical issue
   - Don't add new features

3. **Open PR with [HOTFIX] label**:
   - Requires only 1 approval
   - Can expedite review process

4. **After merge**:
   - Deployment happens automatically
   - Monitor closely

### Bypassing Protection (Emergency Only):

If absolutely necessary, administrators can:

1. Temporarily disable protection rules
2. Make emergency changes
3. Re-enable protection rules immediately

**⚠️ WARNING**: Only do this in extreme emergencies!

---

## Monitoring and Maintenance

### Weekly:

- [ ] Review open pull requests
- [ ] Check for stale branches
- [ ] Verify CI/CD pipelines are running

### Monthly:

- [ ] Review branch protection effectiveness
- [ ] Update required status checks if needed
- [ ] Clean up merged branches

### Quarterly:

- [ ] Review and update CODEOWNERS
- [ ] Audit who has admin access
- [ ] Update this documentation

---

## Examples

### Good PR Workflow:

```bash
# 1. Create feature branch
git checkout -b feature/add-export-feature

# 2. Make changes and commit
git add .
git commit -m "Add CSV export for trainings"

# 3. Push and create PR
git push origin feature/add-export-feature
# Open PR on GitHub

# 4. Address review comments
git add .
git commit -m "Address review feedback"
git push

# 5. Merge after approval
# GitHub automatically runs deployment
```

### Handling Merge Conflicts:

```bash
# 1. Fetch latest main
git fetch origin main

# 2. Rebase on main
git rebase origin/main

# 3. Resolve conflicts
# Edit files, then:
git add <conflicted-files>
git rebase --continue

# 4. Force push (only to feature branch!)
git push --force-with-lease origin feature/my-feature
```

---

## FAQ

**Q: Why can't I push directly to main?**
A: Direct pushes are disabled to ensure all code is reviewed and tested.

**Q: How do I bypass protection rules?**
A: You shouldn't. If you absolutely must, contact an administrator.

**Q: Can I merge my own PR?**
A: Not if you're the only reviewer. At least one other person must approve.

**Q: What if CI/CD is failing incorrectly?**
A: Fix the CI/CD issue first. Don't bypass checks.

**Q: How long do PRs typically take?**
A: Small PRs: 1-4 hours. Large PRs: 1-2 days. Plan accordingly.

---

## Resources

- [GitHub Branch Protection Documentation](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches)
- [GitHub Actions Documentation](https://docs.github.com/en/actions)
- [CODEOWNERS Documentation](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/about-code-owners)

---

**Last Updated**: 2025-11-19
**Reviewed By**: DevOps Team
