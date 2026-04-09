# Troubleshooting

## Installation

### Plugin install fails with "Permission denied (publickey)"

**Symptom:**

```
Error: Failed to install: Failed to clone repository
git@github.com: Permission denied (publickey).
fatal: Could not read from remote repository.
```

**Cause:** Git is configured to redirect HTTPS to SSH. The plugin clones over HTTPS but git rewrites the URL to SSH, which fails without a GitHub SSH key configured.

**Fix:**

```bash
git config --global url."https://github.com/".insteadOf "git@github.com:"
```

Then retry the install.

---

## Getting Help

- [Open an issue](https://github.com/itential/builder-skills/issues/new)
- [Start a discussion](https://github.com/itential/builder-skills/discussions)
