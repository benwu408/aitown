# Agent Interaction System

## Core Principle

Humans don't decide to talk to people through logical reasoning. We see someone, something fires in our brain — familiarity, attraction, anxiety, need, curiosity, obligation — and we either approach them or avoid them. The decision to interact happens before conscious thought.

This system models that. Interaction isn't triggered by a schedule or a random roll. It's triggered by the intersection of proximity, drives, emotional state, relationship, and current mental state. Two agents standing near each other doesn't mean they talk. Two agents with unresolved tension who happen to be in the same room — that's a conversation waiting to happen.

---

## Proximity and Awareness

### Who Can See Whom

Agents can only interact with agents they're aware of. Awareness is determined by physical proximity and attention.

```python
class AwarenessSystem:
    
    # Detection ranges (in tile units)
    VISUAL_RANGE = 8           # Can see agents within 8 tiles in open areas
    INDOOR_RANGE = 4           # Can see everyone inside the same building
    CONVERSATION_RANGE = 2     # Must be within 2 tiles to talk
    OVERHEAR_RANGE = 3         # Can overhear conversations within 3 tiles
    
    def get_perceived_agents(self, agent, all_agents, world_state) -> list:
        """
        Returns agents that this agent is currently aware of,
        sorted by how much attention they're drawing.
        """
        perceived = []
        
        for other in all_agents:
            if other == agent:
                continue
            
            distance = world_state.get_distance(agent.location, other.location)
            same_building = world_state.same_building(agent.location, other.location)
            
            # Basic visibility check
            if same_building:
                visible = distance <= self.INDOOR_RANGE
            else:
                visible = distance <= self.VISUAL_RANGE
            
            if not visible:
                continue
            
            # Calculate attention weight — how much this person draws the agent's eye
            attention = self.calculate_attention_weight(agent, other, distance)
            
            perceived.append({
                "agent": other,
                "distance": distance,
                "attention_weight": attention,
                "can_talk": distance <= self.CONVERSATION_RANGE,
                "can_overhear": distance <= self.OVERHEAR_RANGE,
                "same_building": same_building
            })
        
        # Sort by attention — most attention-drawing first
        perceived.sort(key=lambda x: -x["attention_weight"])
        
        return perceived
    
    def calculate_attention_weight(self, agent, other, distance) -> float:
        """
        How much does this other agent draw my attention?
        Higher = more likely I'll notice them and potentially interact.
        """
        weight = 0.0
        
        # Relationship strength — we notice people we have strong feelings about
        rel = agent.get_relationship(other.name)
        if rel:
            weight += abs(rel.sentiment) * 0.3  # Strong feelings (positive OR negative) draw attention
            
            # Unresolved issues are attention magnets
            if rel.unresolved_issues:
                weight += 0.3
        
        # Closeness — people right next to you demand more attention
        proximity_factor = 1.0 / (1.0 + distance * 0.3)
        weight += proximity_factor * 0.2
        
        # They're doing something unusual — draws the eye
        if other.current_action and other.current_action.is_novel:
            weight += 0.2
        
        # They're in emotional distress — empathetic agents notice
        if other.emotional_state.is_visibly_distressed():
            weight += agent.personality["agreeableness"] * 0.3
        
        # I have a goal that involves them
        for goal in agent.current_goals:
            if other.name in goal.involves_agents:
                weight += 0.4
        
        # I just heard something about them (gossip priming)
        recent_mentions = agent.episodic_memory.count_recent_mentions(other.name, last_n_ticks=50)
        if recent_mentions > 0:
            weight += min(recent_mentions * 0.1, 0.3)
        
        # They're a stranger or unfamiliar — curiosity for open agents, avoidance for closed
        if rel is None or rel.familiarity < 0.2:
            if agent.personality["openness"] > 0.6:
                weight += 0.15  # Curious about new people
            else:
                weight -= 0.1  # Avoid unfamiliar people
        
        # Family/partner — always high baseline attention
        if rel and rel.relationship_type in ["family", "partner"]:
            weight += 0.2
        
        return max(0.0, weight)
```

---

## The Interaction Decision

### When Does An Agent Initiate Interaction?

Every tick, for each agent that's aware of nearby agents, the system evaluates whether they would initiate interaction. This is NOT an LLM call — it's a fast heuristic that fires before the LLM gets involved.

