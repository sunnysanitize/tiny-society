---
name: mirofish-benchmark
description: User is benchmarking their "Tiny Society AI" sim against MiroFish and wants generative-agents-level realism
metadata:
  type: project
---

The user's project ("Tiny Society AI", dir name mirofish-simulation) is a multi-agent LLM social sim. They are explicitly benchmarking its realism against **MiroFish** (open-source repo github.com/666ghj/MiroFish), a swarm-intelligence prediction engine.

**Why:** They feel MiroFish's simulations are more realistic than theirs and want to mirror that.

**How to apply:** The realism gap is architectural, not prompt-tuning. MiroFish's realism comes from: GraphRAG knowledge-graph grounding, Zep temporal memory, the OASIS engine (CAMEL-AI, 23 social actions, scales to 1M agents), observation-based info diffusion. Their project's biggest gaps vs. the canonical Stanford "Generative Agents" realism recipe: (1) no relevance-based memory retrieval — just last-N truncation in [[None]] reasoner.py; (2) no reflection step; (3) global event log instead of per-agent observation/info-asymmetry; (4) relationships collapsed to a single float; (5) static goals, no planning. Their perception layer (perception.py) is actually a genuine strength worth keeping.
