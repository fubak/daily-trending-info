# /check-workflow - GitHub Actions Workflow Status

Check and debug GitHub Actions workflow configuration.

## Input - Use AskUserQuestion Tool

### Required: Workflow Check

**question**: "Which workflow should I check?"
**options**:
- label: "Daily regenerate (Recommended)"
  description: "Main daily pipeline workflow"
- label: "Auto-merge Claude"
  description: "Claude PR auto-merge workflow"
- label: "All workflows"
  description: "Check all workflow files"

## Key Files

- `.github/workflows/daily-regenerate.yml` - Main pipeline (6 AM EST)
- `.github/workflows/auto-merge-claude.yml` - Auto-merge claude/** branches
- `.github/workflows/update-readme.yml` - README changelog updates

## Execution

```bash
# List all workflows
ls -la .github/workflows/

# Validate YAML syntax
for f in .github/workflows/*.yml; do
  yq eval '.' "$f" > /dev/null 2>&1 && echo "✓ $(basename $f)" || echo "✗ $(basename $f) - YAML error"
done

# Check for required secrets references
grep -h "secrets\." .github/workflows/*.yml | sort -u
```

## Required Secrets

- `GROQ_API_KEY` - Primary AI
- `OPENROUTER_API_KEY` - Backup AI
- `PEXELS_API_KEY` - Primary images
- `UNSPLASH_ACCESS_KEY` - Backup images

## Output

Report workflow status and any configuration issues.