```python
class InteractionDecider:
    
    def should_initiate_interaction(self, agent, perceived_agents) -> tuple[bool, str, str]:
        """
        Returns (should_interact, target_agent_name, reason)
        
        This runs every tick for every agent with nearby agents.
        Must be fast — no LLM calls.
        """
        
        if not perceived_agents:
            return False, None, None
        
        # Can't interact if already in a conversation
        if agent.is_in_conversation:
            return False, None, None
        
        # Can't interact if doing something that demands full attention
        if agent.current_action and agent.current_action.requires_focus:
            return False, None, None
        
        # Check each perceived agent for interaction triggers
        best_target = None
        best_score = 0.0
        best_reason = None
        
        for perceived in perceived_agents:
            other = perceived["agent"]
            
            # Can't talk if too far
            if not perceived["can_talk"]:
                # But might walk toward them to talk
                if perceived["attention_weight"] > 0.6:
                    return True, other.name, "approach_to_talk"
                continue
            
            # Skip if the other is busy in conversation
            if other.is_in_conversation:
                continue
            
            score, reason = self.calculate_interaction_score(agent, other, perceived)
            
            if score > best_score:
                best_score = score
                best_target = other.name
                best_reason = reason
        
        # Interaction threshold — must exceed this to actually approach someone
        # Higher threshold = more introverted behavior
        threshold = 0.3 + (1.0 - agent.personality["extraversion"]) * 0.3
        # Threshold range: 0.3 (most extraverted) to 0.6 (most introverted)
        
        # Social need lowers the threshold — lonely people initiate more
        if agent.drives.social_need > 0.6:
            threshold -= 0.15
        
        # Anxiety raises the threshold — anxious people avoid interaction
        if agent.emotional_state.anxiety > 0.5:
            threshold += 0.1
        
        if best_score > threshold:
            return True, best_target, best_reason
        
        return False, None, None
    
    def calculate_interaction_score(self, agent, other, perceived) -> tuple[float, str]:
        """
        How strong is the pull to interact with this specific person?
        Returns (score, reason).
        """
        score = 0.0
        reasons = []
        
        rel = agent.get_relationship(other.name)
        
        # === NEED-DRIVEN TRIGGERS ===
        
        # I need something from them (trade, help, information)
        active_needs = self.get_needs_involving(agent, other)
        if active_needs:
            score += 0.4
            reasons.append(f"need: {active_needs[0]}")
        
        # I have a goal that requires talking to them
        relevant_goals = [g for g in agent.current_goals if other.name in g.involves_agents]
        if relevant_goals:
            score += 0.5
            reasons.append(f"goal: {relevant_goals[0].description}")
        
        # === SOCIAL-DRIVEN TRIGGERS ===
        
        # We're friends and I haven't talked to them recently
        if rel and rel.sentiment > 0.4:
            ticks_since_last = agent.world_state.current_tick - (rel.last_interaction or 0)
            if ticks_since_last > 100:  # More than a day since we talked
                score += 0.3
                reasons.append("haven't caught up in a while")
            elif ticks_since_last > 50:
                score += 0.15
                reasons.append("want to check in")
        
        # Social need is high and this person is available and not hostile
        if agent.drives.social_need > 0.5 and (not rel or rel.sentiment > -0.3):
            score += agent.drives.social_need * 0.3
            reasons.append("lonely")
        
        # === EMOTION-DRIVEN TRIGGERS ===
        
        # I'm upset about something they did — unresolved conflict
        if rel and rel.unresolved_issues:
            if agent.emotional_state.anger > 0.3 or agent.emotional_state.resentment > 0.3:
                score += 0.4
                reasons.append(f"unresolved: {rel.unresolved_issues[0]}")
            elif agent.personality["agreeableness"] > 0.6:
                # Agreeable people try to resolve things even without anger
                score += 0.25
                reasons.append("want to clear the air")
        
        # They look distressed and I'm empathetic
        if other.emotional_state.is_visibly_distressed():
            empathy_score = agent.personality["agreeableness"] * 0.4
            score += empathy_score
            reasons.append("they seem upset")
        
        # I just heard something about them — gossip-driven curiosity
        recent_gossip = agent.get_recent_gossip_about(other.name)
        if recent_gossip:
            score += 0.25
            reasons.append("heard something about them")
        
        # I have gossip TO SHARE and they'd be interested
        shareable_gossip = agent.get_gossip_relevant_to(other)
        if shareable_gossip:
            gossip_inclination = agent.personality["extraversion"] * 0.3
            score += gossip_inclination
            reasons.append("have something to tell them")
        
        # === SITUATION-DRIVEN TRIGGERS ===
        
        # We're both idle in a social space (tavern, town square, gathering)
        if (agent.current_action_type == "idle" and 
            other.current_action_type == "idle" and
            agent.current_location_type in ["social_space", "open_space"]):
            score += 0.2
            reasons.append("both idle, might as well chat")
        
        # Something just happened that we both witnessed
        shared_observations = agent.get_shared_recent_observations(other)
        if shared_observations:
            score += 0.2
            reasons.append(f"both saw: {shared_observations[0]}")
        
        # It's a social time of day (evening, mealtime)
        if agent.world_state.time_of_day in ["evening", "midday"]:
            score += 0.1
            reasons.append("social hour")
        
        # === NEGATIVE MODIFIERS ===
        
        # I actively dislike them
        if rel and rel.sentiment < -0.3:
            score -= 0.3  # Still might interact if there's a strong reason (need, goal, conflict)
        
        # I'm exhausted
        if agent.drives.rest > 0.7:
            score -= 0.2
        
        # I'm deeply focused on something
        if agent.working_memory.current_focus and "them" not in agent.working_memory.current_focus:
            score -= 0.1
        
        primary_reason = reasons[0] if reasons else "proximity"
        return max(0.0, score), primary_reason
    
    def get_needs_involving(self, agent, other) -> list:
        """Check if the agent needs something the other might provide."""
        needs = []
        
        # I'm hungry and they have food / know where food is
        if agent.drives.hunger > 0.5:
            if other.has_in_inventory("food") or other.skill_memory.has_skill("farming"):
                needs.append("food")
        
        # I need shelter and they can build
        if agent.drives.shelter_need > 0.5 and not agent.home:
            if other.skill_memory.has_skill("building"):
                needs.append("help building shelter")
        
        # I need medical attention and they're the healer
        if agent.health < 0.7 and other.skill_memory.has_skill("healing"):
            needs.append("medical help")
        
        # I have something to trade and they have what I need
        if agent.inventory and other.inventory:
            my_surplus = agent.get_surplus_items()
            their_surplus = other.get_surplus_items()
            if my_surplus and their_surplus:
                needs.append("potential trade")
        
        return needs
```

