# Polis: The Open-Ended Action System

## The One Rule

There are no pre-built game mechanics. No crafting system. No trading system. No voting system. No skill tree. No building menu. There is only the Action Interpreter — a single system that evaluates any action any agent proposes, determines if it's physically possible, and applies consequences to the world.

Everything else — currency, governance, property, technology, culture, institutions — emerges from agents taking actions and other agents observing and responding.

---

## How It Works End-to-End

### Step 1: Agent Decides To Do Something

The agent's cognitive system (drives, emotions, beliefs, goals, reflection) produces a decision. The decision is a free-text description, not a selection from a menu.

Examples of decisions the LLM might generate:
- "I'll dig a shallow trench from the river to the farmable land to water crops"
- "I'm going to heat some clay from the riverbank in a fire to make a simple pot"
- "I'll offer to watch over the food storage tonight if someone gives me a meal"
- "I want to scratch tally marks on a stone to track who owes me what"
- "I'm going to pile rocks in a line to mark the boundary of what I consider my land"
- "I'll weave grass into a rough mat to sleep on instead of the bare ground"
- "I want to gather everyone at the square and propose that we share the large building"
- "I'm going to teach Jade how I set fishing lines — she's been struggling with food"
- "I'll refuse to contribute food to the shared pile until the others agree to a fair split"

None of these are pre-programmed action types. They're natural language descriptions of things a human might do in this situation.

### Step 2: The Action Interpreter Evaluates

The Action Interpreter is a single LLM call that acts as the world's physics engine, logic engine, and consequence calculator.

```python
class ActionInterpreter:
    
    async def evaluate(self, agent, action_description, world_state) -> ActionResult:
        
        prompt = f"""
You are the reality engine for a small-town survival simulation. 
Your job is to determine what happens when someone tries to do something.
Be realistic. Think like a physics simulation crossed with common sense.

═══ WHO IS DOING THIS ═══
Name: {agent.name}, Age: {agent.age}
Strength: {agent.physical_traits['strength']}/1.0
Endurance: {agent.physical_traits['endurance']}/1.0  
Dexterity: {agent.physical_traits['dexterity']}/1.0
Health: {agent.drives.health}/1.0
Energy: {agent.drives.energy}/1.0
Known skills and experience levels:
{agent.skill_memory.full_summary()}
Currently carrying: {agent.inventory}

═══ WHAT THEY WANT TO DO ═══
"{action_description}"

═══ WHERE THEY ARE ═══
Location: {agent.location}
Description: {world_state.locations[agent.location]['description']}
Resources available here: {world_state.get_resources_at(agent.location)}
Objects/structures here: {world_state.get_objects_at(agent.location)}
Other agents present: {world_state.get_agents_at(agent.location)}

═══ RELEVANT WORLD CONTEXT ═══
Weather: {world_state.weather}
Time of day: {world_state.time_of_day}
Season: {world_state.season}
Community rules that might apply: {world_state.constitution.get_relevant_rules(action_description)}

═══ INSTRUCTIONS ═══
Evaluate this action with REALISM and COMMON SENSE:

FEASIBILITY: Can this physically be done?
- Does the agent have the physical strength/dexterity?
- Are the necessary materials available at this location?
- Does the agent have enough energy?
- Does the time of day / weather allow it?
- Does the agent have relevant experience? (Inexperienced attempts should 
  have lower success chance, not be impossible)

EXECUTION: If feasible, what happens?
- What materials are consumed?
- How long does it take? (in simulation ticks, where 1 tick ≈ 10 minutes)
- What is the probability of success given the agent's skills?
- What does success produce or change?
- What does failure look like? (partial result? wasted materials? injury?)

CONSEQUENCES: What ripples outward?
- What can nearby agents observe?
- Does this create something new in the world?
- Does this change what's possible going forward?
- Does this set a social precedent?
- Does this violate any existing community rules or norms?

Be generous with feasibility — humans are creative and resourceful.
A first attempt at something should be possible but might produce a 
crude, fragile, or imperfect result. Mastery comes with practice.

Return JSON:
{{
    "feasible": true/false,
    "why_not": "if infeasible, the specific physical/logical reason",
    
    "success_chance": 0.0-1.0,
    "time_ticks": integer,
    "energy_cost": 0.0-1.0,
    
    "materials_consumed": {{
        "resource_name": amount
    }},
    
    "on_success": {{
        "description": "what happens if it works",
        "objects_created": [
            {{
                "name": "descriptive name",
                "description": "what it is, what it looks like",
                "category": "tool/structure/container/food/medicine/art/clothing/document/marker/furniture/mechanism/other",
                "effects": {{
                    "effect_name": value
                }},
                "durability": 0.0-1.0,
                "size": "tiny/small/medium/large/structure",
                "portable": true/false,
                "visual_description": "brief visual description for rendering"
            }}
        ],
        "resources_produced": {{
            "resource_name": amount
        }},
        "world_changes": [
            {{
                "type": "terrain_modification/new_path/building_modification/resource_change/boundary_marker/other",
                "description": "what changed in the world",
                "location": "where",
                "permanent": true/false,
                "visual_change": "how this looks different now"
            }}
        ],
        "skill_practiced": "name of skill being developed",
        "skill_difficulty": 0.0-1.0,
        "knowledge_gained": "what the agent learns from doing this, if anything"
    }},
    
    "on_failure": {{
        "description": "what happens if it fails",
        "materials_wasted": {{}},
        "partial_result": "anything produced even in failure, or null",
        "injury_risk": 0.0-1.0,
        "injury_description": "what kind of injury if unlucky"
    }},
    
    "observability": {{
        "who_can_see": "anyone at this location / nearby / nobody",
        "what_they_see": "description of what an observer would perceive",
        "noise_level": "silent/quiet/normal/loud",
        "duration_visible": "brief moment / ongoing process / permanent result"
    }},
    
    "social_implications": {{
        "rules_violated": ["any community norms this breaks"],
        "precedent": "what social expectation this establishes if it becomes common",
        "likely_reactions": "how others might feel about this"
    }},
    
    "unlocks": [
        "things that become possible now that weren't before"
    ]
}}
"""
        
        result = await llm_call(prompt)
        
        if not result["feasible"]:
            return ActionResult(
                success=False, 
                reason=result["why_not"],
                agent_learns="I tried but couldn't: " + result["why_not"]
            )
        
        # Roll for success
        skill_level = agent.skill_memory.get_skill_level(result["on_success"].get("skill_practiced", "general"))
        adjusted_chance = result["success_chance"] * (0.5 + skill_level * 0.5)
        succeeded = random.random() < adjusted_chance
        
        if succeeded:
            outcome = result["on_success"]
        else:
            outcome = result["on_failure"]
        
        return ActionResult(
            success=succeeded,
            result=result,
            outcome=outcome,
            time_ticks=result["time_ticks"],
            energy_cost=result["energy_cost"]
        )
```

