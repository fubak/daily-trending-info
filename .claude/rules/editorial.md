# Editorial Rules

## Article Structure (8 required sections)
1. **Lead** - Hook + thesis
2. **What People Think** - Public sentiment
3. **What's Happening** - Current facts
4. **Hidden Tradeoffs** - Deeper analysis
5. **Counterarguments** - Alternative views
6. **What's Next** - Future implications
7. **Framework** - Mental model
8. **Conclusion** - Summary

## Article Features
- Permanent retention
- URL: `/articles/YYYY/MM/DD/slug/`
- JSON-LD structured data
- "Why This Matters" for top 3 trends

## Generation
- Module: `editorial_generator.py`
- Uses Groq/OpenRouter for AI
- Central themes from keyword frequency
- Context from `_build_editorial_context()`