---

## Interaction Types

### Not Every Interaction Is A Full Conversation

Real human interactions range from a brief nod to a two-hour heart-to-heart. Model this spectrum.

```python
class InteractionType:
    ACKNOWLEDGE = "acknowledge"       # Nod, wave, brief eye contact. No words. 1 tick.
    GREETING = "greeting"             # "Morning, John." "Hey, Mei." 1-2 ticks.
    SMALL_TALK = "small_talk"         # Weather, general observations. 2-4 ticks.
    INFORMATION_EXCHANGE = "info"     # Sharing specific knowledge. 3-5 ticks.
    REQUEST = "request"               # Asking for something specific. 2-5 ticks.
    NEGOTIATION = "negotiation"       # Trading, bargaining, proposing deals. 5-10 ticks.
    DEEP_CONVERSATION = "deep"        # Emotional, philosophical, personal. 8-15 ticks.
    ARGUMENT = "argument"             # Conflict, disagreement, confrontation. 3-10 ticks.
    COMFORTING = "comforting"          # Supporting someone in distress. 5-10 ticks.
    PLANNING = "planning"             # Coordinating a shared task or project. 5-10 ticks.
    GOSSIP = "gossip"                 # Talking about a third party. 3-8 ticks.
    GROUP_DISCUSSION = "group"        # 3+ agents discussing something. 5-20 ticks.
```

### Selecting Interaction Type

The interaction type is determined by the triggering reason and the relationship:

```python
def select_interaction_type(agent, other, reason, relationship) -> InteractionType:
    """
    Based on why the interaction was triggered, determine what kind
    of interaction this will be.
    """
    
    # Need-driven → purposeful interaction
    if reason.startswith("need:"):
        if "trade" in reason:
            return InteractionType.NEGOTIATION
        elif "help" in reason:
            return InteractionType.REQUEST
        elif "food" in reason or "medical" in reason:
            return InteractionType.REQUEST
    
    # Goal-driven → depends on the goal
    if reason.startswith("goal:"):
        return InteractionType.PLANNING
    
    # Conflict-driven
    if reason.startswith("unresolved:"):
        if agent.emotional_state.anger > 0.5:
            return InteractionType.ARGUMENT
        else:
            return InteractionType.DEEP_CONVERSATION
    
    # Empathy-driven
    if reason == "they seem upset":
        return InteractionType.COMFORTING
    
    # Gossip-driven
    if reason in ["heard something about them", "have something to tell them"]:
        return InteractionType.GOSSIP
    
    # Social-driven
    if reason in ["lonely", "haven't caught up in a while", "want to check in"]:
        if relationship and relationship.sentiment > 0.5:
            return InteractionType.DEEP_CONVERSATION
        else:
            return InteractionType.SMALL_TALK
    
    # Situation-driven
    if reason in ["both idle, might as well chat", "social hour"]:
        return InteractionType.SMALL_TALK
    
    if reason.startswith("both saw:"):
        return InteractionType.INFORMATION_EXCHANGE
    
    # Low familiarity → keep it light
    if not relationship or relationship.familiarity < 0.3:
        return InteractionType.GREETING
    
    # Default
    return InteractionType.SMALL_TALK
```

---

## Conversation Mechanics

### Lightweight Interactions (No LLM)

Acknowledges, greetings, and some small talk can run without LLM calls. Use templates with personality-based variation.

