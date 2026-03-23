# Chapter 8: Conversation Managers — Controlling Context Windows

[← Back to Table of Contents](README.md) | [← Previous: Session Persistence](Chapter_07.md)

---

Conversation managers control how the conversation history is managed — truncation, summarization, or no management at all. This is different from session persistence (which stores history) — conversation managers decide **what's in the context window** when the LLM is called.

```yaml
agents:
  assistant:
    model: default
    conversation_manager:
      type: strands.agent:SlidingWindowConversationManager
      params:
        window_size: 40
        should_truncate_results: false
    system_prompt: "You are a helpful assistant."
```

## Built-in Conversation Managers

These come from strands-agents directly:

| Class | What It Does |
|-------|-------------|
| `strands.agent:SlidingWindowConversationManager` | Keeps the last N messages in context |
| `strands.agent:SummarizingConversationManager` | Summarizes older messages to save context |
| `strands.agent:NullConversationManager` | No management — keeps entire history |

## Using Them

```yaml
# Fixed-window approach
conversation_manager:
  type: strands.agent:SlidingWindowConversationManager
  params:
    window_size: 20

# Summarization approach
conversation_manager:
  type: strands.agent:SummarizingConversationManager
  params:
    summary_ratio: 0.3
    preserve_recent_messages: 10

# No management (pass everything)
conversation_manager:
  type: strands.agent:NullConversationManager
```

## Custom Conversation Managers

Write your own by subclassing `strands.agent.conversation_manager.ConversationManager`:

```yaml
conversation_manager:
  type: ./managers.py:MySmartManager
  params:
    strategy: semantic_relevance
```

> **Tips & Tricks**
>
> - Conversation managers are per-agent. Different agents in the same config can use different strategies.
> - For orchestration coordinators that do a lot of delegating, `SlidingWindowConversationManager` with a generous `window_size` prevents context overflow from long delegate tool results.
> - Unlike session managers, there's no "global" conversation manager — set it on each agent that needs one.

---

[Next: Chapter 9 — MCP →](Chapter_09.md)
