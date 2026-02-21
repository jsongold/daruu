# PRD: Agent-Driven Chat UI — Appendix: Current vs New Architecture

> **Source:** Split from [agent-chat-ui.md](../agent-chat-ui.md). See [README](README.md) for the full index.

## Appendix: Current vs New Architecture

```
CURRENT:
┌──────────┐    ┌──────────┐    ┌──────────┐
│  Mode    │ → │ Pipeline │ → │  Output  │
│ Selection│    │  Stages  │    │          │
└──────────┘    └──────────┘    └──────────┘
     ↑               ↑               ↑
     └───────────────┴───────────────┘
              User sees all of this

NEW:
┌──────────────────────────────────────────┐
│              Chat Interface              │
│  ┌────────────────────────────────────┐  │
│  │          Agent (LLM)               │  │
│  │  ┌─────────────────────────────┐   │  │
│  │  │   Pipeline (hidden)         │   │  │
│  │  │   INGEST→STRUCT→...→FILL    │   │  │
│  │  └─────────────────────────────┘   │  │
│  └────────────────────────────────────┘  │
└──────────────────────────────────────────┘
              User sees only chat
```
