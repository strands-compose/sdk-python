# YAML Configuration Guide

**Everything you need to know about writing strands-compose YAML configs — from zero to production.**

strands-compose lets you describe entire multi-agent systems in YAML and get back live, fully wired strands objects. This guide walks you through every configuration option, from the simplest one-agent setup to nested multi-orchestration systems with MCP servers, hooks, session persistence, conditional graph pipelines, and multi-file configs.

No prior YAML expertise required. We start simple and build up.

---

## Table of Contents

1. [The Basics — Your First Config](Chapter_01.md)
2. [Models — Choosing Your LLM](Chapter_02.md)
3. [Variables — Environment-Driven Config](Chapter_03.md)
4. [YAML Anchors — DRY Config Blocks](Chapter_04.md)
5. [Tools — Giving Agents Superpowers](Chapter_05.md)
6. [Hooks — Middleware for Agents](Chapter_06.md)
7. [Session Persistence — Memory That Survives Restarts](Chapter_07.md)
8. [Conversation Managers — Controlling Context Windows](Chapter_08.md)
9. [MCP — External Tool Servers](Chapter_09.md)
10. [Orchestrations — Multi-Agent Systems](Chapter_10.md)
11. [Graph Conditions — Dynamic Routing](Chapter_11.md)
12. [Nested Orchestrations — Composing Systems](Chapter_12.md)
13. [Multi-File Configs — Splitting and Merging](Chapter_13.md)
14. [Agent Factories — Custom Agent Construction](Chapter_14.md)
15. [Event Streaming — Real-Time Observability](Chapter_15.md)
16. [Name Sanitization — How Names Are Handled](Chapter_16.md)
17. [The Loading Pipeline — What Happens Under the Hood](Chapter_17.md)
18. [Full Reference — Every Field at a Glance](Chapter_18.md)

**Bonus**: [Quick Recipes](Quick_Recipes.md) — Copy-paste-ready configs for common patterns.

---

That covers everything strands-compose YAML has to offer. When in doubt, check the [examples](../../examples/) — each one is a self-contained demo of the concepts above. And remember: after `load()`, what you get back are plain strands objects. No wrappers, no subclasses. Just the real deal, fully wired and ready to go.

Happy composing! 🎼