```python
class LightweightInteraction:
    """
    Handles brief interactions that don't warrant an LLM call.
    These keep the simulation feeling socially alive without burning API credits.
    """
    
    def generate_greeting(self, agent, other, relationship, time_of_day) -> str:
        """Template-based greeting with personality variation."""
        
        warmth = relationship.sentiment if relationship else 0.0
        formality = 1.0 - agent.personality["extraversion"]
        
        if warmth > 0.5:
            greetings = [
                f"Hey {other.name.split()[0]}! Good to see you.",
                f"{other.name.split()[0]}! How are you doing?",
                f"Morning, {other.name.split()[0]}. You look well.",
            ]
        elif warmth < -0.2:
            greetings = [
                f"{other.name.split()[0]}.",  # Curt
                f"Oh. Hello.",
                # might just nod and say nothing
            ]
        else:
            greetings = [
                f"Hello, {other.name.split()[0]}.",
                f"Good {time_of_day}, {other.name.split()[0]}.",
                f"Hey there.",
            ]
        
        return random.choice(greetings)
    
    def generate_small_talk(self, agent, world_state) -> str:
        """Template-based small talk topics."""
        
        topics = []
        
        if world_state.weather == "rain":
            topics.append("This rain doesn't seem like it's stopping anytime soon.")
        elif world_state.weather == "clear" and world_state.season == "spring":
            topics.append("Beautiful day out there.")
        
        if world_state.season == "winter":
            topics.append("Getting cold. Hope we have enough firewood.")
        
        # Can add situational topics based on recent events
        recent_events = world_state.get_recent_notable_events(last_n_ticks=50)
        for event in recent_events[:1]:
            topics.append(f"Did you hear about {event.short_description}?")
        
        return random.choice(topics) if topics else "How's your day going?"
```

### Full Conversations (LLM-Powered)

For information exchange, negotiation, deep conversation, arguments, comforting, planning, and gossip — use the LLM.

```python
class Conversation:
    """
    A multi-turn conversation between two (or more) agents.
    Each turn is an LLM call for the responding agent.
    """
    
    participants: list[str]
    initiator: str
    interaction_type: InteractionType
    location: str
    started_at: int
    turns: list[ConversationTurn]
    is_active: bool
    max_turns: int
    topic: str
    
    def __init__(self, initiator, target, interaction_type, reason, location):
        self.participants = [initiator.name, target.name]
        self.initiator = initiator.name
        self.interaction_type = interaction_type
        self.location = location
        self.turns = []
        self.is_active = True
        self.reason = reason
        
        # Max turns based on interaction type
        turn_ranges = {
            InteractionType.GREETING: (1, 2),
            InteractionType.SMALL_TALK: (2, 4),
            InteractionType.INFORMATION_EXCHANGE: (3, 6),
            InteractionType.REQUEST: (2, 5),
            InteractionType.NEGOTIATION: (4, 10),
            InteractionType.DEEP_CONVERSATION: (6, 15),
            InteractionType.ARGUMENT: (3, 10),
            InteractionType.COMFORTING: (4, 10),
            InteractionType.PLANNING: (4, 10),
            InteractionType.GOSSIP: (3, 8),
        }
        min_t, max_t = turn_ranges.get(interaction_type, (2, 6))
        self.max_turns = random.randint(min_t, max_t)
    
    async def generate_opening(self, initiator_agent, target_agent) -> ConversationTurn:
        """The first thing the initiator says."""
        
        prompt = f"""
You are {initiator_agent.name}. You've decided to talk to {target_agent.name}.

Why you're approaching them: {self.reason}
Interaction type: {self.interaction_type}

Your personality: {initiator_agent.personality_summary()}
Your current emotional state: {initiator_agent.emotional_state.get_prompt_description()}
Your relationship with {target_agent.name}: {initiator_agent.get_relationship_summary(target_agent.name)}
Your mental model of {target_agent.name}: {initiator_agent.get_mental_model_summary(target_agent.name)}

What's on your mind right now: {initiator_agent.working_memory.get_summary()}

Context: You're at {self.location}. It's {initiator_agent.world_state.time_of_day}.
{self.get_environmental_context()}

Open the conversation naturally. Remember:
- If this is small talk, keep it light
- If you need something, you might not ask directly right away
- If you're angry, you might be passive-aggressive or blunt depending on personality
- If you're comforting someone, lead with empathy not solutions
- If you have gossip, you might ease into it rather than blurting it out
- Match your communication style to your personality and your comfort level with this person

Keep it to 1-3 sentences. Real people don't give speeches.

Return JSON:
{{
    "speech": "what you say out loud",
    "inner_thought": "what you're thinking but not saying",
    "tone": "warm/casual/formal/tense/hesitant/urgent/playful/concerned",
    "body_language": "brief description: crossed arms, leaning in, avoiding eye contact, etc."
}}
"""
        return await llm_call(prompt)
    
    async def generate_response(self, responding_agent, speaking_agent, previous_turn) -> ConversationTurn:
        """Generate a response to the previous turn."""
        
        # Retrieve memories relevant to what was just said
        relevant_memories = responding_agent.episodic_memory.retrieve(
            query=previous_turn.speech,
            top_n=5
        )
        
        # Retrieve beliefs relevant to the topic
        relevant_beliefs = responding_agent.belief_system.retrieve(
            query=previous_turn.speech,
            top_n=3
        )
        
        prompt = f"""
You are {responding_agent.name}. You're in a conversation with {speaking_agent.name}.

{speaking_agent.name} just said: "{previous_turn.speech}"
Their tone was: {previous_turn.tone}
Their body language: {previous_turn.body_language}

Conversation so far:
{self.get_transcript_summary()}

Your personality: {responding_agent.personality_summary()}
Your emotional state: {responding_agent.emotional_state.get_prompt_description()}
Your relationship with {speaking_agent.name}: {responding_agent.get_relationship_summary(speaking_agent.name)}

Relevant memories:
{[m.content for m in relevant_memories]}

Relevant beliefs:
{[b.content for b in relevant_beliefs]}

Respond naturally as {responding_agent.name}. Consider:
- Do you agree or disagree with what they said?
- Does this trigger any emotional reaction?
- Are you hiding something or being evasive?
- Would you change the subject, go deeper, or try to end the conversation?
- Are you distracted by something else on your mind?

1-3 sentences. Natural speech, not a monologue.

Return JSON:
{{
    "speech": "what you say out loud",
    "inner_thought": "what you're thinking but not saying",
    "tone": "warm/casual/formal/tense/hesitant/urgent/playful/concerned/defensive/amused",
    "body_language": "brief description",
    "new_information_learned": "any facts you learned from what they said, or null",
    "emotion_shift": "how this exchange made you feel (brief), or null",
    "wants_to_continue": true/false,
    "wants_to_change_topic": "new topic, or null",
    "trust_shift": "slightly_up/slightly_down/unchanged",
    "gossip_learned": "information about a third party, or null"
}}
"""
        return await llm_call(prompt)
    
    def should_continue(self, latest_turn, turn_count) -> bool:
        """Determine if the conversation should continue."""
        
        # Hit max turns
        if turn_count >= self.max_turns:
            return False
        
        # Responder wants to end
        if not latest_turn.get("wants_to_continue", True):
            return False
        
        # Both agents are losing interest (check engagement)
        if turn_count > 3 and self.get_average_engagement() < 0.3:
            return False
        
        # Argument escalated too much — one agent walks away
        if latest_turn.get("tone") in ["furious", "disgusted"] and random.random() < 0.5:
            return False
        
        # External interruption — another agent arrives, something happens
        if self.check_for_interruptions():
            return False
        
        return True
```