### Step 3: Consequences Apply to the World

```python
class ConsequenceEngine:
    """
    Takes an ActionResult and modifies the world state accordingly.
    This is where actions become reality.
    """
    
    def apply(self, action_result, agent, world_state):
        
        if not action_result.success:
            self.apply_failure(action_result, agent, world_state)
            return
        
        outcome = action_result.outcome
        
        # Consume materials
        for resource, amount in action_result.result.get("materials_consumed", {}).items():
            source = agent.inventory if agent.has_item(resource) else world_state
            source.consume(resource, amount, agent.location)
        
        # Drain energy
        agent.drives.energy = max(0.0, agent.drives.energy - action_result.energy_cost)
        
        # Create new objects
        for obj_spec in outcome.get("objects_created", []):
            obj = WorldObject(
                id=generate_id(),
                name=obj_spec["name"],
                description=obj_spec["description"],
                category=obj_spec["category"],
                effects=obj_spec.get("effects", {}),
                durability=obj_spec.get("durability", 1.0),
                size=obj_spec.get("size", "small"),
                portable=obj_spec.get("portable", True),
                visual_description=obj_spec.get("visual_description", ""),
                created_by=agent.name,
                created_on=world_state.day_number,
                location=agent.location if not obj_spec.get("portable") else None,
                owner=agent.name
            )
            
            if obj.portable:
                agent.inventory.append(obj)
            else:
                world_state.add_object_to_location(obj, agent.location)
            
            # Register this object type as something that exists in the world
            world_state.known_object_types.add(obj.category, obj.name, obj_spec)
        
        # Produce resources
        for resource, amount in outcome.get("resources_produced", {}).items():
            agent.add_to_inventory(resource, amount)
        
        # Apply world changes
        for change in outcome.get("world_changes", []):
            world_state.apply_environmental_change(change)
        
        # Update agent's skill
        if outcome.get("skill_practiced"):
            agent.skill_memory.record_success(
                outcome["skill_practiced"],
                outcome.get("skill_difficulty", 0.5)
            )
        
        # Record knowledge gained
        if outcome.get("knowledge_gained"):
            agent.world_understanding.learn(outcome["knowledge_gained"])
        
        # Register new possibilities
        for unlock in action_result.result.get("unlocks", []):
            world_state.latent_possibilities.add(unlock)
        
        # CRITICAL: Notify observers
        self.notify_observers(action_result, agent, world_state)
    
    def notify_observers(self, action_result, acting_agent, world_state):
        """
        Other agents perceive the action and its results.
        This is how innovations spread, norms form, and social
        dynamics emerge from individual actions.
        """
        
        observability = action_result.result.get("observability", {})
        who_sees = observability.get("who_can_see", "nearby")
        what_they_see = observability.get("what_they_see", "")
        
        if who_sees == "nobody":
            return
        
        observers = world_state.get_agents_who_can_observe(
            acting_agent.location, 
            who_sees,
            observability.get("noise_level", "normal")
        )
        
        for observer in observers:
            if observer.name == acting_agent.name:
                continue
            
            # Create an observation for this agent
            observation = {
                "who": acting_agent.name,
                "what": what_they_see,
                "result_visible": action_result.success,
                "objects_visible": [
                    obj["name"] for obj in 
                    action_result.outcome.get("objects_created", [])
                    if obj.get("size") != "tiny"
                ],
                "location": acting_agent.location,
                "tick": world_state.current_tick
            }
            
            # Push into the observer's attention system
            observer.attention.push(
                f"{acting_agent.name} is {what_they_see}",
                priority=0.4
            )
            
            # Store as an episodic memory
            observer.episodic_memory.append(Episode(
                content=f"I saw {acting_agent.name} {what_they_see}",
                agents_involved=[acting_agent.name],
                location=acting_agent.location,
                memory_type="observation",
                emotional_intensity=0.2
            ))
            
            # The observer might react — this could trigger THEIR decision system
            # "I saw John build a sled. I want one too."
            # "I saw Marcus take food from the shared pile at night. That's not right."
            # "I saw Oleg teaching Tom how to build. Maybe he'd teach me too."
    
    def apply_failure(self, action_result, agent, world_state):
        """Handle failed actions — still has consequences."""
        
        outcome = action_result.outcome  # The on_failure block
        
        # Waste materials
        for resource, amount in outcome.get("materials_wasted", {}).items():
            agent.consume(resource, amount)
        
        # Possible injury
        if outcome.get("injury_risk", 0) > 0:
            if random.random() < outcome["injury_risk"]:
                agent.drives.health -= 0.1
                agent.episodic_memory.append(Episode(
                    content=f"I hurt myself trying to {action_result.original_action}: {outcome['injury_description']}",
                    emotional_valence=-0.5,
                    emotional_intensity=0.6,
                    primary_emotion="pain"
                ))
        
        # Partial results
        if outcome.get("partial_result"):
            # Even failure produces something sometimes
            pass
        
        # Record the failure — skill development happens through failure too
        skill = action_result.result["on_success"].get("skill_practiced")
        if skill:
            agent.skill_memory.record_failure(skill)
        
        # Emotional impact of failure
        agent.emotional_state.apply_event("task_failure", intensity=0.3)
        
        # Observers see the failure too
        self.notify_observers(action_result, agent, world_state)
```

