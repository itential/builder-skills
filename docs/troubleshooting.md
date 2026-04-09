# Troubleshooting

## Installation

### Plugin not found or fails to install

**Fix:** Make sure you are on the latest version of Claude Code, then retry:

```bash
/plugin install itential-builder@claude-plugins-official
```

---

## Environment Setup

### Skills can't connect to the platform

**Symptom:** Agent errors on first run, authentication failures, or "platform not reachable."

**Fix:** Verify your `.env` file exists in the folder where you are running the skill and contains the correct values for your platform:

```bash
# Cloud / OAuth
PLATFORM_URL=https://your-instance.itential.io
AUTH_METHOD=oauth
CLIENT_ID=your-client-id
CLIENT_SECRET=your-client-secret
```

```bash
# Local / Password
PLATFORM_URL=http://localhost:4000
AUTH_METHOD=password
USERNAME=admin
PASSWORD=admin
```

The `.env` file must be in your use-case directory, not the plugin directory.

---

## Getting Help

- [Open an issue](https://github.com/itential/builder-skills/issues/new)
- [Start a discussion](https://github.com/itential/builder-skills/discussions)