---

## Conversation Consequences

### What Happens After A Conversation

Every conversation produces effects that ripple through the simulation.

```python
class ConversationProcessor:
    """
    After a conversation ends, process all its consequences.
    """
    
    def process_completed_conversation(self, conversation, agents, world_state):
        
        for agent_name in conversation.participants:
            agent = self.get_agent(agent_name)
            other_name = [n for n in conversation.participants if n != agent_name][0]
            
            # 1. Store the conversation as an episodic memory
            memory = Episode(
                content=self.summarize_conversation_for(agent_name, conversation),
                emotional_valence=self.calculate_conversation_valence(agent_name, conversation),
                emotional_intensity=self.calculate_conversation_intensity(conversation),
                primary_emotion=self.get_dominant_emotion_during(agent_name, conversation),
                agents_involved=[other_name],
                location=conversation.location,
                my_role="participant",
                memory_type="conversation"
            )
            agent.episodic_memory.append(memory)
            
            # 2. Update relationship
            rel = agent.get_relationship(other_name)
            sentiment_change = self.calculate_sentiment_change(agent_name, conversation)
            trust_change = self.calculate_trust_change(agent_name, conversation)
            rel.sentiment = max(-1.0, min(1.0, rel.sentiment + sentiment_change))
            rel.trust = max(0.0, min(1.0, rel.trust + trust_change))
            rel.familiarity = min(1.0, rel.familiarity + 0.02)
            rel.interaction_count += 1
            rel.last_interaction = world_state.current_tick
            
            # 3. Update emotional state based on conversation
            for turn in conversation.turns:
                if turn.agent == agent_name and turn.get("emotion_shift"):
                    agent.emotional_state.apply_shift(turn["emotion_shift"])
            
            # 4. Process learned information
            for turn in conversation.turns:
                if turn.agent != agent_name:  # What the OTHER person said
                    if turn.get("new_information_learned"):
                        agent.belief_system.integrate_new_information(
                            turn["new_information_learned"],
                            source=other_name,
                            trust_in_source=rel.trust
                        )
            
            # 5. Process gossip
            for turn in conversation.turns:
                if turn.get("gossip_learned"):
                    gossip = turn["gossip_learned"]
                    # Store as a memory with source attribution
                    gossip_memory = Episode(
                        content=f"{other_name} told me: {gossip}",
                        emotional_intensity=0.4,
                        memory_type="gossip",
                        agents_involved=[other_name, gossip.mentioned_agent],
                        my_interpretation=f"I heard from {other_name} that {gossip}"
                    )
                    agent.episodic_memory.append(gossip_memory)
                    
                    # Potentially update beliefs about the gossip subject
                    # Trust in the source affects how much the gossip shifts beliefs
                    if rel.trust > 0.5:
                        agent.belief_system.integrate_gossip(
                            gossip, source=other_name, trust=rel.trust
                        )
            
            # 6. Update mental model of the other person
            if conversation.interaction_type in [
                InteractionType.DEEP_CONVERSATION,
                InteractionType.ARGUMENT,
                InteractionType.COMFORTING,
                InteractionType.NEGOTIATION
            ]:
                agent.update_mental_model(other_name, conversation)
            
            # 7. Check if new goals emerged
            for turn in conversation.turns:
                if turn.agent == agent_name and turn.get("inner_thought"):
                    # Sometimes a conversation sparks a new goal
                    # This gets picked up in the next reflection cycle
                    pass
            
            # 8. Mark unresolved issues as resolved (if applicable)
            if conversation.interaction_type == InteractionType.ARGUMENT:
                if self.was_issue_resolved(conversation):
                    rel.unresolved_issues = [
                        issue for issue in rel.unresolved_issues
                        if issue not in conversation.resolved_issues
                    ]
                else:
                    # Argument didn't resolve — might have made things worse
                    rel.unresolved_issues.append(
                        self.summarize_new_issue(conversation)
                    )
            
            # 9. Social need satisfaction
            if conversation.interaction_type != InteractionType.ARGUMENT:
                agent.drives.social_need = max(0.0, agent.drives.social_need - 0.15)
            else:
                # Arguments don't satisfy social need — might increase it
                agent.drives.social_need = min(1.0, agent.drives.social_need + 0.05)
```

