# /check-design - Design System Validation

Validate the AI-generated design system configuration.

## Input - Use AskUserQuestion Tool

### Required: Check Type

**question**: "What aspect of the design system should I check?"
**options**:
- label: "Full design validation (Recommended)"
  description: "Check all design elements: colors, typography, hero styles, animations"
- label: "Color scheme only"
  description: "Validate color accessibility and contrast ratios"
- label: "Typography only"
  description: "Check font loading and scale"
- label: "Hero styles"
  description: "Validate hero section generation"

## Key Files

- `scripts/generate_design.py` - Design system generator
- `scripts/config.py` - Design constants (ALLOWED_FONTS, color schemes)
- `data/design.json` - Generated design configuration

## Execution

```bash
# Check design.json exists and is valid
python3 -c "import json; json.load(open('data/design.json'))" && echo "Design JSON: Valid"

# Run design generation in dry-run
cd scripts && python main.py --dry-run
```

## Validation Checklist

- [ ] 9 personalities available (brutalist, editorial, minimal, etc.)
- [ ] 12 hero styles configured
- [ ] 20+ color schemes defined
- [ ] Font whitelist enforced (ALLOWED_FONTS in config.py)
- [ ] Animation levels appropriate

## Output

Report design system status with any issues found.
