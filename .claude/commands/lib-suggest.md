# Library Suggestion Command

Find and compare popular libraries for common functionality.

## Usage

```
/lib-suggest <feature description>
```

## Examples

```
/lib-suggest pan and zoom for React
/lib-suggest form validation
/lib-suggest PDF generation Python
/lib-suggest drag and drop
/lib-suggest charts and graphs
/lib-suggest date picker
/lib-suggest infinite scroll
/lib-suggest authentication
```

## Process

When invoked, follow these steps:

### 1. Identify Category

Determine which category the request falls into:
- UI interactions (pan, zoom, drag, resize)
- Forms and validation
- Data visualization
- State management
- File processing
- Date/time handling
- Animation
- Authentication
- Real-time communication

### 2. Search for Libraries

For the identified category, search:
- npm (for JavaScript/TypeScript)
- PyPI (for Python)
- Evaluate by: stars, size, maintenance, TypeScript support

### 3. Present Comparison Table

Format results as:

| Library | Stars | Size | Features | Best For |
|---------|-------|------|----------|----------|
| **lib-name** | Xk+ | ~Xkb | Key features | Primary use case |

### 4. Make Recommendation

Provide:
- Clear recommendation with reasoning
- Example usage code
- Installation command
- Trade-offs if applicable

### 5. Ask for Selection

Let user choose which library to use, then proceed with implementation.

## Quality Criteria

Only suggest libraries that meet:
- 500+ GitHub stars
- Active maintenance (commits in last 6 months)
- Good documentation
- TypeScript support (for JS libraries)

## Output Template

```markdown
## Library Options for: [Feature]

| Library | Stars | Size | Features | Best For |
|---------|-------|------|----------|----------|
| **recommended** | Xk+ | ~Xkb | Features | Use case |
| option-2 | Xk+ | ~Xkb | Features | Use case |
| option-3 | Xk+ | ~Xkb | Features | Use case |

**Recommendation: `recommended`**

Reasons:
1. Reason one
2. Reason two
3. Reason three

Example usage:
\`\`\`typescript
import { Feature } from 'recommended'

// Basic example
\`\`\`

Which option would you like to use?
```
