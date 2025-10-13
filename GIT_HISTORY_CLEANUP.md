# Git History Cleanup Required

## WARNING: API Keys Were Found in Git History

During security audit on 2025-10-13, we discovered that API keys were committed to the git history in the following commits:

### Affected Commits:
- **c0f5b9e286625666790d1946d1477c8972b3361e** - "get updated structure"
  - File: `archive/notebooks/negate-gpt4-data.ipynb`
  - Contains: OpenAI API key (`sk-proj-...`)

### Exposed Keys Summary:
1. **OpenAI API Key** (sk-proj-...) - Found in notebooks committed on 2025-09-07
2. **Entrez API Key** - Found in notebooks
3. **OpenRouter API Key** (sk-or-v1-...) - In uncommitted files (now removed)

## Actions Taken:

### 1. Current Repository State (Secured)
- ✅ All API keys removed from tracked files
- ✅ Keys replaced with `REDACTED` placeholders in archived files
- ✅ `.gitignore` updated with comprehensive security patterns
- ✅ `ENV.sample` created with proper key templates
- ✅ `SECURITY.md` documentation created
- ✅ Scripts updated to use environment variables only

### 2. Files Modified (ready to commit):
- `.gitignore` - Enhanced with security patterns
- `ENV.sample` - Updated with all required keys
- `scripts/run_openrouter_evals.sh` - Removed hardcoded keys
- `archive/` files - API keys redacted
- `README.md` - Complete security documentation
- New: `SECURITY.md` - Comprehensive security guide
- New: `run_complete_medal_pipeline.sh` - Reproducible pipeline

## CRITICAL: Git History Must Be Cleaned

The API keys in git history are still accessible and must be cleaned. Choose one method:

### Method 1: git-filter-repo (Recommended)

```bash
# 1. Create backup
cp -r ../MEDAL ../MEDAL-backup

# 2. Install git-filter-repo
pip install git-filter-repo

# 3. Create replacement file with actual exposed keys
cat > /tmp/api-keys-to-remove.txt <<'EOF'
***OPENAI_API_KEY_REDACTED***==>OPENAI_API_KEY_REDACTED
***OPENAI_API_KEY_REDACTED***==>OPENAI_API_KEY_REDACTED
***OPENROUTER_API_KEY_REDACTED***==>OPENROUTER_API_KEY_REDACTED
***ENTREZ_API_KEY_REDACTED***==>ENTREZ_API_KEY_REDACTED
EOF

# 4. Run filter-repo
git filter-repo --replace-text /tmp/api-keys-to-remove.txt --force

# 5. Clean up
rm /tmp/api-keys-to-remove.txt
git reflog expire --expire=now --all
git gc --prune=now --aggressive

# 6. Force push (WARNING: Rewrites history!)
git push origin --force --all
git push origin --force --tags
```

### Method 2: BFG Repo-Cleaner

```bash
# 1. Create backup
cp -r ../MEDAL ../MEDAL-backup

# 2. Install BFG (macOS)
brew install bfg

# 3. Create password file with exposed keys
cat > /tmp/passwords.txt <<'EOF'
***OPENAI_API_KEY_REDACTED***
***OPENAI_API_KEY_REDACTED***
***OPENROUTER_API_KEY_REDACTED***
***ENTREZ_API_KEY_REDACTED***
EOF

# 4. Run BFG
cd ..
bfg --replace-text /tmp/passwords.txt MEDAL

# 5. Clean up
cd MEDAL
rm /tmp/passwords.txt
git reflog expire --expire=now --all
git gc --prune=now --aggressive

# 6. Force push (WARNING: Rewrites history!)
git push origin --force --all
git push origin --force --tags
```

## CRITICAL: After History Cleanup

### 1. Revoke ALL Exposed API Keys Immediately

**OpenAI Keys:**
- Go to: https://platform.openai.com/api-keys
- Revoke the exposed keys
- Generate new keys and update your `.env` file

**OpenRouter Keys:**
- Go to: https://openrouter.ai/keys
- Revoke the exposed keys
- Generate new keys and update your `.env` file

**Entrez Keys:**
- Visit: https://www.ncbi.nlm.nih.gov/account/settings/
- Generate new API key

### 2. Notify All Collaborators

Send this message to all team members:

```
URGENT: Git history has been rewritten to remove exposed API keys.

Action required:
1. Backup your local work
2. Run these commands:
   cd MEDAL
   git fetch origin
   git reset --hard origin/main
3. DO NOT push any branches created before this cleanup
4. Update your .env file with new API keys
```

### 3. Verify Cleanup

After force-push, verify keys are gone:

```bash
# Clone fresh copy
cd /tmp
git clone <repo-url> MEDAL-verify
cd MEDAL-verify

# Search for any remaining keys
git log -p -S "sk-proj-" --all
git log -p -S "sk-or-v1-" --all

# Should return no results
```

## Prevention Going Forward

1. **Pre-commit hook** - Install from SECURITY.md
2. **Regular audits** - Run security scans before major releases
3. **Environment variables only** - Never hardcode credentials
4. **Code reviews** - Check for accidental key exposure
5. **Rotate keys** - Regularly rotate API keys

## Timeline

- **2025-10-13**: API keys discovered in git history
- **2025-10-13**: Current working tree secured and cleaned
- **Next**: History cleanup required (use methods above)
- **After cleanup**: Revoke all exposed keys and notify team

## Questions?

Contact the repository maintainer for assistance with git history cleanup.