### Step 4: The Innovation Cascade

When an observer sees something new, their cognitive system processes it. This is where individual inventions become cultural practices.

```python
class InnovationCascade:
    """
    Tracks how new ideas, techniques, and practices spread 
    through the community via observation and conversation.
    """
    
    def process_observed_innovation(self, observer, innovator, innovation):
        """
        An agent saw someone do something new or create something new.
        How do they respond?
        """
        
        # Does this relate to one of my unmet needs?
        relevance_to_needs = self.assess_need_relevance(observer, innovation)
        
        # Am I capable of doing something similar?
        capability_match = self.assess_capability(observer, innovation)
        
        # Do I respect/trust the innovator?
        relationship = observer.get_relationship(innovator.name)
        trust_in_innovator = relationship.trust if relationship else 0.3
        
        # Based on personality, how do I react to novelty?
        openness = observer.personality["openness"]
        
        # Calculate adoption likelihood
        adoption_score = (
            relevance_to_needs * 0.35 +
            capability_match * 0.2 +
            trust_in_innovator * 0.15 +
            openness * 0.15 +
            innovation.get("visible_benefit", 0.5) * 0.15
        )
        
        if adoption_score > 0.5:
            # Agent wants to try this themselves
            observer.pending_goals.append({
                "type": "imitate_innovation",
                "description": f"Try to {innovation['description']} like {innovator.name} did",
                "inspired_by": innovator.name,
                "priority": adoption_score
            })
        
        elif adoption_score > 0.3:
            # Agent is curious — will ask about it
            observer.pending_goals.append({
                "type": "ask_about_innovation",
                "description": f"Ask {innovator.name} about {innovation['name']}",
                "priority": adoption_score * 0.7
            })
        
        else:
            # Agent notes it but isn't interested
            # Still stored in memory — might become relevant later
            pass
        
        # Track the innovation's spread through the population
        world_state.innovation_tracker.record_observation(
            innovation_id=innovation["id"],
            observer=observer.name,
            reaction="adopt" if adoption_score > 0.5 else "curious" if adoption_score > 0.3 else "noted"
        )
```

### Step 5: Pattern Detection (Emergent Systems Recognition)

The simulation watches for repeated patterns that indicate a new system has emerged.

