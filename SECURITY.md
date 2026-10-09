# Security Policy

## Supported Versions

Security fixes are released for the latest version only. Update to the newest release to receive them.

| Version | Supported          |
| ------- | ------------------ |
| Latest release | :white_check_mark: |
| Older releases | :x:                |

## Reporting a Vulnerability

If you discover a security vulnerability in this project:

1. **Do not** create a public GitHub issue
2. Report via one of the following:
   - **Preferred:** [GitHub Security Advisories](https://github.com/itential/builder-skills/security/advisories/new) (report privately)
   - **Alternative:** security@itential.com
3. Include in your report:
   - Description of the vulnerability
   - Steps to reproduce
   - Affected versions
   - Impact assessment
   - Suggested fix (if any)

We will acknowledge your report within 48 hours and provide regular updates on our progress toward a fix. We follow coordinated disclosure practices.

## Security Best Practices

These skills drive an AI agent that calls your Itential Platform's API with your credentials. When using them:

- **Credentials:** keep platform credentials in the `.env` of the folder you work in (the agent caches a token in `.auth.json` next to it). Never commit either file, and never put credentials in a skill's `custom/` rules.
- **Least privilege:** use a service account whose roles cover only what the work needs, rather than an administrator's login.
- **Review before changes:** read what the agent plans to change on the platform before you approve it, and try new work on a non-production platform first.
- **Treat `custom/` rules as code:** they are instructions the agent follows. Review changes to them like any other change to your automation.
- **Report skill guidance that is unsafe** — for example, guidance that could expose credentials or bypass a skill's safety rules — the same way as any other vulnerability (above).