---

## Overhearing and Observation

### Agents Don't Just Talk — They Watch and Listen

```python
class OverhearingSystem:
    """
    Agents within overhearing range of a conversation absorb information
    from it — but imperfectly. They catch fragments, not full context.
    """
    
    def process_overhearing(self, observer, conversation, distance):
        """
        An agent near a conversation picks up fragments.
        What they hear depends on distance, conversation volume, 
        and their own attention.
        """
        
        # Probability of catching each turn decreases with distance
        catch_probability = max(0.2, 1.0 - (distance * 0.25))
        
        # Arguments are louder — easier to overhear
        if conversation.interaction_type == InteractionType.ARGUMENT:
            catch_probability = min(1.0, catch_probability + 0.3)
        
        # Whispered/private conversations are harder
        if any(t.get("tone") == "whispered" for t in conversation.turns):
            catch_probability *= 0.3
        
        overheard_fragments = []
        for turn in conversation.turns:
            if random.random() < catch_probability:
                # Don't get the full speech — get a fragment
                fragment = self.extract_fragment(turn.speech)
                overheard_fragments.append({
                    "speaker": turn.agent,
                    "fragment": fragment,
                    "confidence": catch_probability
                })
        
        if overheard_fragments:
            # Store as a memory — but marked as overheard (less reliable)
            memory = Episode(
                content=f"Overheard {conversation.participants[0]} and {conversation.participants[1]} talking. Caught: {self.summarize_fragments(overheard_fragments)}",
                emotional_intensity=0.3,
                memory_type="overheard",
                agents_involved=conversation.participants,
                my_role="overheard",
                my_interpretation=None  # Will be filled in during next reflection
            )
            observer.episodic_memory.append(memory)
            
            # Update working memory — this might grab attention
            if any(observer.name in f["fragment"] for f in overheard_fragments):
                # They're talking about ME
                observer.working_memory.interrupt_with(
                    f"I think {conversation.participants[0]} and {conversation.participants[1]} are talking about me"
                )
                observer.emotional_state.anxiety += 0.1
    
    def extract_fragment(self, full_speech: str) -> str:
        """
        Extract a partial, potentially misunderstood fragment.
        Real overhearing catches words out of context.
        """
        words = full_speech.split()
        if len(words) <= 4:
            return full_speech  # Short enough to catch fully
        
        # Catch a random contiguous chunk of 3-6 words
        chunk_size = random.randint(3, min(6, len(words)))
        start = random.randint(0, len(words) - chunk_size)
        return "..." + " ".join(words[start:start + chunk_size]) + "..."


class ObservationSystem:
    """
    Agents notice what others are doing, not just what they say.
    """
    
    def generate_observations(self, agent, perceived_agents, world_state) -> list:
        """
        What does the agent notice about nearby agents?
        No LLM needed — rule-based observation generation.
        """
        observations = []
        
        for perceived in perceived_agents:
            other = perceived["agent"]
            
            # Notice what they're carrying
            if other.inventory:
                notable_items = [item for item in other.inventory if item.is_visible]
                if notable_items:
                    observations.append(
                        f"{other.name} is carrying {notable_items[0].name}"
                    )
            
            # Notice their emotional state (if visible)
            if other.emotional_state.is_visibly_distressed():
                observations.append(
                    f"{other.name} looks {other.emotional_state.get_visible_state()}"
                )
            
            # Notice unusual behavior
            if other.current_action and other.current_action.is_unusual_for(other):
                observations.append(
                    f"{other.name} is {other.current_action.description} — that's unusual for them"
                )
            
            # Notice where they came from (if agent was watching)
            if other.just_arrived and other.previous_location:
                observations.append(
                    f"{other.name} just came from {other.previous_location}"
                )
            
            # Notice who they were talking to
            if other.just_finished_conversation:
                observations.append(
                    f"{other.name} was just talking to {other.last_conversation_partner}"
                )
        
        return observations
```