```python
class PatternDetector:
    """
    Runs every 50 ticks. Scans recent actions for patterns that 
    indicate emergent systems — economic, social, political, cultural.
    When detected, registers them in the world constitution as
    de facto norms or institutions.
    """
    
    def scan_for_patterns(self, world_state, action_log):
        
        recent_actions = action_log.get_last_n_ticks(200)  # ~2 game days
        
        # === ECONOMIC PATTERNS ===
        
        # Currency emergence: Is a specific item being used as a medium of exchange?
        trade_actions = [a for a in recent_actions if "trade" in a.description.lower() or "exchange" in a.description.lower() or "give" in a.description.lower()]
        if len(trade_actions) > 5:
            media = self.find_common_exchange_medium(trade_actions)
            if media and not world_state.constitution.economic_rules.get("currency"):
                world_state.constitution.economic_rules["currency"] = {
                    "item": media,
                    "emerged_on": world_state.day_number,
                    "status": "informal",
                    "description": f"Agents have been consistently using {media} as a medium of exchange"
                }
                self.broadcast_world_event(f"A de facto currency has emerged: {media} are now commonly used for trade")
        
        # Market location: Is trading concentrating at one location?
        trade_locations = [a.location for a in trade_actions]
        if trade_locations:
            most_common = max(set(trade_locations), key=trade_locations.count)
            frequency = trade_locations.count(most_common) / len(trade_locations)
            if frequency > 0.5 and not world_state.has_institution("marketplace"):
                world_state.register_institution({
                    "name": "Marketplace",
                    "type": "economic",
                    "location": most_common,
                    "description": f"Trading has concentrated at {most_common}",
                    "emerged_on": world_state.day_number,
                    "status": "informal"
                })
        
        # === SOCIAL PATTERNS ===
        
        # Regular gatherings: Are agents meeting at the same place at the same time?
        gathering_actions = [a for a in recent_actions if a.agent_count_at_location > 5]
        if gathering_actions:
            gathering_times = [(a.location, a.time_of_day) for a in gathering_actions]
            common_gathering = max(set(gathering_times), key=gathering_times.count)
            frequency = gathering_times.count(common_gathering)
            if frequency > 3 and not world_state.has_norm("regular_gathering"):
                world_state.constitution.social_norms.append({
                    "name": "Regular Gathering",
                    "description": f"The community gathers at {common_gathering[0]} during {common_gathering[1]}",
                    "emerged_on": world_state.day_number,
                    "adherence_rate": frequency / len(set(a.tick for a in gathering_actions))
                })
        
        # Role specialization: Is someone spending >60% of their time on one activity?
        for agent in world_state.agents:
            dominant_activity = agent.skill_memory.get_dominant_activity(last_n_days=5)
            if dominant_activity and dominant_activity["time_fraction"] > 0.6:
                if not agent.identity.role_in_community:
                    role_name = dominant_activity["activity_name"]
                    agent.identity.role_in_community = role_name
                    
                    if not world_state.has_recognized_role(role_name):
                        world_state.register_role({
                            "name": role_name,
                            "held_by": agent.name,
                            "emerged_on": world_state.day_number,
                            "description": f"{agent.name} has become the community's {role_name}"
                        })
        
        # Leadership emergence: Is one agent consistently influencing group decisions?
        influence_scores = self.calculate_influence_scores(recent_actions, world_state)
        top_influencer = max(influence_scores, key=influence_scores.get)
        if influence_scores[top_influencer] > 0.6 and not world_state.constitution.governance_rules.get("leader"):
            world_state.constitution.governance_rules["informal_leader"] = {
                "agent": top_influencer,
                "emerged_on": world_state.day_number,
                "influence_score": influence_scores[top_influencer],
                "status": "informal",
                "description": f"{top_influencer} has emerged as the community's informal leader"
            }
        
        # Norm emergence: Is a behavior being repeated by multiple agents?
        behavior_counts = self.count_behavior_patterns(recent_actions)
        for behavior, data in behavior_counts.items():
            if data["unique_agents"] > 7 and data["total_count"] > 10:
                if not world_state.has_norm(behavior):
                    world_state.constitution.social_norms.append({
                        "name": behavior,
                        "description": f"Multiple agents regularly {behavior}",
                        "adherence_rate": data["unique_agents"] / len(world_state.agents),
                        "emerged_on": world_state.day_number
                    })
        
        # === CONFLICT PATTERNS ===
        
        # Recurring disputes: Are the same agents or same issues causing repeated conflict?
        arguments = [a for a in recent_actions if "argument" in a.action_type or "dispute" in a.description.lower()]
        if len(arguments) > 3:
            common_topics = self.extract_dispute_topics(arguments)
            for topic, count in common_topics.items():
                if count > 2:
                    world_state.active_tensions.append({
                        "topic": topic,
                        "frequency": count,
                        "agents_involved": self.get_disputants(arguments, topic),
                        "detected_on": world_state.day_number
                    })
        
        # === INNOVATION TRACKING ===
        
        # Technology adoption: How many agents have adopted each innovation?
        for innovation_id, data in world_state.innovation_tracker.items():
            adoption_rate = data["adopters"] / len(world_state.agents)
            if adoption_rate > 0.3 and not data.get("registered_as_common"):
                data["registered_as_common"] = True
                world_state.common_practices.append({
                    "name": data["name"],
                    "adoption_rate": adoption_rate,
                    "originated_by": data["inventor"],
                    "description": data["description"]
                })
```

