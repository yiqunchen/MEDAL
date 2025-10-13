# Security Guidelines for MEDAL Repository

## Critical Security Practices

### 1. API Key Management

**NEVER commit API keys to version control!**

- All API keys must be stored in `.env` file (already gitignored)
- Use `ENV.sample` as a template, then copy to `.env` and fill in your keys
- Never hardcode API keys in Python scripts, notebooks, or shell scripts
- Always use environment variables: `os.getenv("API_KEY_NAME")`

### 2. Files That Must Stay Private

The following patterns are automatically ignored by `.gitignore`:

```
.env
.env.local
.env.*.local
*.pem
*.key
*_credentials.json
credentials/
secrets/
.claude/settings.local.json
```

### 3. Checking for Exposed Keys

Before committing any changes, run:

```bash
# Check current files for potential API keys
grep -r "sk-proj-" . --include="*.py" --include="*.sh" --include="*.md"
grep -r "sk-or-v1-" . --include="*.py" --include="*.sh" --include="*.md"
grep -r "sk-ant-" . --include="*.py" --include="*.sh" --include="*.md"
```

If any matches are found (excluding ENV.sample placeholders), they need to be redacted!

### 4. Git History Cleanup (If Keys Were Already Committed)

If API keys were previously committed to git history, they must be removed:

#### Option A: Using git-filter-repo (Recommended)

```bash
# Install git-filter-repo
pip install git-filter-repo

# Create a backup first!
cp -r ../MEDAL ../MEDAL-backup

# Remove specific strings from history
git filter-repo --invert-paths --path-regex '.*\.env$' --force
git filter-repo --replace-text <(echo 'sk-proj-EXPOSED_KEY_HERE==>REDACTED')
git filter-repo --replace-text <(echo 'sk-or-v1-EXPOSED_KEY_HERE==>REDACTED')

# Force push to remote (WARNING: This rewrites history!)
git push origin --force --all
git push origin --force --tags
```

#### Option B: Using BFG Repo-Cleaner

```bash
# Install BFG
brew install bfg  # macOS
# or download from: https://rtyley.github.io/bfg-repo-cleaner/

# Create a backup first!
cp -r ../MEDAL ../MEDAL-backup

# Remove passwords from history
echo 'sk-proj-EXPOSED_KEY_HERE' > passwords.txt
echo 'sk-or-v1-EXPOSED_KEY_HERE' >> passwords.txt
bfg --replace-text passwords.txt ../MEDAL

cd ../MEDAL
git reflog expire --expire=now --all && git gc --prune=now --aggressive

# Force push (WARNING: This rewrites history!)
git push origin --force --all
git push origin --force --tags
```

#### Important Notes After History Rewrite:

1. **Notify all collaborators** that history has been rewritten
2. All collaborators must:
   ```bash
   git fetch origin
   git reset --hard origin/main
   ```
3. **Revoke and regenerate ALL exposed API keys** from their respective platforms:
   - OpenAI: https://platform.openai.com/api-keys
   - OpenRouter: https://openrouter.ai/keys
   - Anthropic: https://console.anthropic.com/settings/keys

### 5. Best Practices

1. **Always use environment variables**:
   ```python
   import os
   api_key = os.getenv("OPENAI_API_KEY")
   if not api_key:
       raise ValueError("OPENAI_API_KEY not set in environment")
   ```

2. **Never log API keys**:
   ```python
   # BAD
   print(f"Using API key: {api_key}")

   # GOOD
   print("API key loaded successfully")
   ```

3. **Use .env files**:
   ```bash
   # In your .env file
   OPENAI_API_KEY=sk-proj-your-key-here
   OPENROUTER_API_KEY=sk-or-v1-your-key-here
   ```

4. **Load .env in scripts**:
   ```python
   from dotenv import load_dotenv
   load_dotenv()  # Loads .env file
   api_key = os.getenv("OPENAI_API_KEY")
   ```

### 6. Pre-commit Hook (Optional but Recommended)

Create `.git/hooks/pre-commit`:

```bash
#!/bin/bash
# Pre-commit hook to check for API keys

echo "Checking for potential API keys..."

# Check for common API key patterns
if git diff --cached --name-only | xargs grep -E "sk-(proj|or-v1|ant)-[A-Za-z0-9_-]{20,}" 2>/dev/null; then
    echo "ERROR: Potential API key found in staged files!"
    echo "Please remove API keys before committing."
    exit 1
fi

echo "No API keys detected. Proceeding with commit."
exit 0
```

Make it executable:
```bash
chmod +x .git/hooks/pre-commit
```

## Reporting Security Issues

If you discover a security vulnerability, please:

1. **DO NOT** create a public GitHub issue
2. Contact the repository maintainer directly
3. Include details about the vulnerability and steps to reproduce

## Additional Resources

- [GitHub: Removing sensitive data from a repository](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/removing-sensitive-data-from-a-repository)
- [BFG Repo-Cleaner](https://rtyley.github.io/bfg-repo-cleaner/)
- [git-filter-repo](https://github.com/newren/git-filter-repo)
