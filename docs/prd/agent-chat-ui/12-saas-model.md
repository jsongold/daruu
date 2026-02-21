# PRD: Agent-Driven Chat UI — SaaS Model

> **Source:** Split from [agent-chat-ui.md](../agent-chat-ui.md). See [README](README.md) for the full index.

## SaaS Model

### Features

| Feature | Description |
|---------|-------------|
| **Multi-tenancy** | Org/workspace isolation, team management, role-based access |
| **Billing** | Stripe integration, subscription management |
| **Usage Tracking** | Documents processed, API calls, storage used |
| **Plans** | Subscription tiers with limits |

### Subscription Tiers

| Tier | Limits | Features |
|------|--------|----------|
| **Free** | 10 docs/month, 100MB storage | Basic form filling |
| **Pro** | 100 docs/month, 1GB storage | Templates, batch processing, priority support |
| **Enterprise** | Unlimited | Custom templates, API access, SSO, dedicated support |

### Usage Tracking

| Metric | Tracked For |
|--------|-------------|
| Documents processed | Billing, limits |
| API calls | Rate limiting, billing |
| Storage used | Plan limits |
| LLM tokens | Cost tracking |

### Multi-tenancy Schema

Tables: `organizations` (id, name, plan, stripe_customer_id), `org_members` (org_id, user_id, role), `usage` (org_id, metric, value, period). Add `org_id` to `conversations`.

See [agent-chat-ui.md](../agent-chat-ui.md) § SaaS Model for full SQL.