---

## How This Reflects On The Frontend

### The World View (Main Isometric Scene)

The world view needs to visually reflect emergent changes that nobody pre-programmed.

#### Dynamic Object Rendering

When agents create objects, they appear in the world. The rendering system handles this through a category-based visual system:

```python
VISUAL_CATEGORIES = {
    "tool": {
        "icon": "🔧",
        "sprite_base": "tool_generic",
        "color_tint": "#8B7355",  # Brown/wooden
        "size_on_map": "tiny_icon",  # Floats near owner or sits at location
    },
    "structure": {
        "icon": "🏗️",
        "sprite_base": "structure_generic", 
        "color_tint": "#A0A0A0",  # Gray/stone
        "size_on_map": "building_overlay",  # Modifies existing location tile
    },
    "container": {
        "icon": "📦",
        "sprite_base": "container_generic",
        "color_tint": "#DEB887",
        "size_on_map": "small_object",
    },
    "food": {
        "icon": "🍖",
        "sprite_base": "food_generic",
        "color_tint": "#90EE90",
        "size_on_map": "tiny_icon",
    },
    "marker": {
        "icon": "🪨",
        "sprite_base": "marker_generic",
        "color_tint": "#808080",
        "size_on_map": "ground_overlay",  # Flat on the ground
    },
    "art": {
        "icon": "🎨",
        "sprite_base": "art_generic",
        "color_tint": "#FF69B4",
        "size_on_map": "small_object",
    },
    "document": {
        "icon": "📜",
        "sprite_base": "document_generic",
        "color_tint": "#FFFACD",
        "size_on_map": "tiny_icon",
    },
    "clothing": {
        "icon": "👕",
        "sprite_base": "clothing_generic",
        "color_tint": "#DDA0DD",
        "size_on_map": "equipped",  # Shows on agent sprite
    },
    "furniture": {
        "icon": "🪑",
        "sprite_base": "furniture_generic",
        "color_tint": "#D2B48C",
        "size_on_map": "small_object",
    },
    "mechanism": {
        "icon": "⚙️",
        "sprite_base": "mechanism_generic",
        "color_tint": "#B0C4DE",
        "size_on_map": "medium_object",
    },
    "medicine": {
        "icon": "🌿",
        "sprite_base": "medicine_generic",
        "color_tint": "#228B22",
        "size_on_map": "tiny_icon",
    }
}
```

#### What Changes Visually As The Simulation Progresses

**Day 1-3:** The town looks empty. Raw buildings, wild land, agents wandering without clear purpose. No objects. No modifications. The isometric scene is pristine and unused.

**Day 4-7:** Objects start appearing. A crude stone tool sits outside a building. Boundary markers appear — rocks piled along invisible property lines. A fire pit appears in the town square (someone made it). Drying racks for fish near the river. The world starts looking inhabited.

**Day 7-14:** Buildings get claimed — small visual indicators show ownership (a colored flag or sign sprite on the building). A trading area forms at one location — objects pile up there visually. Paths between frequently visited locations start looking worn (subtle tile tint change on high-traffic routes). Gardens appear on farmland — tilled soil tiles replace wild grass.

**Day 14-30:** The town is transformed. Some buildings have been modified (expanded, decorated, repurposed — shown through overlay sprites). A marketplace has formed with visible goods on display. Boundary markers have been formalized into fences or walls. Art might appear on buildings (colored overlay). Infrastructure that agents built — irrigation channels (line sprites from river to farm), storage structures, gathering spaces — is visible on the map.

#### Dynamic Location Labels

Locations start unnamed. As agents designate purposes for buildings, labels appear:

```
Day 1:  "Empty Building (North)"
Day 5:  "Empty Building (North) — Claimed by Oleg"
Day 10: "Oleg's Workshop"
Day 20: "The Workshop — Built and operated by Oleg. Tom sometimes works here too."
```

The label evolves based on what agents actually do there, not based on a pre-assigned function.

#### Visual Indicators of Emergent Systems

When the Pattern Detector identifies emergent systems, the frontend reflects them:

**Currency in use:** When agents trade, if a recognized currency is being used, the transaction animation shows the currency icon (shell icon, for example) instead of a generic trade icon.

**Marketplace:** When a location is recognized as a marketplace, it gets a subtle visual enhancement — a colored border, a small market stall sprite overlay, or a trade icon pinned to the building.

**Regular gatherings:** When a gathering norm is detected, the location where gatherings happen gets a subtle "gathering spot" indicator (a small campfire icon or bench icon).

**Territory/property:** When boundaries are established, faint colored outlines or dotted lines appear on the ground showing claimed areas. Different agents' claims have different colors matching their character color.