---

## Group Interactions

### When Three Or More Agents Interact

Group conversations emerge naturally when multiple agents are in the same social space.

```python
class GroupInteraction:
    """
    Handles conversations with 3+ participants.
    These happen at gatherings, shared meals, town meetings, or when 
    a third person joins an existing conversation.
    """
    
    def check_for_group_formation(self, active_conversations, idle_agents, world_state):
        """
        An idle agent near a conversation might join it.
        Multiple idle agents in the same social space might form a group chat.
        """
        
        # Check if any idle agent wants to join an active conversation
        for conversation in active_conversations:
            nearby_idle = [
                agent for agent in idle_agents
                if world_state.get_distance(agent.location, conversation.location) <= 3
                and agent.name not in conversation.participants
            ]
            
            for agent in nearby_idle:
                join_score = self.calculate_join_score(agent, conversation)
                if join_score > 0.4:
                    conversation.add_participant(agent)
                    # The joining agent might redirect the conversation
                    break
        
        # Check for spontaneous group formation in social spaces
        social_locations = world_state.get_social_locations()
        for location in social_locations:
            agents_here = [a for a in idle_agents if a.location == location]
            if len(agents_here) >= 3:
                # Potential group conversation
                if random.random() < 0.3:  # Don't force it every time
                    self.start_group_conversation(agents_here, location, world_state)
    
    def calculate_join_score(self, agent, conversation) -> float:
        """Would this agent want to join this conversation?"""
        score = 0.0
        
        # Know the participants well
        for participant in conversation.participants:
            rel = agent.get_relationship(participant)
            if rel and rel.sentiment > 0.3:
                score += 0.15
        
        # The conversation topic is relevant to me
        if conversation.topic and agent.is_interested_in(conversation.topic):
            score += 0.3
        
        # They're talking about me (overheard)
        if agent.name in conversation.get_mentioned_names():
            score += 0.5
        
        # I'm lonely
        if agent.drives.social_need > 0.6:
            score += 0.2
        
        # I'm shy
        score -= (1.0 - agent.personality["extraversion"]) * 0.2
        
        return score
```

---

## Interaction Avoidance

### Sometimes The Decision Is NOT To Interact

Just as important as modeling why agents talk is modeling why they DON'T.

```python
class AvoidanceSystem:
    """
    Agents actively avoid certain people or situations.
    This is as important as interaction for creating realistic social dynamics.
    """
    
    def check_avoidance(self, agent, perceived_agents) -> list[str]:
        """
        Returns list of agent names this agent is actively trying to avoid.
        Affects pathfinding — agent will take a longer route to dodge them.
        """
        avoiding = []
        
        for perceived in perceived_agents:
            other = perceived["agent"]
            rel = agent.get_relationship(other.name)
            
            # Active hostility — avoid unless confrontation is intended
            if rel and rel.sentiment < -0.5 and not agent.intends_confrontation_with(other.name):
                avoiding.append(other.name)
            
            # Shame or embarrassment related to this person
            if agent.has_shame_memory_involving(other.name):
                if agent.emotional_state.shame > 0.3:
                    avoiding.append(other.name)
            
            # Owe them something and can't pay
            if agent.has_unpaid_debt_to(other.name):
                if agent.personality["conscientiousness"] > 0.5:  # Conscientious people feel worse about debts
                    avoiding.append(other.name)
            
            # Just had an argument — need cooling off time
            if rel and rel.last_argument_tick:
                ticks_since = agent.world_state.current_tick - rel.last_argument_tick
                if ticks_since < 30:  # Still raw
                    avoiding.append(other.name)
            
            # Socially exhausted — avoid everyone
            if agent.drives.rest > 0.7 or agent.emotional_state.valence < -0.5:
                if rel and rel.sentiment < 0.5:  # Only close friends are tolerated
                    avoiding.append(other.name)
        
        return avoiding
    
    def modify_pathfinding(self, agent, destination, avoiding, world_state):
        """
        When an agent is avoiding someone, modify their path
        to minimize the chance of encounter.
        """
        if not avoiding:
            return world_state.get_shortest_path(agent.location, destination)
        
        avoided_locations = []
        for avoid_name in avoiding:
            avoided_agent = world_state.get_agent(avoid_name)
            if avoided_agent:
                avoided_locations.append(avoided_agent.location)
                # Also avoid locations near the avoided agent
                nearby = world_state.get_adjacent_tiles(avoided_agent.location, radius=2)
                avoided_locations.extend(nearby)
        
        return world_state.get_path_avoiding(agent.location, destination, avoided_locations)
```

