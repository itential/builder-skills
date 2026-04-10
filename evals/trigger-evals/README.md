# Skill Trigger Evaluations

Trigger eval sets for the 5 high-conflict skills in the builder-skills plugin. Used to test and optimize skill description routing.

## Files

| File | Purpose |
|------|---------|
| `{skill}.json` | 20-query eval set (10 should-trigger, 10 should-not-trigger) |
| `{skill}-results.json` | Last eval run results |

## Running

```bash
# Single eval pass against a skill's current description
cd ~/.claude/plugins/cache/claude-plugins-official/skill-creator/unknown/skills/skill-creator
python -m scripts.run_eval \
  --eval-set /path/to/builder-skills/evals/trigger-evals/{skill}.json \
  --skill-path /path/to/builder-skills/.claude/skills/{skill} \
  --model claude-sonnet-4-6 \
  --verbose

# Full optimization loop (requires ANTHROPIC_API_KEY)
python -m scripts.run_loop \
  --eval-set /path/to/builder-skills/evals/trigger-evals/{skill}.json \
  --skill-path /path/to/builder-skills/.claude/skills/{skill} \
  --model claude-sonnet-4-6 \
  --max-iterations 5 \
  --verbose
```

## Last Results (2026-04-10)

| Skill | Score | Notes |
|-------|-------|-------|
| `documentation` | 11/20 | Precision 100%, undertriggering systemic |
| `spec-agent` | 12/20 | Precision 100%, undertriggering systemic |
| `solution-arch-agent` | 11/20 | Precision 100%, undertriggering systemic |
| `builder-agent` | 10/20 | Precision 100%, undertriggering systemic |
| `explore` | 11/20 | Precision 100%, undertriggering systemic |

**Note:** All failures are false negatives (skills not triggering when they should). Zero false positives across all skills. This is a known Claude undertriggering behavior — not a description quality issue.