**Social tension:** When the Pattern Detector identifies active tensions, subtle visual cues appear — agents in conflict might have a small red indicator when near each other. The connection line between them pulses red.

---

### The Dashboard (Inspector Panels)

#### Live Feed — Now Shows Emergent Events

The live feed must surface emergent system events alongside individual actions:

```
🏃 [Day 7, 2:15 PM] John Harlow walked to forest edge
🔨 [Day 7, 2:20 PM] John Harlow is building something — "a crude drag-sled from branches and vines"
✅ [Day 7, 3:45 PM] John Harlow successfully built: Crude Drag-Sled
        "A rough frame of branches tied with vines. Can drag loads along the ground."
        → INNOVATION: First transport device in the community
👀 [Day 7, 3:45 PM] Tom Kowalski observed John building the drag-sled
💭 [Day 7, 3:46 PM] Tom Kowalski: "That's clever. I could use something like that."

📊 [Day 8, Evening] PATTERN DETECTED: Currency Emergence
        River shells are being consistently used as a medium of exchange.
        First used by Mei Chen on Day 5. Now accepted by 8 of 15 agents.

📊 [Day 10, Evening] PATTERN DETECTED: Role Specialization
        John Harlow has become the community's farmer (68% of time on farming)
        Oleg Petrov has become the community's builder (72% of time on building)
        Amara Osei has become the community's healer (55% of time on healing)

📊 [Day 12, Evening] PATTERN DETECTED: Informal Leadership
        Eleanor Voss has emerged as the community's informal leader.
        Influence score: 0.72 — she is referenced in the decisions of 11 agents.

🏛️ [Day 14, 5:30 PM] INSTITUTION FORMED: Evening Gathering
        The community regularly gathers at Town Square during evening hours.
        Attendance rate: 80%. Organized informally by Daniel Park.

⚖️ [Day 18, 6:00 PM] NORM ESTABLISHED: Property Respect
        "Don't take from someone's claimed area without asking"
        Emerged from 3 disputes over the past week. Now observed by 12 of 15 agents.

🔬 [Day 22, Morning] INNOVATION SPREADING: Clay Pottery
        Jade Reeves invented clay pottery on Day 19.
        Now adopted by: Jade, Lisa, Mei (3 of 15 agents)
        Curious but haven't tried: Tom, Sarah (2 agents)
```

**Feed filter additions:**
- All | Actions | Thoughts | Social | Economic | 🆕 **Innovations** | 🆕 **Patterns** | 🆕 **Institutions**

#### Agent Inspector — New Tabs for Open-Ended World

##### Tab: Skills & Creations

Shows what this agent has discovered they're good at and what they've made.

```
╔══════════════════════════════════════════╗
║  SKILLS                                  ║
╠══════════════════════════════════════════╣
║                                          ║
║  ████████████░░ Farming       0.72       ║
║  Attempts: 45  Successes: 38             ║
║  Enjoyment: ★★★★☆                       ║
║  "My strongest skill. Learned from       ║
║   my father."                            ║
║                                          ║
║  ██████░░░░░░░░ Tool-Making   0.35       ║
║  Attempts: 8   Successes: 5              ║
║  Enjoyment: ★★★☆☆                       ║
║  "Getting better. The drag-sled was      ║
║   my first real creation."               ║
║                                          ║
║  ███░░░░░░░░░░░ Fishing       0.18       ║
║  Attempts: 4   Successes: 2              ║
║  Enjoyment: ★★☆☆☆                       ║
║  "Not my strength but it feeds me."      ║
║                                          ║
╠══════════════════════════════════════════╣
║  THINGS I'VE CREATED                     ║
╠══════════════════════════════════════════╣
║                                          ║
║  🛷 Crude Drag-Sled (Day 7)              ║
║    Transport capacity x2                 ║
║    Durability: ████░░ 60%                ║
║    "Branches and vines. Gets the job     ║
║     done but needs constant repair."     ║
║                                          ║
║  🏗️ Irrigation Trench (Day 12)           ║
║    Farm water supply: reliable           ║
║    "Dug from river to north field.       ║
║     Took two days. Worth it."            ║
║                                          ║
╚══════════════════════════════════════════╝
```

##### Tab: World Knowledge

What this agent knows about the world — which may differ from what other agents know.

