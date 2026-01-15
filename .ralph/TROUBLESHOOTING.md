# Troubleshooting Ralph

## Agent Permission Issues

### Claude Code: "Cannot write files" or permission errors

**Problem:** Claude Code may run in restricted mode by default, preventing file writes.

**Solutions:**

1. **Use the correct Claude Code flags:**

   ```toml
   [runners.claude]
   argv = ["claude", "-p", "--allow-write", "--output-format", "text"]
   ```

2. **Or use full-auto mode if available:**

   ```toml
   [runners.claude]
   argv = ["claude", "exec", "--full-auto"]
   ```

3. **Check Claude Code session permissions:**

   ```bash
   claude --help  # Check available flags
   ```

### Codex: Permission issues

**Problem:** Codex may need explicit permission flags.

**Solution:**

```toml
[runners.codex]
argv = ["codex", "exec", "--full-auto"]
```

### GitHub Copilot: File access

**Problem:** Copilot CLI may have workspace restrictions.

**Solution:**

```toml
[runners.copilot]
argv = ["copilot", "--prompt", "--allow-file-write"]
```

## Common Issues

### "No task selected" or empty PRD

**Problem:** PRD file is malformed or empty.

**Solution:**

1. Check your PRD file exists: `.ralph/prd.json` or `.ralph/PRD.md`
2. Validate JSON format: `cat .ralph/prd.json | jq .`
3. For Markdown, ensure you have a `## Tasks` section with checkboxes

### "Rate limit reached"

**Problem:** Too many iterations in short time.

**Solution:**

```toml
[loop]
rate_limit_per_hour = 0  # Disable rate limiting
# or increase the limit
rate_limit_per_hour = 100
```

### "No progress streak"

**Problem:** Agent isn't making git commits or file changes.

**Solution:**

1. Check agent has write permissions (see above)
2. Review last log: `ralph logs --last`
3. Ensure AGENTS.md has correct build/test commands
4. Try dry-run: `ralph step --dry-run`

### Git not initialized

**Problem:** Ralph requires a git repository.

**Solution:**

```bash
git init
git add .
git commit -m "Initial commit"
```

### Agent CLI not found

**Problem:** Agent CLI not installed or not in PATH.

**Solution:**

```bash
ralph doctor  # Check what's missing

# Install missing tools:
npm install -g @openai/codex@alpha
# or
brew install claude-code
# or
gh extension install github/gh-copilot
```

## Debug Mode

To see exactly what ralph is doing:

1. **Check the last log:**

   ```bash
   ralph logs --last
   ```

2. **View the prompt sent to agent:**

   ```bash
   cat .ralph/prompt-iter0001.txt
   ```

3. **Check state:**

   ```bash
   cat .ralph/state.json | jq .
   ```

4. **Dry run to preview:**

   ```bash
   ralph step --dry-run
   ```

## Getting Help

1. Check logs: `ralph logs --last`
2. Check status: `ralph status`
3. Verify setup: `ralph doctor`
4. Review config: `ralph edit config`
5. Open an issue: <https://github.com/jscraik/ralph-gold/issues>
