# Voice Agent Orchestrator

Multi-agent voice AI orchestration framework for home services, built on [LiveKit Agents](https://docs.livekit.io/agents/).

Demonstrates deterministic conversation control over probabilistic LLM outputs through finite state machines, slot-filling with confirmation gates, multi-layer guardrails, and an evaluation framework for continuous improvement.

## Architecture

```
Caller  ──>  Deepgram STT  ──>  Agent Orchestrator  ──>  Cartesia TTS  ──>  Caller
                                        │
                          ┌─────────────┼─────────────┐
                          │             │             │
                    IntakeAgent   BookingAgent   InfoAgent
                          │             │             │
                          └──── EscalationAgent ──────┘
```

### Agents

| Agent | Responsibility | Tools |
|-------|---------------|-------|
| **IntakeAgent** | Greet, identify intent, route | `route_to_booking`, `route_to_info`, `route_to_emergency`, `identify_caller` |
| **BookingAgent** | Slot collection, confirmation gate, booking | `record_*` (7 slots), `confirm_booking_details`, `check_and_book`, `correct_detail`, `escalate_to_human` |
| **InfoAgent** | Service/pricing questions | `get_service_info`, `list_all_services`, `route_to_booking` |
| **EscalationAgent** | Emergency handling, human handoff | `complete_handoff`, `record_callback_number`, `provide_emergency_guidance` |

### Conversation State Machine

12 states with 23 explicit transitions ensuring deterministic conversation flow:

```
GREETING → INTENT_DETECTION → SERVICE_SELECTION → SLOT_FILLING → SLOT_CONFIRMATION
    → AVAILABILITY_CHECK → BOOKING_CREATION → CONFIRMATION → FAREWELL

Branch paths:
  INTENT_DETECTION → INFO_RESPONSE (service questions)
  INTENT_DETECTION → ESCALATION (emergency / human request)
  SLOT_FILLING → ERROR_RECOVERY (max retries)
  SLOT_CONFIRMATION → SLOT_FILLING (caller corrects info)
```

### Slot-Filling Pattern

Three-phase lifecycle: **Collect → Validate → Confirm**

- 7 slots with per-slot validators (phone regex, service catalog match, address length)
- Correction history tracking for evaluation
- Confirmation gate prevents booking execution until explicit caller approval

### Guardrails

Four independent layers composed into pre-LLM and post-LLM pipelines:

1. **ScopeGuardrail** — validates services against catalog, rejects off-topic requests
2. **HallucinationGuardrail** — flags unverified claims (guarantees, warranties, etc.)
3. **PersonaGuardrail** — enforces voice style, blocks AI self-references and markdown
4. **EscalationGuardrail** — detects emergencies, frustration keywords, error thresholds

## Setup

```bash
# Clone and install
git clone <repo-url> && cd voice-agent-orchestrator
pip install -e ".[dev]"

# Configure environment
cp .env.example .env
# Edit .env with your API keys
```

## Usage

```bash
# Run tests
make test

# Run with coverage
make test-cov

# Run evaluation on sample transcripts
make eval

# Start voice agent (requires LiveKit server)
make run

# Start in console mode (text-only, no mic)
make console
```

## Evaluation Framework

15 KPIs across 5 categories, 10 failure pattern detectors, and auto-improvement suggestions.

```bash
python -m src.evaluation.run_eval --transcripts sample_transcripts/ --verbose
```

### Metrics

| Category | KPIs |
|----------|------|
| Task Success | Success rate, first-call resolution, containment rate |
| Slot Quality | Fill rate, correction rate, avg attempts, confirmation pass rate |
| Efficiency | Avg turns to booking, avg duration, handoff rate |
| Errors | Error rate, recovery success rate, escalation rate |
| Guardrails | Scope violation rate, hallucination detection rate |

### Failure Detection

Detects 10 patterns: repeated slot failure, confirmation loops, wrong agent handoff, scope violations, caller frustration, hallucinated info, missed intent, incomplete booking, unnecessary escalation, slow responses.

### Auto-Improvement

Maps each detected failure to a specific prompt modification with expected impact. Prioritized by severity (critical > high > medium > low).

## Configuration

All business values are configurable via environment variables — nothing is hardcoded in agent logic. See `.env.example` for all options.

## Project Structure

```
voice-agent-orchestrator/
├── src/
│   ├── agents/           # 4 specialized agents
│   ├── conversation/     # State machine, slot manager, guardrails
│   ├── evaluation/       # Metrics, failure detection, auto-improvement
│   ├── prompts/          # System prompts and templates
│   ├── schemas/          # Pydantic models
│   ├── tools/            # Mock service integrations
│   └── config.py         # Centralized configuration
├── tests/                # Test suite
├── sample_transcripts/   # 5 evaluation scenarios
├── main.py               # LiveKit entry point
├── pyproject.toml
└── Makefile
```

## Tech Stack

- **Voice Pipeline**: LiveKit Agents SDK, Deepgram STT, OpenAI GPT-4o-mini, Cartesia TTS, Silero VAD
- **Framework**: Python 3.11+, Pydantic, asyncio
- **Testing**: pytest, ruff, mypy
- **CI**: GitHub Actions