```
╔══════════════════════════════════════════╗
║  MY MAP KNOWLEDGE          67% explored  ║
╠══════════════════════════════════════════╣
║                                          ║
║  ✅ Town Square — Central gathering spot ║
║  ✅ Forest Edge — Wood, berries, herbs   ║
║  ✅ River — Water, fish, clay            ║
║  ✅ North Farmland — I farm here         ║
║  ✅ Oleg's Workshop — Tools and repairs  ║
║  ✅ Trading Post (Mei) — Buy and sell    ║
║  ❓ Hill Overlook — Haven't been there   ║
║  ❓ South Field — Heard there's good     ║
║     soil but haven't checked             ║
║                                          ║
╠══════════════════════════════════════════╣
║  COMMUNITY RULES I KNOW ABOUT           ║
╠══════════════════════════════════════════╣
║                                          ║
║  • Don't take from claimed areas         ║
║    (Learned: Day 9, from dispute)        ║
║  • Everyone contributes to shared food   ║
║    (Learned: Day 6, Eleanor proposed)    ║
║  • Shells are used for trading           ║
║    (Learned: Day 8, from Mei)            ║
║  • Gatherings happen at the square       ║
║    most evenings                         ║
║    (Observed: Day 10 onward)             ║
║                                          ║
╠══════════════════════════════════════════╣
║  WHO DOES WHAT (my understanding)        ║
╠══════════════════════════════════════════╣
║                                          ║
║  John — Farmer (me)                      ║
║  Oleg — Builder, repairs things          ║
║  Mei — Trader, runs the market           ║
║  Amara — Healer, knows herbs             ║
║  Eleanor — Runs the meetings             ║
║  Ricky — Social, everyone talks to him   ║
║  Clara — Writes things down              ║
║  Jake — ??? (odd jobs, seems lost)       ║
║                                          ║
╚══════════════════════════════════════════╝
```

##### Updated Mind Tab — Now Shows Reasoning About World-Changing Decisions

```
╔══════════════════════════════════════════╗
║  CURRENT THOUGHT                         ║
║                                          ║
║  "If I could find a way to store water   ║
║   near the field instead of hauling it   ║
║   from the river every morning, I could  ║
║   grow twice as much food."              ║
║                                          ║
╠══════════════════════════════════════════╣
║  RECENT INNER MONOLOGUE                  ║
╠══════════════════════════════════════════╣
║                                          ║
║  💭 "The clay near the river... Jade     ║
║     made a pot from it. Could I make     ║
║     something bigger? A basin?"          ║
║     [3:20 PM — Realization]              ║
║                                          ║
║  💭 "My back is killing me. These trips  ║
║     to the river are the worst part."    ║
║     [2:45 PM — Physical]                 ║
║                                          ║
║  💭 "Tom's been watching me work. Maybe  ║
║     I should show him what I know. Two   ║
║     farmers would be better than one."   ║
║     [1:30 PM — Self-talk]               ║
║                                          ║
║  💭 "The soil smells different after     ║
║     rain. Dad used to say that meant     ║
║     good planting."                      ║
║     [10:00 AM — Nostalgia]              ║
║                                          ║
╠══════════════════════════════════════════╣
║  ACTIVE GOALS                            ║
╠══════════════════════════════════════════╣
║                                          ║
║  1. 🔴 Find a way to irrigate the field ║
║     Priority: HIGH                       ║
║     "Hauling water is killing me. There  ║
║      must be a better way."              ║
║                                          ║
║  2. 🟡 Build a better storage for crops ║
║     Priority: MEDIUM                     ║
║     "Food spoils too fast in the open."  ║
║                                          ║
║  3. 🟢 Teach Tom basic farming          ║
║     Priority: LOW                        ║
║     "Having help would change everything"║
║                                          ║
╠══════════════════════════════════════════╣
║  EVENING REFLECTION (Last Night)         ║
╠══════════════════════════════════════════╣
║                                          ║
║  "Day 11. The irrigation trench idea     ║
║   kept me up. If I dig from the river    ║
║   bend where it's closest... maybe 20   ║
║   paces of trench. Hard work but I've    ║
║   done harder. I'll start tomorrow.      ║
║                                          ║
║   The community is starting to feel      ║
║   like something real. Eleanor runs the  ║
║   meetings but I'm not sure anyone       ║
║   actually chose her. Sarah's been       ║
║   making noises about that.              ║
║                                          ║
║   Ricky left extra bread at my door      ║
║   again. I know it's him. I don't know   ║
║   how to feel about that."               ║
║                                          ║
╚══════════════════════════════════════════╝
```

#### New Dashboard Panel: World Evolution Timeline

A dedicated panel that tracks how the world has changed over time — the emergent systems, institutions, innovations, and norms that nobody programmed.

