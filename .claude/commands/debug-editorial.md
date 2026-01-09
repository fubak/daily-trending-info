# /debug-editorial - Debug Editorial Generation

Debug and test editorial article generation.

## Input - Use AskUserQuestion Tool

### Required: Debug Focus

**question**: "What editorial aspect needs debugging?"
**options**:
- label: "Full editorial pipeline"
  description: "Test complete 8-section article generation"
- label: "LLM prompts"
  description: "Review and test Groq/OpenRouter prompts"
- label: "Section structure"
  description: "Validate 8 required sections"
- label: "Theme extraction"
  description: "Debug central theme identification"

## Key Files

- `scripts/editorial_generator.py` - Main editorial generator
- `scripts/enrich_content.py` - Content enrichment (Word of Day, etc.)

## 8 Required Sections

1. **Lead** - Hook + thesis
2. **What People Think** - Common perspectives
3. **What's Happening** - Current events
4. **Hidden Tradeoffs** - Non-obvious considerations
5. **Counterarguments** - Alternative viewpoints
6. **What's Next** - Future outlook
7. **Framework** - Mental model
8. **Conclusion** - Summary

## Execution

```bash
# Test editorial generation with existing trends
cd scripts && python -c "
from editorial_generator import generate_editorial
from collect_trends import load_trends
trends = load_trends()
if trends:
    result = generate_editorial(trends[:3])
    print('Editorial generated:', bool(result))
"
```

## Output

Report editorial generation status with specific issues found.
