# Customizations

Use this directory to layer organization, team, and developer-specific guidance on top of the canonical Itential Builder Skills.

Canonical source remains:

```text
AGENTS.md
skills/*/SKILL.md
docs/constitution.md
```

Customization layers are optional and applied in this order:

| Priority | Layer | Path | Tracked |
|---:|---|---|---|
| 1 | Developer local | `customizations/developer/` | No, except examples |
| 2 | Team | `customizations/team/` | Yes |
| 3 | Organization | `customizations/org/` | Yes |
| 4 | Core | `AGENTS.md`, `skills/`, `docs/constitution.md` | Yes |

Higher-priority layers may add guidance or narrow choices, but they must not violate `docs/constitution.md`.

Recommended files:

```text
customizations/org/style.md
customizations/org/security.md
customizations/org/platform-defaults.md

customizations/team/style.md
customizations/team/delivery-rules.md
customizations/team/platform-defaults.md

customizations/developer/local-style.md
customizations/developer/local-notes.md
```

Developer-local files are ignored by git. Use `*.example.md` files to share templates.
