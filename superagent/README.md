# SuperAgent - Advanced AI Agent with Multi-Level Planning

**Enhanced OODA loop agent with vision, self-reflection, and intent understanding**

## Features

-  **Multi-level Planning** - Strategic → Tactical → Operational hierarchy
-  **Intent-Based Execution** - Understands WHAT you want, not HOW
-  **Vision Integration** - Google Gemini 2.5 Flash for screen understanding
-  **Loop Detection** - Prevents infinite loops, forces progress
-  **Self-Reflection** - Detects failures and adapts approach
-  **Direct App Control** - Launches Chrome, Gmail, Slack, etc.
-  **Active Development** - Fixing Xpra rendering and tactical planning

---

##  Architecture

```
┌─────────────────────────────────────────┐
│         EnhancedSuperAgent              │
├─────────────────────────────────────────┤
│  • Strategic Planning (Goal → Steps)    │
│  • Tactical Planning (Steps → Actions)  │
│  • OODA Loop (Observe-Decide-Act)       │
│  • Self-Reflection & Adaptation          │
│  • Loop Detection & Breaking             │
└─────────────────────────────────────────┘
           │                    │
           ▼                    ▼
    ┌────────────┐      ┌──────────────┐
    │   Vision   │      │   Executor   │
    │  (Gemini)  │      │  (PyAutoGUI) │
    └────────────┘      └──────────────┘
```

### Components

| File | Purpose | Status |
|------|---------|--------|
| `enhanced_core.py` | Multi-level planning agent |  Complete |
| `actions.py` | Action types & results |  Complete |
| `gemini_vision.py` | Google Gemini 2.5 Flash API |  Complete |
| `advanced_vision.py` | OCR + UI detection |  Complete |
| `executor.py` | PyAutoGUI execution |  Complete |
| `memory.py` | Short/long-term memory |  Complete |
| `workflows.py` | Multi-app orchestration |  Complete |

---

## Quick Start

### 1. Set API Key
```bash
export GEMINI_API_KEY="your_key_here"
```

### 2. Run Agent
```python
from superagent.enhanced_core import EnhancedSuperAgent
from superagent.gemini_vision import GeminiVisionAPI

vision_api = GeminiVisionAPI(api_key="YOUR_KEY", model="gemini-2.5-flash")
agent = EnhancedSuperAgent(vision_api=vision_api, max_iterations=50)

result = agent.execute_task("find information about OpenAI")
```

### 3. Test via API
```bash
curl -X POST http://localhost:10000/api/superagent/execute \
  -H "Content-Type: application/json" \
  -d '{"task": "find information about OpenAI", "userId": "test"}'
```
---
