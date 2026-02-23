# Library-First Development

## Core Principle

ALWAYS suggest popular, battle-tested libraries before writing code from scratch.

## When to Suggest Libraries

- UI interactions (pan, zoom, drag, resize)
- Data visualization (charts, graphs)
- Form handling and validation
- State management
- Date/time handling
- Animation and transitions
- File processing (PDF, images, video)
- Authentication flows
- Real-time communication

## Decision Process

1. **Identify the need** - What specific functionality is required?
2. **Search for libraries** - Find popular solutions (npm, PyPI)
3. **Evaluate options** - Compare by:
   - GitHub stars and maintenance activity
   - Bundle size / dependencies
   - TypeScript support
   - Features vs complexity
   - Documentation quality
4. **Present to user** - Format as comparison table
5. **Implement chosen library** - Don't reinvent the wheel

## Suggestion Format

Always present library suggestions as a comparison table:

```markdown
| Library | Stars | Size | Features | Best For |
|---------|-------|------|----------|----------|
| library-a | 10k+ | ~15kb | Feature list | Use case |
| library-b | 5k+ | ~8kb | Feature list | Use case |
```

Include:
- **Recommendation** with reasoning
- **Example usage** pattern
- **Trade-offs** between options

## Red Flags for Custom Code

Avoid writing from scratch when:
- Multiple npm packages exist with 1k+ stars
- The functionality is common (drag-drop, charts, forms)
- Security implications exist (auth, crypto)
- Cross-browser/device compatibility needed

## Exceptions (OK to Write Custom)

- Very specific business logic
- Simple utilities (<20 lines)
- When all libraries are abandoned/insecure
- Performance-critical code with specific requirements

## Quality Criteria for Library Selection

| Priority | Criterion | Minimum |
|----------|-----------|---------|
| 1 | Active maintenance | Commits in last 6 months |
| 2 | Community adoption | 500+ GitHub stars |
| 3 | TypeScript support | Types included or @types/* |
| 4 | Documentation | README + examples |
| 5 | Bundle size | Appropriate for use case |