```
╔══════════════════════════════════════════════════════╗
║  WORLD EVOLUTION TIMELINE                            ║
╠══════════════════════════════════════════════════════╣
║                                                      ║
║  Day 1  ○ 15 agents arrive. No structures claimed.  ║
║           No rules. No roles. No economy.            ║
║                                                      ║
║  Day 2  ● First shelter claims                       ║
║           John claims north farmland                 ║
║           Oleg claims building with best workspace   ║
║                                                      ║
║  Day 3  ● First successful harvest                   ║
║           John produces food from wild plants         ║
║           First trades: food for labor               ║
║                                                      ║
║  Day 5  ● Currency emergence begins                  ║
║           Mei starts accepting river shells           ║
║                                                      ║
║  Day 6  ● First community gathering                  ║
║           Eleanor organizes discussion at square      ║
║           Proposal: share food communally            ║
║           VOTE: 9 for, 4 against, 2 absent           ║
║                                                      ║
║  Day 7  ★ INNOVATION: Drag-Sled (John Harlow)       ║
║           First transport device                     ║
║                                                      ║
║  Day 9  ● First property dispute                     ║
║           Tom & Marcus both claim same building      ║
║           Daniel mediates                            ║
║           NORM ESTABLISHED: "Claim by first use"     ║
║                                                      ║
║  Day 10 ● Role specialization detected               ║
║           3 agents have dominant roles               ║
║                                                      ║
║  Day 12 ★ INNOVATION: Irrigation Trench (John)      ║
║           Farm productivity doubles                  ║
║                                                      ║
║  Day 14 ● INSTITUTION: Evening Gathering             ║
║           Regular community meetings formalized      ║
║                                                      ║
║  Day 16 ● Shell currency now accepted by 80%         ║
║           ECONOMY: Formal currency established       ║
║                                                      ║
║  Day 18 ● INSTITUTION: Marketplace at Trading Post   ║
║           Mei operates daily                         ║
║                                                      ║
║  Day 19 ★ INNOVATION: Clay Pottery (Jade Reeves)    ║
║           Storage and cooking capability             ║
║                                                      ║
║  Day 22 ● First theft incident                       ║
║           Community debates justice response         ║
║           NORM ESTABLISHED: "Theft is punished       ║
║           by community service"                      ║
║                                                      ║
║  Day 25 ● POLITICAL: Sarah challenges Eleanor's     ║
║           leadership. Election proposed.             ║
║                                                      ║
║  Day 28 ● First election held                        ║
║           Eleanor: 8 votes. Sarah: 7 votes.          ║
║           GOVERNANCE: Elected leadership             ║
║           established with 30-day terms.             ║
║                                                      ║
╚══════════════════════════════════════════════════════╝
```

This timeline is the ultimate screenshot. Someone sees a simulation that went from "15 strangers with nothing" to "a functioning society with currency, governance, property rights, specialized roles, justice norms, and democratic elections" in 28 days — all emergent, all unscripted — and they share it immediately.

#### New Dashboard Panel: Innovation Tree

Shows what's been invented and how innovations built on each other:

```
╔══════════════════════════════════════════╗
║  INNOVATION TREE                         ║
╠══════════════════════════════════════════╣
║                                          ║
║  Wild Plant Gathering (Day 1)            ║
║  └── Farming (Day 3, John)               ║
║      └── Irrigation (Day 12, John)       ║
║      └── Seed Selection (Day 15, John)   ║
║                                          ║
║  Wood Gathering (Day 1)                  ║
║  └── Shelter Building (Day 2, Oleg)      ║
║  └── Tool Making (Day 4, Oleg)           ║
║      └── Drag-Sled (Day 7, John)         ║
║      └── Better Axes (Day 11, Oleg)      ║
║                                          ║
║  Clay Gathering (Day 6, Jade)            ║
║  └── Clay Pottery (Day 19, Jade)         ║
║      └── Water Storage (Day 23, John)    ║
║      └── Cooking Pots (Day 24, Lisa)     ║
║                                          ║
║  Herb Gathering (Day 3, Amara)           ║
║  └── Herbal Medicine (Day 5, Amara)      ║
║  └── Herb Cultivation (Day 20, Amara)    ║
║                                          ║
║  Fish Catching (Day 2, Marcus)           ║
║  └── Fish Traps (Day 10, Marcus)         ║
║  └── Fish Drying (Day 14, Lisa)          ║
║                                          ║
╚══════════════════════════════════════════╝
```

This shows the technology tree that the agents built themselves. Nobody designed this tree. It emerged from agents solving problems, observing each other, and building on previous inventions. That's the tweet — "My AI agents invented a technology tree. I didn't program a single recipe."

---

## Summary: What You Build vs What Emerges

### What You Build (Code These Systems):
1. Action Interpreter — evaluates any proposed action
2. Consequence Engine — applies results to the world
3. Pattern Detector — recognizes emergent systems
4. Observer Notification — tells other agents what happened
5. Innovation Cascade — tracks how inventions spread
6. World State — tracks everything that exists
7. Visual Category System — renders any object by category
8. Dashboard Panels — displays emergent data

### What Emerges (DO NOT Code These):
- Currency and economic systems
- Property rights and boundaries
- Governance and leadership
- Justice and conflict resolution
- Social norms and expectations
- Specialization and roles
- Technology and tools
- Institutions and gathering places
- Cultural practices and art
- Trade networks and markets
- Education and skill transfer
- Religion, ritual, and shared meaning

The entire point of Polis is that second list. If you find yourself coding any item from the second list as a dedicated system, stop. Ask: "Would the Action Interpreter handle this if an agent proposed it?" The answer should be yes.
