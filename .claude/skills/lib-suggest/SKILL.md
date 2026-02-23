---
name: lib-suggest
description: Use this skill when you need to add new functionality that likely has existing library solutions. Searches for and compares popular libraries, presents options in a table format, and provides recommendations. Invoke with /lib-suggest <feature description>.
---

# Library Suggestion Skill

This skill helps find and evaluate popular libraries for common functionality instead of writing code from scratch.

## When to Use

Invoke this skill when:
- Adding UI interactions (pan, zoom, drag-drop, resize, virtual scroll)
- Implementing data visualization (charts, graphs, maps)
- Handling forms (validation, multi-step, file upload)
- Managing state (global, form, server state)
- Processing files (PDF, images, video, audio)
- Working with dates/times
- Adding animations/transitions
- Implementing authentication
- Real-time features (WebSockets, SSE)

## How to Invoke

```
/lib-suggest <feature description>
```

Examples:
- `/lib-suggest pan and zoom for image preview`
- `/lib-suggest form validation in React`
- `/lib-suggest PDF generation in Python`
- `/lib-suggest drag and drop file upload`

## What This Skill Does

1. **Identifies the category** of functionality needed
2. **Searches** for popular libraries (npm, PyPI, crates.io)
3. **Evaluates** each option by:
   - GitHub stars / downloads
   - Bundle size / dependencies
   - TypeScript support
   - Active maintenance
   - Documentation quality
4. **Presents comparison table** with options
5. **Recommends** the best fit with reasoning
6. **Shows example usage** for the recommended library

## Output Format

### Comparison Table

| Library | Stars | Size | Features | Best For |
|---------|-------|------|----------|----------|
| **recommended-lib** | 10k+ | ~15kb | Full feature list | Primary use case |
| alternative-a | 5k+ | ~8kb | Feature list | Specific use case |
| alternative-b | 2k+ | ~20kb | Feature list | Another use case |

### Recommendation Section

```markdown
**Recommendation: `recommended-lib`**

Reasons:
1. Most popular and well-maintained
2. Best TypeScript support
3. Comprehensive documentation
4. Active community

Example usage:
```code
import { Component } from 'recommended-lib'

<Component option={value} />
```
```

## Common Library Categories

### React UI Interactions
- `react-zoom-pan-pinch` - Pan/zoom/pinch
- `react-dnd` / `dnd-kit` - Drag and drop
- `react-resizable` - Resize elements
- `react-virtual` / `@tanstack/virtual` - Virtual scrolling

### Forms
- `react-hook-form` - Form state
- `zod` / `yup` - Schema validation
- `react-dropzone` - File upload

### Data Visualization
- `recharts` - Simple charts
- `@nivo/core` - Rich visualizations
- `react-map-gl` - Maps

### State Management
- `zustand` - Simple global state
- `@tanstack/query` - Server state
- `jotai` / `recoil` - Atomic state

### Animation
- `framer-motion` - Declarative animations
- `react-spring` - Physics-based
- `auto-animate` - Zero-config

### Python PDF
- `pypdf` / `PyMuPDF` - PDF manipulation
- `reportlab` - PDF generation
- `pdfplumber` - PDF extraction

### Python Web
- `httpx` - HTTP client
- `pydantic` - Data validation
- `fastapi` - API framework

## Quality Thresholds

Libraries must meet these criteria:

| Criterion | Minimum Requirement |
|-----------|---------------------|
| GitHub Stars | 500+ |
| Last Commit | Within 6 months |
| TypeScript | Types available |
| Documentation | README with examples |
| Issues Response | Maintainer activity |

## Decision Tree

```
Is this common functionality?
├── Yes → Search for libraries
│   ├── Found popular options → Present comparison table
│   │   └── User selects → Implement with library
│   └── No good options → Discuss custom implementation
└── No (very specific) → Custom implementation OK
```

## Integration Notes

After user selects a library:
1. Install the package
2. Read the documentation
3. Implement following library patterns
4. Don't fight the library's conventions
5. Test the integration
