# GitHub Secrets Configuration

This document describes all required GitHub Secrets for the CI/CD pipeline.

## Required Secrets

### 1. ALWAYSDATA_SSH_KEY

**Purpose**: SSH private key for deploying to AlwaysData server

**How to generate**:
```bash
# On your local machine, generate a new SSH key pair
ssh-keygen -t ed25519 -C "github-actions-deploy" -f ~/.ssh/alwaysdata_deploy_key

# This creates:
# - ~/.ssh/alwaysdata_deploy_key (private key)
# - ~/.ssh/alwaysdata_deploy_key.pub (public key)
```

**Setup**:
1. **Add public key to AlwaysData**:
   ```bash
   # Copy the public key
   cat ~/.ssh/alwaysdata_deploy_key.pub

   # Then:
   # - SSH to AlwaysData: ssh y-b@ssh-y-b.alwaysdata.net
   # - Add the public key to ~/.ssh/authorized_keys
   ```

2. **Add private key to GitHub**:
   - Go to: Repository → Settings → Secrets and variables → Actions
   - Click "New repository secret"
   - Name: `ALWAYSDATA_SSH_KEY`
   - Value: Paste the entire content of the private key file
   ```bash
   cat ~/.ssh/alwaysdata_deploy_key
   ```

**Security Notes**:
- Never commit the private key to Git
- Use a dedicated key for CI/CD (not your personal SSH key)
- Rotate the key every 6-12 months
- Limit key permissions on AlwaysData (read/write to deployment directory only)

---

### 2. ALWAYSDATA_USER

**Purpose**: Username for SSH connection to AlwaysData

**Value**: `y-b`

**Setup**:
- Go to: Repository → Settings → Secrets and variables → Actions
- Click "New repository secret"
- Name: `ALWAYSDATA_USER`
- Value: `y-b`

---

### 3. ALWAYSDATA_HOST

**Purpose**: Hostname for SSH connection to AlwaysData

**Value**: `ssh-y-b.alwaysdata.net`

**Setup**:
- Go to: Repository → Settings → Secrets and variables → Actions
- Click "New repository secret"
- Name: `ALWAYSDATA_HOST`
- Value: `ssh-y-b.alwaysdata.net`

---

### 4. DATABASE_PASSWORD (Optional)

**Purpose**: PostgreSQL database password for production

**Value**: Your production database password

**Setup**:
- Go to: Repository → Settings → Secrets and variables → Actions
- Click "New repository secret"
- Name: `DATABASE_PASSWORD`
- Value: Your database password from AlwaysData

**Note**: This is optional if your DATABASE_URL is already in the server's `.env` file.

---

### 5. SECRET_KEY_PRODUCTION

**Purpose**: JWT secret key for production environment

**How to generate**:
```bash
# Generate a secure random key
python3 -c "import secrets; print(secrets.token_urlsafe(32))"
```

**Setup**:
- Go to: Repository → Settings → Secrets and variables → Actions
- Click "New repository secret"
- Name: `SECRET_KEY_PRODUCTION`
- Value: The generated secret key

**Security Notes**:
- NEVER use the same secret key as development
- Rotate this key every 3-6 months
- When rotating, plan a maintenance window (all users will need to re-login)

---

## Environment Setup (Optional)

You can create environment-specific secrets by using GitHub Environments:

### Create Production Environment:
1. Go to: Repository → Settings → Environments
2. Click "New environment"
3. Name: `production`
4. Add protection rules:
   - ✅ Required reviewers (select team members)
   - ✅ Wait timer: 0 minutes
   - ✅ Deployment branches: Only `main`

### Create Staging Environment:
1. Go to: Repository → Settings → Environments
2. Click "New environment"
3. Name: `staging`
4. Add the same secrets but with staging values

---

## Verification

After setting up all secrets, verify they're configured correctly:

1. Go to: Repository → Settings → Secrets and variables → Actions
2. You should see:
   - `ALWAYSDATA_SSH_KEY` (Updated X days ago)
   - `ALWAYSDATA_USER` (Updated X days ago)
   - `ALWAYSDATA_HOST` (Updated X days ago)
   - `SECRET_KEY_PRODUCTION` (Updated X days ago)

3. Test the deployment:
   ```bash
   # Trigger manual deployment
   # Go to Actions → Deploy to Production → Run workflow
   ```

---

## Troubleshooting

### SSH Connection Fails

**Error**: `Permission denied (publickey)`

**Solution**:
1. Verify the public key is in AlwaysData's `~/.ssh/authorized_keys`
2. Check the private key in GitHub Secrets (no extra whitespace)
3. Ensure the key format is correct (starts with `-----BEGIN OPENSSH PRIVATE KEY-----`)

### Deployment Fails

**Error**: `Host key verification failed`

**Solution**:
- The GitHub runner couldn't verify the AlwaysData host
- This is handled by the workflow (ssh-keyscan)
- If it persists, check if AlwaysData changed their SSH host key

### Health Check Fails

**Error**: Health check times out after deployment

**Solution**:
1. SSH to server manually: `ssh y-b@ssh-y-b.alwaysdata.net`
2. Check application logs: `tail -f /home/y-b/trainings-backoffice/logs/error.log`
3. Verify supervisor status: `supervisorctl status trainings-backoffice`

---

## Security Best Practices

1. **Principle of Least Privilege**:
   - Only grant necessary permissions
   - Use separate keys for different purposes

2. **Regular Rotation**:
   - Rotate SSH keys: Every 6-12 months
   - Rotate SECRET_KEY: Every 3-6 months
   - Rotate database passwords: Every 6 months

3. **Audit Access**:
   - Review who has access to secrets
   - Check GitHub Actions logs regularly
   - Monitor failed deployment attempts

4. **Backup**:
   - Keep secure backup of SSH keys
   - Document secret rotation procedures
   - Have rollback plan ready

---

## Emergency Procedures

### If SSH Key is Compromised:

1. **Immediately**:
   - Remove the public key from AlwaysData `~/.ssh/authorized_keys`
   - Delete the secret from GitHub

2. **Then**:
   - Generate new SSH key pair
   - Add new public key to AlwaysData
   - Update GitHub Secret with new private key
   - Test deployment

### If SECRET_KEY is Leaked:

1. **Immediately**:
   - Generate new SECRET_KEY
   - Update GitHub Secret
   - Deploy new key to production
   - All users will need to re-login

2. **Then**:
   - Investigate how the leak occurred
   - Review access logs
   - Consider enabling 2FA for all users

---

## Support

For issues with secrets configuration:
1. Check this documentation first
2. Review [DEPLOYMENT.md](../DEPLOYMENT.md) for deployment procedures
3. Contact DevOps team
4. Create GitHub issue with [SECURITY] tag (for non-sensitive issues only)

**Last Updated**: 2025-11-19
