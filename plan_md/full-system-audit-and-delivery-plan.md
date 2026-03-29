# Polis Full System Audit And Delivery Plan

## Scope

This audit compares the current codebase against the required systems in the request and the target architecture in `plan_md/polis-open-ended-action-system.md`.

Status labels:

- `COMPLETE`: implemented and wired through backend plus frontend where relevant
- `PARTIAL`: meaningful code exists, but the system is incomplete, off-spec, or not fully integrated
- `MISSING`: no real implementation
- `OFF-SPEC`: code exists, but it conflicts with the requested architecture and should be removed or folded back into the open-ended action model

## Reality Check

- The frontend does **not currently build**. `npm run build` fails because [`frontend/src/stores/simulationStore.ts:141`]( /Users/benwu/Desktop/aitown/frontend/src/stores/simulationStore.ts#L141 ) pushes a `conversationId` field that is not declared in the speech bubble type or `GameEvent`.
- The backend test suite is **not currently runnable as-is** in this environment. `python3 -m unittest discover -s backend/tests -q` fails because the tests import `simulation` and `systems` as top-level modules without setting `PYTHONPATH`.
- The current engine still contains several explicit subsystems that the requested architecture says should **not** be first-class mechanics, including direct economy/barter/tax handling in [`backend/simulation/engine.py:1840`]( /Users/benwu/Desktop/aitown/backend/simulation/engine.py#L1840 ), [`backend/simulation/engine.py:1984`]( /Users/benwu/Desktop/aitown/backend/simulation/engine.py#L1984 ), and the imported `EconomySystem` in [`backend/simulation/engine.py:16`]( /Users/benwu/Desktop/aitown/backend/simulation/engine.py#L16 ).

## Audit

### Core Engine

| System | Status | Audit |
| --- | --- | --- |
| Simulation Loop | `PARTIAL` | A real tick loop exists in [`backend/simulation/engine.py:1815`]( /Users/benwu/Desktop/aitown/backend/simulation/engine.py#L1815 ), but it does not follow the requested loop shape. Novelty, action interpretation, and consequences are not the universal heartbeat for every agent. |
| Action Interpreter | `PARTIAL` | There is one LLM evaluator in [`backend/systems/action_interpreter.py:15`]( /Users/benwu/Desktop/aitown/backend/systems/action_interpreter.py#L15 ), but it returns a much thinner schema than the spec and is only invoked opportunistically every 30 ticks for one random idle agent in [`backend/simulation/engine.py:2409`]( /Users/benwu/Desktop/aitown/backend/simulation/engine.py#L2409 ). |
| Consequence Engine | `PARTIAL` | Consequences are embedded in `ActionInterpreter.apply_consequences()` at [`backend/systems/action_interpreter.py:64`]( /Users/benwu/Desktop/aitown/backend/systems/action_interpreter.py#L64 ) instead of being a dedicated engine. It handles only simple resource consumption, object creation, and basic skill logging. It does not implement success/failure branches, observability, injuries, unlocks, or world-change application from the spec. |
| World State | `PARTIAL` | The mutable world exists in [`backend/simulation/world.py`]( /Users/benwu/Desktop/aitown/backend/simulation/world.py ), with locations, resources, structures, and pathfinding. It does not yet provide a complete object model, innovation registry, latent possibility registry, or world-change application layer required by the open-ended action spec. |

### Agent Cognition

| System | Status | Audit |
| --- | --- | --- |
| Drive System | `PARTIAL` | Deterministic drives exist in [`backend/agents/cognition/drives.py:4`]( /Users/benwu/Desktop/aitown/backend/agents/cognition/drives.py#L4 ), but the required list is incomplete. Thirst and belonging are missing as drives, energy/health are not modeled as drives, and world/environmental effects are only lightly integrated. |
| Attention System | `PARTIAL` | `WorkingMemory` provides a 7-item attention-like buffer in [`backend/agents/cognition/working_memory.py:7`]( /Users/benwu/Desktop/aitown/backend/agents/cognition/working_memory.py#L7 ), but it is not a scored attention system with priority, persistence, eviction policy, and formal prompt selection. |
| Emotional State | `PARTIAL` | The 10 requested emotion axes and decay exist in [`backend/agents/cognition/emotions.py:18`]( /Users/benwu/Desktop/aitown/backend/agents/cognition/emotions.py#L18 ), but baseline tuning is shallow and many event mappings are incomplete or inconsistent with engine usage. |
| Memory System | `PARTIAL` | Structured episodes exist in [`backend/agents/cognition/episodic_memory.py:8`]( /Users/benwu/Desktop/aitown/backend/agents/cognition/episodic_memory.py#L8 ), with retrieval by recency/emotion/rehearsal in [`backend/agents/cognition/episodic_memory.py:100`]( /Users/benwu/Desktop/aitown/backend/agents/cognition/episodic_memory.py#L100 ). Missing pieces: embeddings, LLM-shaped subjective encoding per witness, stronger distortion modeling, and full integration with observations/actions/conversations. |
| Belief System | `PARTIAL` | Beliefs with confidence and challenge logic exist in [`backend/agents/cognition/beliefs.py:6`]( /Users/benwu/Desktop/aitown/backend/agents/cognition/beliefs.py#L6 ), but extraction from episode patterns is weak and not systematically driven by evening reflection plus evidence accumulation. |
| Mental Model System | `PARTIAL` | A strong data model exists in [`backend/agents/cognition/mental_models.py:6`]( /Users/benwu/Desktop/aitown/backend/agents/cognition/mental_models.py#L6 ), but updates are mostly numeric deltas; there is no dedicated LLM-based post-interaction model synthesis loop matching the spec. |
| Identity System | `PARTIAL` | Identity state exists in [`backend/agents/cognition/identity.py:4`]( /Users/benwu/Desktop/aitown/backend/agents/cognition/identity.py#L4 ), and the engine does light synthesis in [`backend/simulation/engine.py:343`]( /Users/benwu/Desktop/aitown/backend/simulation/engine.py#L343 ). It does not yet produce full long-arc goal generation from identity tension. |
| Skill Memory | `PARTIAL` | Open-ended skill discovery exists in [`backend/agents/cognition/skills.py:4`]( /Users/benwu/Desktop/aitown/backend/agents/cognition/skills.py#L4 ), but it lacks the richer attempt history, failure/success trace, time-spent modeling, and direct action-interpreter skill naming loop from the target spec. |
| World Understanding | `PARTIAL` | Personal world knowledge exists in [`backend/agents/cognition/world_model.py:4`]( /Users/benwu/Desktop/aitown/backend/agents/cognition/world_model.py#L4 ), but it is still coarse, mostly correct, and not deeply integrated with misinformation, confidence, or conversation-driven updates. |

### Agent Decision Pipeline

| System | Status | Audit |
| --- | --- | --- |
| Novelty Detector | `PARTIAL` | A novelty heuristic exists in [`backend/agents/cognition/decision.py:9`]( /Users/benwu/Desktop/aitown/backend/agents/cognition/decision.py#L9 ), but it is not the main engine gate. The actual engine uses timed random novel actions instead of per-agent novelty-driven deliberation. |
| Routine Behavior System | `PARTIAL` | Routine logic exists both in [`backend/agents/cognition/decision.py:45`]( /Users/benwu/Desktop/aitown/backend/agents/cognition/decision.py#L45 ) and the richer agent routine in [`backend/agents/agent.py:334`]( /Users/benwu/Desktop/aitown/backend/agents/agent.py#L334 ). However, one routine set still references legacy locations like `bakery` and `tavern`, which do not match the frontier settlement map. |
| Decision Prompt Constructor | `MISSING` | There is no single constructor that assembles attention, drives, beliefs, mental models, goals, skills, and world understanding into the conscious decision prompt that feeds the action interpreter. |
| Inner Voice Generator | `PARTIAL` | Background thought generation exists in [`backend/agents/cognition/inner_monologue.py:65`]( /Users/benwu/Desktop/aitown/backend/agents/cognition/inner_monologue.py#L65 ), but it currently runs for one random agent every 60 ticks rather than every agent every 3-5 ticks as specified. |
| Morning Planner | `PARTIAL` | A daily planner exists in [`backend/agents/cognition/daily_cycle.py:155`]( /Users/benwu/Desktop/aitown/backend/agents/cognition/daily_cycle.py#L155 ) and is scheduled from the engine in [`backend/simulation/engine.py:1958`]( /Users/benwu/Desktop/aitown/backend/simulation/engine.py#L1958 ). It is meaningful, but not yet the master planner for the full open-ended action pipeline. |
| Evening Reflector | `PARTIAL` | The engine calls evening reflection in [`backend/simulation/engine.py:2388`]( /Users/benwu/Desktop/aitown/backend/simulation/engine.py#L2388 ), but the current system still falls short of the requested crystallization pass over beliefs, mental models, identity, and tomorrow intentions. |

### Social Systems

| System | Status | Audit |
| --- | --- | --- |
| Awareness System | `PARTIAL` | Physical/social awareness exists in [`backend/systems/interactions.py:16`]( /Users/benwu/Desktop/aitown/backend/systems/interactions.py#L16 ). It is solid, but it does not yet fully model indoor/outdoor visibility, attention competition, and observer-specific weighting from world context. |
| Interaction Decider | `PARTIAL` | Present in [`backend/systems/interactions.py:71`]( /Users/benwu/Desktop/aitown/backend/systems/interactions.py#L71 ) and used in the engine at [`backend/simulation/engine.py:2245`]( /Users/benwu/Desktop/aitown/backend/simulation/engine.py#L2245 ). This is one of the stronger systems, but still needs alignment to the spec’s drives/goals/emotion weighting and full interaction taxonomy. |
| Conversation Engine | `PARTIAL` | Multi-turn LLM conversations exist in [`backend/systems/interactions.py`]( /Users/benwu/Desktop/aitown/backend/systems/interactions.py ) and are orchestrated by [`backend/simulation/engine.py:2283`]( /Users/benwu/Desktop/aitown/backend/simulation/engine.py#L2283 ). It is substantial, but still mixes template and ad hoc logic and is not fully wired to the open-ended action architecture. |
| Conversation Consequence Processor | `PARTIAL` | Exists in [`backend/systems/interactions.py:822`]( /Users/benwu/Desktop/aitown/backend/systems/interactions.py#L822 ) and does update relationships, emotions, commitments, and memories. Missing: more rigorous gossip propagation, uncertainty, and stronger downstream belief/world-understanding changes. |
| Overhearing System | `PARTIAL` | Exists in [`backend/systems/interactions.py:286`]( /Users/benwu/Desktop/aitown/backend/systems/interactions.py#L286 ) and is used from the engine. It still needs fragment confidence handling, name-triggered anxiety redirects, and better distortion modeling. |
| Observation System | `PARTIAL` | Rule-based observations are generated in interactions and pushed into working memory in [`backend/simulation/engine.py:1940`]( /Users/benwu/Desktop/aitown/backend/simulation/engine.py#L1940 ). They are not yet stored and propagated with the richness described in the spec. |
| Avoidance System | `PARTIAL` | The avoidance logic exists in [`backend/systems/interactions.py:1083`]( /Users/benwu/Desktop/aitown/backend/systems/interactions.py#L1083 ), but it is not integrated into A* routing. Avoidance-driven detour pathfinding is still missing. |

### World Systems

| System | Status | Audit |
| --- | --- | --- |
| Pattern Detector | `PARTIAL` | Pattern recognition is split across `meta_simulation` and proposal/project logic, but there is no single spec-matching pattern detector that runs every 50 ticks over recent actions and explicitly registers emergent systems. |
| Innovation Tracker | `MISSING` | There is no actual innovation tracker with inventor, observers, adopters, and adoption rate over time. The open-ended action doc requires this and the frontend Innovation Tree depends on it. |
| World Object System | `PARTIAL` | `created_objects` exists in [`backend/simulation/world.py:203`]( /Users/benwu/Desktop/aitown/backend/simulation/world.py#L203 ) and structures append lightweight records in [`backend/simulation/world.py:652`]( /Users/benwu/Desktop/aitown/backend/simulation/world.py#L652 ). Missing: first-class world object entities with ownership, effects, durability, location, portability, and breakage. |
| Resource System | `PARTIAL` | Resources and regeneration exist in [`backend/simulation/world.py:554`]( /Users/benwu/Desktop/aitown/backend/simulation/world.py#L554 ) and [`backend/simulation/world.py:572`]( /Users/benwu/Desktop/aitown/backend/simulation/world.py#L572 ). Missing: location-level scarcity modeling, non-resource material stacks from actions, and integration with open-ended material costs. |
| Time and Environment System | `PARTIAL` | Time, weather, and season exist via `TimeManager` and are surfaced in the engine state. However, environment effects are not deeply driving feasibility, comfort, drive pressure, rendering, and resource behavior yet. |
| Pathfinding System | `PARTIAL` | A* exists in [`backend/simulation/world.py:584`]( /Users/benwu/Desktop/aitown/backend/simulation/world.py#L584 ). Missing: precomputed route caching strategy, avoidance routing, and dynamic obstacle handling for social detours. |

### Frontend

| System | Status | Audit |
| --- | --- | --- |
| Isometric Renderer | `PARTIAL` | A PixiJS isometric map exists in [`frontend/src/components/GameCanvas.tsx`]( /Users/benwu/Desktop/aitown/frontend/src/components/GameCanvas.tsx ), with pan/zoom and backend-driven tile/building rendering. Missing: weather particle effects, stronger day/night tinting, and a clean build. |
| Dynamic Object Renderer | `MISSING` | There is no renderer for backend-created world objects from the open-ended action system. The canvas currently renders tiles, buildings, agents, and speech bubbles. |
| Agent Sprite System | `PARTIAL` | Agents render and move, but the requested full animation set, richer activity icons, and clearer emotional distress indicators are incomplete. |
| Live Feed | `PARTIAL` | Present in [`frontend/src/components/panels/LiveFeed.tsx`]( /Users/benwu/Desktop/aitown/frontend/src/components/panels/LiveFeed.tsx ), but filters are narrow and it does not yet deliberately surface pattern-detection and innovation events as first-class feed categories. |
| Agent Inspector Panel | `PARTIAL` | The inspector exists in [`frontend/src/components/panels/InspectorPanel.tsx`]( /Users/benwu/Desktop/aitown/frontend/src/components/panels/InspectorPanel.tsx ), with several tabs. It still does not match the requested tab set and depth, especially for economics, world knowledge, creations, and reflections. |
| World Evolution Timeline | `PARTIAL` | Timeline-like views exist inside [`frontend/src/components/panels/Dashboard.tsx`]( /Users/benwu/Desktop/aitown/frontend/src/components/panels/Dashboard.tsx ), but there is no dedicated “world evolution timeline” focused on emergent systems, institutions, norms, innovations, and political events. |
| Innovation Tree | `MISSING` | No implementation found. |
| Top Bar | `PARTIAL` | Exists in [`frontend/src/components/panels/TopBar.tsx`]( /Users/benwu/Desktop/aitown/frontend/src/components/panels/TopBar.tsx ), but only exposes time, speed, connection, population, and average mood. It lacks food supply and institutions aggregate indicators from the requested spec. |
| God Mode Panel | `PARTIAL` | Exists in [`frontend/src/components/panels/GodModePanel.tsx`]( /Users/benwu/Desktop/aitown/frontend/src/components/panels/GodModePanel.tsx ), but its event model is still tied to off-spec systems like elections, trade caravans, and price crashes. |
| WebSocket Connection | `PARTIAL` | The WS loop exists in [`backend/main.py:71`]( /Users/benwu/Desktop/aitown/backend/main.py#L71 ) and [`frontend/src/hooks/useWebSocket.ts`]( /Users/benwu/Desktop/aitown/frontend/src/hooks/useWebSocket.ts ), but the payload schema is incomplete for world deltas, innovation/pattern events, commands, and the frontend build is currently broken. |

### Systems That Should Not Be First-Class Mechanics

| System | Status | Audit |
| --- | --- | --- |
| Trading / Currency / Tax / Governance / Job Assignment / Explicit Economy | `OFF-SPEC` | The current backend still contains explicit barter, currency, tax, and governance mechanics. Those need to be removed as hardcoded systems and re-expressed as emergent outcomes of open-ended actions, beliefs, observation, and pattern detection. |

### Emergent-Only Systems That Must Not Be Hardcoded

These must emerge from the action interpreter, consequence engine, cognition, conversations, observation, innovation spread, and pattern detection. They should not exist as bespoke gameplay systems.

| System | Required Handling |
| --- | --- |
| Currency and economic systems | Remove direct hardcoded economy logic; allow exchange media, pricing habits, and economic norms to emerge from repeated actions and detected patterns. |
| Property rights and boundaries | Do not hardcode property systems; agents may mark, claim, defend, ignore, or negotiate boundaries through actions and social response. |
| Governance and leadership | Do not hardcode governance loops; leadership should emerge from influence, support, coordination, and pattern recognition. |
| Justice and conflict resolution | Do not build a justice subsystem; conflict, retaliation, mediation, shunning, repair, and punishment should emerge socially. |
| Social norms and expectations | Do not predefine norms beyond minimal simulation safety assumptions; norms should be detected from repeated behavior and reinforced socially. |
| Specialization and roles | Do not assign fixed jobs/roles; roles should emerge from repeated successful activity, reputation, and identity formation. |
| Technology and tools | Do not ship a crafting tech tree; tools and techniques should appear through open-ended actions, inventions, and adoption. |
| Institutions and gathering places | Do not hardcode institution classes as gameplay systems; institutions should emerge when repeated gatherings, rules, and projects stabilize. |
| Cultural practices and art | Do not pre-script culture systems; recurring rituals, art, stories, and aesthetics should arise from actions and imitation. |
| Trade networks and markets | Do not build market mechanics; repeated exchange at places/times should be recognized by pattern detection if they emerge. |
| Education and skill transfer | Do not build a formal education system; teaching, imitation, apprenticeship, and skill spread should happen through action + conversation. |
| Religion, ritual, and shared meaning | Do not build religion mechanics; shared meaning should emerge from reflection, gatherings, repeated symbolic acts, and cultural memory. |

## Deletion / Refactor Rule

When an existing code path hardcodes one of the emergent-only systems above, the implementation plan is to:

1. Delete the bespoke mechanic if it is only there to force emergence.
2. Preserve any reusable low-level primitives.
   Examples: inventories, pathfinding, world objects, memory storage, WebSocket transport.
3. Re-route the behavior through:
   - open-ended action generation
   - action interpretation
   - consequence application
   - observation / conversation
   - belief and identity updates
   - pattern detection
4. Only keep explicit code when it is truly foundational simulation infrastructure rather than a prebuilt social/economic mechanic.

## Open-Ended Action System Audit

Compared to `plan_md/polis-open-ended-action-system.md`, the codebase is missing the central contract that makes everything else work:

1. The current action interpreter schema does not match the required schema.
2. There is no `ActionResult` model with `feasible`, `success_chance`, `time_ticks`, `energy_cost`, `on_success`, `on_failure`, `observability`, `social_implications`, and `unlocks`.
3. There is no dedicated `ConsequenceEngine` that applies success and failure in a spec-compliant way.
4. Observers are not notified through a universal action-observation flow.
5. There is no innovation cascade tracker.
6. There is no latent possibility registry or world-change application layer.
7. The engine does not route every non-routine deliberate decision through the action interpreter.

Bottom line: the current code has a promising base, but the open-ended action system is still only a prototype, not the actual simulation backbone.

## Delivery Plan

The plan below is the shortest safe path to the requested end state: every required system built out, the open-ended action spec implemented exactly, the frontend rendering the results, and the app running cleanly.

### Phase 0: Stabilize The Project So It Can Be Built

Goal: make the repo runnable and verifiable before expanding features.

Deliverables:

1. Fix the frontend type/build break around conversation payloads and speech bubbles.
2. Make backend tests runnable through a single project command by fixing import paths and adding test runner instructions.
3. Add a smoke test that boots the engine, runs ticks, and validates WebSocket payload shape.
4. Add frontend smoke validation for `vite build`.

Acceptance:

- `npm run build` passes
- backend tests run from the repo root
- app boots and streams tick payloads without schema errors

### Phase 1: Replace Off-Spec Hardcoded Systems With The Real Simulation Backbone

Goal: remove or demote systems that conflict with the requested architecture.

Deliverables:

1. Remove direct economy/barter/tax/governance assumptions from the engine as first-class mechanics.
2. Keep social proposals, norms, institutions, and exchange only as things agents can propose or perform through open-ended actions.
3. Refactor world state so emergent systems live as discovered patterns, norms, institutions, and object/resource histories instead of bespoke subsystems.
4. Audit and remove bespoke logic for all emergent-only systems:
   - currency and economic systems
   - property rights and boundaries
   - governance and leadership
   - justice and conflict resolution
   - social norms and expectations
   - specialization and roles
   - technology and tools
   - institutions and gathering places
   - cultural practices and art
   - trade networks and markets
   - education and skill transfer
   - religion, ritual, and shared meaning
5. Keep only the substrate needed for those systems to emerge:
   - actions
   - consequences
   - memory
   - beliefs
   - relationships
   - world objects
   - pattern detection
   - frontend visualization

Acceptance:

- no direct “price crash”, “tax collection”, “trade system”, or “currency system” logic is required for simulation correctness
- those outcomes can only appear through actions plus pattern detection
- no bespoke subsystem remains for any emergent-only domain listed above

### Phase 2: Implement The Open-Ended Action System Exactly

Goal: make the action interpreter and consequence engine the true core of the sim.

Deliverables:

1. Create typed models for:
   - `ActionIntent`
   - `ActionEvaluation`
   - `ActionResult`
   - `WorldObject`
   - `WorldChange`
   - `ObservationRecord`
2. Rewrite the interpreter prompt and JSON contract to match `polis-open-ended-action-system.md`.
3. Add skill-aware success rolling and explicit success/failure outcomes.
4. Build a dedicated `ConsequenceEngine` that:
   - consumes materials
   - drains energy
   - creates portable and placed objects
   - applies world changes
   - updates skills
   - records knowledge gained
   - registers unlocks / latent possibilities
   - applies injuries on failure
   - notifies observers
5. Add an action queue so agents can begin, continue, and finish long actions over multiple ticks.
6. Add universal observation events so every visible action can ripple through attention, memory, belief, and innovation systems.

Acceptance:

- every deliberate non-routine action goes through the interpreter
- success/failure both change the world
- observations are emitted for nearby witnesses
- objects, terrain, and new possibilities persist in world state

### Phase 3: Complete Agent Cognition

Goal: finish the internal systems the action pipeline depends on.

Deliverables:

1. Expand drives to the requested set, including thirst and belonging-pressure equivalents, plus explicit energy/health coupling.
2. Replace `WorkingMemory` with a scored attention buffer supporting:
   - 5-7 active items
   - priorities
   - persistence for background worry
   - drive-forced insertions
3. Upgrade episodic memory creation so the same event can be encoded differently per witness through LLM-assisted subjective framing.
4. Add embedding-backed retrieval for memory relevance.
5. Improve belief extraction from repeated episodes and nightly reflection.
6. Add LLM-based mental model synthesis after significant interactions.
7. Complete identity tension updates and goal generation.
8. Expand skill memory into per-skill histories with attempts, successes, failures, enjoyment, difficulty, and recent practice.
9. Add uncertain and incorrect world understanding with confidence levels.

Acceptance:

- decision prompts can be built entirely from cognition layers
- agents remember, believe, misread, and update over time
- nightly reflection materially changes future behavior

### Phase 4: Rebuild The Decision Pipeline Around Novelty

Goal: stop using timed random “novel actions” and move to the required conscious/autopilot loop.

Deliverables:

1. Integrate the novelty detector directly into every agent tick.
2. Keep routine behavior fully deterministic when no novelty is present.
3. Build the single decision prompt constructor that gathers:
   - attention
   - drives
   - emotions
   - active goals
   - beliefs
   - mental models of involved agents
   - skill memory
   - world understanding
4. Make morning plan and evening reflection first-class inputs to routine selection and novelty.
5. Run inner voice generation at the requested cadence per agent.

Acceptance:

- no random one-off action interpreter calls
- agents deliberate only when novelty requires it
- routine/autopilot remains cheap and plausible

### Phase 5: Finish Social Dynamics

Goal: make social life run through awareness, conversations, overhearing, and avoidance as specified.

Deliverables:

1. Tighten awareness scoring and visibility ranges.
2. Expand interaction types to match the requested taxonomy.
3. Improve multi-party conversations and end conditions.
4. Ensure conversation consequences reliably update:
   - episodic memory
   - emotions
   - relationships
   - trust
   - beliefs
   - mental models
   - world understanding
   - social commitments
5. Upgrade overhearing fragments with low-confidence storage and name-triggered anxiety spikes.
6. Integrate avoidance into pathfinding so hostile agents visibly route around each other.

Acceptance:

- nearby agents notice and react to one another
- overheard fragments propagate misinformation and gossip
- avoidance affects actual movement paths

### Phase 6: Finish World Systems

Goal: make the world carry long-term emergent structure.

Deliverables:

1. Add a real `PatternDetector` that scans recent interpreted actions every 50 ticks.
2. Add a real `InnovationTracker` with inventor, witnesses, adopters, adoption rate, and parent-child innovation links.
3. Promote `created_objects` into a typed world-object registry with:
   - durability
   - effects
   - size
   - portability
   - owner
   - placed location
4. Add environmental world-change application:
   - terrain modification
   - new paths
   - boundary markers
   - resource shifts
   - structure modification
5. Finish time/environment coupling so weather and season affect drives, resource availability, action feasibility, and rendering.
6. Add avoidance-aware pathfinding plus common-route caching.

Acceptance:

- innovations and norms can be inspected over time
- objects decay and break
- weather and season matter mechanically

### Phase 7: Finish The Frontend

Goal: surface the full simulation on the frontend, not just a subset.

Deliverables:

1. Fix the current build break and keep the frontend green throughout development.
2. Extend WebSocket payloads to include:
   - world object deltas
   - action result events
   - innovation events
   - pattern detection events
   - timeline events
   - richer agent detail payloads
3. Add dynamic object rendering for portable/placed objects created by interpreted actions.
4. Finish agent sprite indicators for activity, distress, and selection.
5. Expand Live Feed filters and event categories.
6. Rework Inspector tabs to match the requested information architecture:
   - Status
   - Mind
   - Relationships
   - Skills & Creations
   - World Knowledge
   - Economics / Inventory
7. Add a dedicated World Evolution Timeline.
8. Add the Innovation Tree.
9. Extend Top Bar with food supply and institution count.
10. Refactor God Mode so injected events and free-text commands use the same backend action/event system, not off-spec bespoke systems.
11. Add weather particles and stronger day/night scene treatment.

Acceptance:

- every major backend system has a visible frontend representation
- frontend can show norms, institutions, innovations, objects, and agent cognition live

### Phase 8: Verification And Hardening

Goal: prove the build works and the simulation remains coherent.

Deliverables:

1. Backend unit tests for each cognition and world subsystem.
2. Integration tests for:
   - deliberate action -> interpretation -> consequence -> observer update
   - conversation -> consequence processing -> belief/model updates
   - innovation spread -> pattern detection -> frontend event payloads
3. Frontend build and smoke tests for major panels.
4. Long-run simulation soak test to verify no runaway errors.
5. Data migration and save/load compatibility for new world object and action history structures.

Acceptance:

- backend tests pass
- frontend build passes
- a long-running sim produces coherent objects, innovations, and timeline events without schema drift

## Exact Work Breakdown For The Open-Ended Action System

This is the implementation checklist for `polis-open-ended-action-system.md`.

### Backend

1. Add `backend/systems/open_action_models.py` with the full action/result/object schema.
2. Replace `backend/systems/action_interpreter.py` with a spec-matching interpreter that returns:
   - `feasible`
   - `why_not`
   - `success_chance`
   - `time_ticks`
   - `energy_cost`
   - `materials_consumed`
   - `on_success`
   - `on_failure`
   - `observability`
   - `social_implications`
   - `unlocks`
3. Add `backend/systems/consequence_engine.py`.
4. Add `backend/systems/innovation.py`.
5. Add world-state support for:
   - first-class objects
   - object lookup by location and owner
   - environmental changes
   - latent possibilities
   - innovation registry
6. Rewire the engine so deliberative actions always pass through:
   - novelty detection
   - decision prompt construction
   - action interpreter
   - consequence engine
   - observer notifications
   - innovation processing
   - pattern detection

### Frontend

1. Add world object types to frontend models.
2. Render objects from backend deltas.
3. Surface interpreted action outcomes in the feed.
4. Add innovation and pattern events to dashboard and timeline.
5. Add innovation tree UI from tracker data.

## Definition Of Done

The work is done only when all of the following are true:

1. Every system in the “Must Build” list is `COMPLETE`.
2. Every system in the “Do NOT Build” list is no longer a hardcoded first-class mechanic.
3. The open-ended action system from `plan_md/polis-open-ended-action-system.md` is fully implemented as the primary simulation backbone.
4. The frontend builds and renders:
   - world state
   - dynamic objects
   - agents
   - live feed
   - inspector
   - timeline
   - innovation tree
   - top bar
   - god mode
5. The backend runs, saves, loads, and streams cleanly over WebSocket.
6. The project has passing verification for backend and frontend.

## Recommended Execution Order

1. Phase 0
2. Phase 1
3. Phase 2
4. Phase 3
5. Phase 4
6. Phase 5
7. Phase 6
8. Phase 7
9. Phase 8

Do not start polishing frontend panels before Phases 2-6 are stable, or the UI work will be rebuilt twice.