---

## Social Space Dynamics

### Certain Locations Encourage Different Interaction Patterns

```python
class SocialSpaceRules:
    """
    How location affects interaction behavior.
    """
    
    LOCATION_MODIFIERS = {
        "town_square": {
            "interaction_probability_boost": 0.2,
            "default_interaction_type": InteractionType.SMALL_TALK,
            "group_formation_boost": 0.3,
            "privacy": 0.0,  # Everything is public here
            "noise_level": "normal"
        },
        "social_building": {  # If agents designate a building as tavern/gathering spot
            "interaction_probability_boost": 0.3,
            "default_interaction_type": InteractionType.SMALL_TALK,
            "group_formation_boost": 0.4,
            "privacy": 0.2,
            "noise_level": "loud",
            "alcohol_effect": True  # If they create alcohol — lowers inhibition
        },
        "workspace": {
            "interaction_probability_boost": -0.1,  # People are busy
            "default_interaction_type": InteractionType.INFORMATION_EXCHANGE,
            "group_formation_boost": 0.0,
            "privacy": 0.3,
            "noise_level": "normal"
        },
        "private_home": {
            "interaction_probability_boost": -0.3,  # People don't barge in
            "default_interaction_type": InteractionType.DEEP_CONVERSATION,
            "group_formation_boost": -0.5,
            "privacy": 0.9,  # Conversations here are private
            "noise_level": "quiet",
            "requires_invitation": True  # Must be invited or have high relationship
        },
        "natural_area": {  # Park, river, hill
            "interaction_probability_boost": 0.0,
            "default_interaction_type": InteractionType.DEEP_CONVERSATION,
            "group_formation_boost": 0.1,
            "privacy": 0.5,
            "noise_level": "quiet"
        },
        "open_land": {
            "interaction_probability_boost": -0.2,
            "default_interaction_type": InteractionType.GREETING,
            "group_formation_boost": -0.3,
            "privacy": 0.3,
            "noise_level": "quiet"
        }
    }
    
    def can_enter_location(self, agent, location, world_state) -> bool:
        """Some locations require permission to enter."""
        
        rules = self.LOCATION_MODIFIERS.get(location.type, {})
        
        if rules.get("requires_invitation"):
            owner = location.claimed_by
            if owner and owner != agent.name:
                rel = agent.get_relationship(owner)
                # Can enter if: good relationship, or urgent need, or owner invited
                if rel and rel.sentiment > 0.4:
                    return True
                if agent.has_active_invitation_from(owner):
                    return True
                if agent.drives.get_dominant_drive()[1] > 0.9:  # Desperate
                    return True
                return False
        
        return True
```

---

## The Interaction Pipeline Summary

Every tick, for every agent:

```
1. AWARENESS: Who can I see? Who draws my attention? (No LLM)

2. AVOIDANCE CHECK: Am I actively avoiding anyone nearby? 
   If yes, modify my path. (No LLM)

3. OBSERVATION: What are nearby agents doing? Store observations. (No LLM)

4. OVERHEARING: Is there a conversation nearby I can partially hear?
   Store fragments as memories. (No LLM)

5. INTERACTION DECISION: Should I approach someone?
   Calculate interaction scores for all perceived agents.
   Compare best score against personality-adjusted threshold. (No LLM)

6. If YES:
   a. Select interaction type based on reason and relationship (No LLM)
   b. If lightweight (greeting, basic small talk): use templates (No LLM)
   c. If substantive: initiate LLM-powered conversation
      - Generate opening (1 LLM call)
      - Exchange turns until conversation ends (1 LLM call per turn)
      - Process consequences: memories, relationships, emotions, 
        gossip, beliefs (No LLM)

7. GROUP CHECK: Are 3+ agents idle in a social space?
   Potential group conversation formation. (No LLM until conversation starts)

8. If NO interaction: continue current activity. (No LLM)
```

Estimated LLM calls per tick from the interaction system:
- 0-2 conversations active at any time (most ticks have 0-1)
- Each active conversation generates 1 LLM call per turn
- Average conversation is 3-6 turns
- Most interactions are lightweight (greeting, acknowledgment) with no LLM calls
- Total: roughly 1-4 LLM calls per tick from the interaction system, 
  with many ticks at 0
