# The Agent Mind: Complete Cognitive Architecture for Polis

## What This Document Is

This is the definitive spec for how an agent thinks, remembers, reasons, and decides in Polis. It supersedes and integrates the earlier cognition doc, incorporating the open-ended simulation design where agents have no pre-assigned roles and can modify the world's rules.

An agent in Polis isn't a character executing a script. It's a mind — messy, biased, emotional, sometimes irrational, sometimes brilliant — that experiences a world, builds an understanding of it, forms relationships, discovers what it's good at, and gradually shapes both itself and the world around it.

---

## The Mind's Structure

```
┌──────────────────────────────────────────────────────────────┐
│                     THE AGENT MIND                            │
│                                                              │
│  ┌─────────────┐  ┌──────────────┐  ┌───────────────────┐   │
│  │  ATTENTION   │  │  INNER VOICE │  │  DRIVES & NEEDS   │   │
│  │  (Spotlight) │  │  (Stream of  │  │  (The engine that │   │
│  │  5-7 items   │  │  consciousness│  │  moves behavior)  │   │
│  └──────┬──────┘  └──────┬───────┘  └────────┬──────────┘   │
│         │                │                    │              │
│  ┌──────▼──────────────────────────────────────▼──────────┐  │
│  │              EMOTIONAL LANDSCAPE                       │  │
│  │  Continuous variables: joy, anxiety, anger, loneliness │  │
│  │  shame, pride, resentment, gratitude, hope             │  │
│  │  Influenced by everything. Influences everything.      │  │
│  └──────┬────────────────────────────────────┬───────────┘  │
│         │                                    │              │
│  ┌──────▼──────┐  ┌────────────┐  ┌─────────▼──────────┐  │
│  │  EPISODIC   │  │  SEMANTIC  │  │  MENTAL MODELS     │  │
│  │  MEMORY     │  │  MEMORY   │  │  OF OTHERS         │  │
│  │  (Events)   │  │  (Beliefs) │  │  (Theory of Mind)  │  │
│  └──────┬──────┘  └─────┬──────┘  └─────────┬──────────┘  │
│         │               │                    │              │
│  ┌──────▼───────────────▼────────────────────▼──────────┐  │
│  │              WORLD UNDERSTANDING                      │  │
│  │  Known locations, resources, claims, rules, norms     │  │
│  │  Skills discovered, tools made, institutions known    │  │
│  └──────┬───────────────────────────────────────────────┘  │
│         │                                                   │
│  ┌──────▼──────────────────────────────────────────────┐   │
│  │              IDENTITY                                │   │
│  │  Self-concept, values, fears, emerging role,         │   │
│  │  personal narrative, sense of purpose                │   │
│  └─────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────┘
```

---

## Layer 1: Attention (Working Memory)

### What It Is

The tiny spotlight of conscious awareness. At any moment, an agent is actively thinking about at most 5-7 things. Everything else exists in deeper memory and only surfaces when triggered.

### Implementation

```python
class Attention:
    # The spotlight — what's in conscious awareness right now
    active_items: list[str] = []        # Max 7
    current_focus: str = None           # The ONE thing getting most attention
    
    # Background processes — things nagging at the edge of awareness
    background_worry: str = None        # "I still don't have proper shelter"
    background_desire: str = None       # "I really want to try fishing at the river"
    unfinished_business: str = None     # "I never responded to what Eleanor said yesterday"
    
    # What just happened — the freshest input
    latest_observation: str = None      # Updated every tick from environment
    latest_sensation: str = None        # Physical feeling: "My stomach is growling"
    
    def push(self, new_item: str, priority: float):
        """
        Something enters awareness. If attention is full, 
        the least important item gets pushed out.
        High-priority items (threats, strong emotions, personal relevance)
        always get in. Low-priority items only enter if there's room.
        """
        if len(self.active_items) < 7:
            self.active_items.append(new_item)
        elif priority > 0.5:
            # Push out the least attended item
            self.active_items.pop(-1)
            self.active_items.insert(0, new_item)
        
        # If this is higher priority than current focus, redirect focus
        if priority > 0.7:
            self.current_focus = new_item
    
    def update_from_drives(self, drives):
        """Drives that cross thresholds force their way into attention."""
        if drives.hunger > 0.7 and "hungry" not in str(self.active_items):
            self.push("I'm getting really hungry", priority=0.8)
            self.latest_sensation = "My stomach is growling"
        
        if drives.rest > 0.8 and "tired" not in str(self.active_items):
            self.push("I'm exhausted", priority=0.7)
            self.latest_sensation = "My body feels heavy. I need to rest."
        
        if drives.social_need > 0.7 and "lonely" not in str(self.active_items):
            self.background_worry = "I haven't really talked to anyone today"
        
        if drives.safety > 0.6 and "unsafe" not in str(self.active_items):
            self.background_worry = "I don't feel safe here"
        
        if drives.purpose_need > 0.7:
            self.background_worry = "What am I even doing here? I need to figure out my place."
    
    def update_from_observations(self, observations: list[str]):
        """New environmental observations enter attention."""
        for obs in observations:
            novelty = self.assess_novelty(obs)
            personal_relevance = self.assess_personal_relevance(obs)
            threat_level = self.assess_threat(obs)
            
            priority = max(novelty, personal_relevance, threat_level)
            
            if priority > 0.3:  # Only notable things enter attention
                self.push(obs, priority)
                self.latest_observation = obs
    
    def get_prompt_context(self) -> str:
        """Format attention contents for LLM prompt."""
        lines = []
        lines.append(f"You are currently focused on: {self.current_focus}")
        lines.append(f"Also on your mind: {', '.join(self.active_items[:4])}")
        if self.background_worry:
            lines.append(f"A nagging worry in the back of your mind: {self.background_worry}")
        if self.background_desire:
            lines.append(f"Something you've been wanting: {self.background_desire}")
        if self.unfinished_business:
            lines.append(f"Something unresolved: {self.unfinished_business}")
        if self.latest_sensation:
            lines.append(f"Physical sensation: {self.latest_sensation}")
        return "\n".join(lines)
```

### Why This Matters For Open-Ended Simulation

In the old design where agents had assigned jobs, attention was simple — they thought about work during work hours and social stuff otherwise. With no roles, attention is chaotic on Day 1. An agent's attention is bouncing between "I'm hungry," "where am I going to sleep," "that building looks empty," "who are all these people," "is anyone in charge here?" This chaotic attention drives the scramble behavior that makes the first days interesting.

As agents settle into routines, their attention stabilizes. The farmer thinks about crops. The builder thinks about materials. But attention can always be disrupted by novel events, threats, or emotional triggers — which is how crises break agents out of their routines.

---

## Layer 2: The Inner Voice (Stream of Consciousness)

### What It Is

The continuous internal monologue that runs below decision-making. Most thoughts aren't decisions — they're observations, reactions, worries, memories surfacing unbidden, daydreams, self-talk.

### Implementation

```python
class InnerVoice:
    """
    Generates background thoughts every 3-5 ticks.
    These are NOT action-oriented. They're the texture of inner life.
    They surface in the Mind tab and make agents feel alive.
    """
    
    recent_thoughts: list[dict] = []  # Last 20 thoughts
    
    async def generate_thought(self, agent) -> dict:
        """
        Generate a single background thought.
        Lightweight LLM call — short prompt, short response.
        """
        
        # Select thought type based on current state
        thought_type = self.select_thought_type(agent)
        
        prompt = f"""
You are the inner voice of {agent.name}, age {agent.age}.
Personality: {agent.personality_brief()}
Current location: {agent.location}
Currently doing: {agent.current_activity_description()}
Time of day: {agent.world_state.time_of_day}
Day number: {agent.world_state.day_number}

Emotional state: {agent.emotional_state.get_prompt_description()}
Physical state: {agent.drives.get_physical_description()}
Focus: {agent.attention.current_focus}

Generate ONE brief inner thought ({thought_type}).

Thought types and what they mean:
- observation: noticing something about the environment or another person
- worry: anxiety about something unresolved
- memory_trigger: a sensory detail triggering a memory from before arriving here
- self_talk: talking to yourself about what you should do
- daydream: imagining a future possibility or wishing for something
- reaction: emotional response to something that just happened
- question: wondering about something you don't understand
- gratitude: appreciating something small
- frustration: annoyance at a situation or yourself
- realization: connecting two things you hadn't connected before
- physical: awareness of your body (tired, hungry, sore, comfortable)
- nostalgia: thinking about life before you came here

Keep it to 1-2 sentences. Make it feel like a real human inner voice — 
fragmented, honest, sometimes mundane, sometimes profound. 

Don't make every thought dramatic. A builder might think "This nail keeps 
bending. I need better tools." A lonely person might think "I wonder what 
Mei is doing right now." Someone by the river might think "The water sounds 
like the creek behind my old house."

Return ONLY the thought as plain text, nothing else.
"""
        thought_text = await llm_call(prompt)
        
        thought = {
            "content": thought_text,
            "type": thought_type,
            "tick": agent.world_state.current_tick,
            "location": agent.location,
            "emotional_context": agent.emotional_state.get_dominant_emotion()
        }
        
        self.recent_thoughts.append(thought)
        if len(self.recent_thoughts) > 20:
            self.recent_thoughts.pop(0)
        
        # Some thoughts become memories (if important enough)
        if thought_type in ["realization", "worry", "reaction"]:
            agent.episodic_memory.append(Episode(
                content=f"Thought to myself: {thought_text}",
                emotional_intensity=0.3,
                memory_type="inner_thought"
            ))
        
        return thought
    
    def select_thought_type(self, agent) -> str:
        """
        What kind of thought is most likely right now?
        Weighted by emotional state, drives, and situation.
        """
        weights = {
            "observation": 0.15,
            "worry": agent.emotional_state.anxiety * 0.3,
            "memory_trigger": 0.08,
            "self_talk": 0.12,
            "daydream": max(0, 0.15 - agent.emotional_state.anxiety * 0.1),
            "reaction": 0.1 if agent.attention.latest_observation else 0.02,
            "question": agent.personality["openness"] * 0.1,
            "gratitude": max(0, agent.emotional_state.joy * 0.15),
            "frustration": max(0, (agent.emotional_state.anger + agent.drives.competence_need) * 0.1),
            "realization": 0.05,
            "physical": max(0, (agent.drives.hunger + agent.drives.rest) * 0.15 - 0.1),
            "nostalgia": 0.05 if agent.world_state.day_number < 10 else 0.02
        }
        
        # Normalize weights
        total = sum(weights.values())
        weights = {k: v/total for k, v in weights.items()}
        
        return random.choices(list(weights.keys()), weights=list(weights.values()))[0]
```

---

## Layer 3: Episodic Memory (With Distortion)

### What It Is

Personal history — specific events the agent experienced, stored with emotional coloring and subjective interpretation. These memories are NOT objective records. They're biased by the agent's personality, emotional state at the time, and subsequent reflection.

### Implementation

```python
class Episode:
    id: str
    content: str                     # What happened, from MY perspective
    raw_event: str                   # What actually happened (objective, for debugging)
    
    # Temporal context
    tick: int
    day_number: int
    time_of_day: str
    location: str
    
    # Who
    agents_involved: list[str]
    my_role: str                     # "I initiated" / "I responded" / "I witnessed" / "I overheard"
    
    # Emotional encoding
    emotional_valence: float         # -1.0 to 1.0
    emotional_intensity: float       # 0.0 to 1.0
    primary_emotion: str
    
    # Subjective interpretation (the bias layer)
    my_interpretation: str           # "I think John was avoiding my question"
    what_i_think_others_felt: str    # "Eleanor seemed annoyed but hid it well"
    what_this_means: str             # "Maybe I shouldn't bring up the tax issue again"
    
    # Sensory anchoring (makes memories feel real and triggers recall)
    sensory_detail: str              # "It was getting dark. The fire crackled."
    
    # Memory dynamics
    times_recalled: int = 0
    last_recalled: int = 0
    accuracy_drift: float = 0.0
    consolidated: bool = False       # Has this been processed into a belief yet?
    
    # Retrieval
    embedding: list[float] = None
    importance: float = 0.0          # Scored at creation time
    
    def distort_on_recall(self):
        """
        Each time a memory is recalled, it changes slightly.
        Emotional intensity amplifies (we exaggerate over time).
        Details fade but emotional coloring strengthens.
        Interpretation solidifies (we become more certain of our subjective take).
        """
        self.times_recalled += 1
        self.last_recalled = current_tick()
        
        # Emotional amplification
        if self.emotional_intensity > 0.3:
            self.emotional_intensity = min(1.0, self.emotional_intensity * 1.03)
        
        # Accuracy degrades
        self.accuracy_drift = min(0.5, self.accuracy_drift + 0.02)
        
        # Interpretation solidifies — we become more confident in our biased reading
        # (This is modeled by not changing interpretation on recall — it freezes)
    
    def compute_retrieval_score(self, query_embedding, current_tick) -> float:
        """How likely is this memory to surface?"""
        
        # Recency — recent memories are more accessible
        ticks_ago = current_tick - self.last_recalled if self.last_recalled else current_tick - self.tick
        recency = 1.0 / (1.0 + ticks_ago * 0.005)
        
        # Emotional weight — intense emotions make memories stickier
        emotional_weight = self.emotional_intensity * 1.5
        
        # Relevance to current query
        if query_embedding and self.embedding:
            relevance = cosine_similarity(query_embedding, self.embedding)
        else:
            relevance = 0.0
        
        # Rehearsal boost — frequently recalled memories are easier to access
        rehearsal = min(self.times_recalled * 0.08, 0.4)
        
        # Importance
        importance = self.importance * 0.2
        
        return (0.20 * recency + 
                0.25 * emotional_weight + 
                0.25 * relevance + 
                0.15 * rehearsal + 
                0.15 * importance)
```

### Creating Memories With Subjective Bias

When something happens, the memory isn't stored as an objective record. The LLM generates the agent's subjective experience of it.

```python
async def create_memory_from_event(agent, event) -> Episode:
    """
    Takes an objective event and creates a subjective memory.
    The memory is colored by personality, emotional state, 
    and existing beliefs.
    """
    
    prompt = f"""
Something just happened. Create {agent.name}'s subjective memory of it.

OBJECTIVE EVENT:
{event.description}

{agent.name}'s PERSONALITY:
{agent.personality_summary()}

{agent.name}'s CURRENT EMOTIONAL STATE:
{agent.emotional_state.get_prompt_description()}

{agent.name}'s RELEVANT EXISTING BELIEFS:
{agent.belief_system.get_relevant_beliefs(event.description)}

{agent.name}'s RELATIONSHIP WITH PEOPLE INVOLVED:
{agent.get_relationship_summaries(event.agents_involved)}

How would {agent.name} SUBJECTIVELY experience and interpret this event?
Remember:
- Anxious people interpret ambiguous situations as threatening
- People with low self-esteem assume others are judging them
- People who distrust someone interpret their actions more negatively
- People who like someone give them the benefit of the doubt
- People often project their own feelings onto others
- We notice details that confirm what we already believe

Return JSON:
{{
    "subjective_content": "What happened from {agent.name}'s perspective (1-2 sentences)",
    "my_interpretation": "What {agent.name} thinks this means",
    "what_i_think_others_felt": "How {agent.name} reads the emotions of others involved",
    "what_this_means_for_me": "How this affects {agent.name}'s situation or goals",
    "sensory_detail": "One vivid sensory detail {agent.name} noticed",
    "emotional_valence": -1.0 to 1.0,
    "emotional_intensity": 0.0 to 1.0,
    "primary_emotion": "the dominant feeling",
    "importance": 1-10
}}
"""
    result = await llm_call(prompt)
    
    return Episode(
        content=result["subjective_content"],
        raw_event=event.description,
        my_interpretation=result["my_interpretation"],
        what_i_think_others_felt=result["what_i_think_others_felt"],
        what_this_means=result["what_this_means_for_me"],
        sensory_detail=result["sensory_detail"],
        emotional_valence=result["emotional_valence"],
        emotional_intensity=result["emotional_intensity"],
        primary_emotion=result["primary_emotion"],
        importance=result["importance"],
        agents_involved=event.agents_involved,
        location=event.location,
        tick=event.tick,
        day_number=event.day_number,
        time_of_day=event.time_of_day
    )
```

This means two agents who witness the exact same event will remember it differently. Eleanor sees Marcus take extra food from the shared pile and remembers "Marcus took more than his share — he's always pushing boundaries." Ricky sees the same thing and remembers "Marcus grabbed some extra food — he was probably hungry." Same event, different memories, because their personalities and beliefs filter the experience.

---

## Layer 4: Semantic Memory (Beliefs)

### What It Is

Generalized knowledge and beliefs extracted from patterns across multiple episodes. Not specific events but conclusions drawn from experience. These are the most influential memory type because they shape how ALL new information is processed.

### The Belief Engine

```python
class Belief:
    content: str                     # "This community can work if we cooperate"
    category: str                    # Categories listed below
    confidence: float                # 0.0 to 1.0
    emotional_charge: float          # How emotionally invested in this belief (0-1)
    
    supporting_evidence: list[str]   # Episode IDs that support this
    contradicting_evidence: list[str] # Episode IDs that challenge this
    
    source_type: str                 # "lived_experience", "told_by_someone", "assumption", "reflection"
    source_agent: str                # If told by someone
    
    first_formed: int                # Day number
    last_reinforced: int
    last_challenged: int
    
    is_core_belief: bool             # Core beliefs resist change much more

class BeliefCategories:
    # About the world
    WORLD_WORKS = "how_the_world_works"        # "People are generally selfish"
    COMMUNITY = "about_our_community"           # "This town needs a leader"
    RESOURCES = "about_resources"               # "There's enough food if we share"
    RULES = "about_rules_and_norms"             # "The tax system is unfair"
    
    # About other people
    PERSON_MODEL = "about_a_person"             # "Eleanor is controlling"
    GROUP_MODEL = "about_a_group"               # "The Kowalskis stick to themselves"
    
    # About self
    SELF_ABILITY = "about_my_abilities"          # "I'm good at building things"
    SELF_WORTH = "about_my_worth"               # "People respect me here"
    SELF_ROLE = "about_my_role"                  # "I'm the one who keeps the peace"
    
    # About how things should be
    MORAL = "moral_belief"                       # "Everyone should contribute equally"
    POLITICAL = "political_belief"               # "We need elected leadership"
    PRACTICAL = "practical_belief"               # "Barter works better than currency"

class BeliefSystem:
    beliefs: dict[str, Belief] = {}
    
    def integrate_new_experience(self, episode: Episode):
        """
        After a new experience, check if any beliefs are 
        confirmed or challenged.
        """
        relevant_beliefs = self.get_beliefs_relevant_to(episode)
        
        for belief in relevant_beliefs:
            alignment = self.assess_alignment(belief, episode)
            
            if alignment > 0.5:
                # Experience confirms the belief
                belief.confidence = min(1.0, belief.confidence + 0.03)
                belief.supporting_evidence.append(episode.id)
                belief.last_reinforced = episode.day_number
                
            elif alignment < -0.5:
                # Experience challenges the belief
                # Resistance to change based on confidence, emotional charge, and whether it's core
                resistance = (
                    belief.confidence * 0.3 + 
                    belief.emotional_charge * 0.3 + 
                    (0.3 if belief.is_core_belief else 0.0)
                )
                change = 0.05 * (1.0 - resistance)
                belief.confidence = max(0.0, belief.confidence - change)
                belief.contradicting_evidence.append(episode.id)
                belief.last_challenged = episode.day_number
                
                # If confidence drops low enough, mark for questioning
                if belief.confidence < 0.3:
                    belief.is_actively_questioned = True
    
    def get_beliefs_for_prompt(self, context: str, max_beliefs: int = 5) -> str:
        """
        Return the most relevant beliefs for a decision context.
        These replace raw memories in the decision prompt.
        """
        relevant = self.get_beliefs_relevant_to_context(context)
        sorted_beliefs = sorted(relevant, key=lambda b: b.confidence * (1 + b.emotional_charge), reverse=True)
        
        lines = []
        for belief in sorted_beliefs[:max_beliefs]:
            certainty = "strongly believe" if belief.confidence > 0.7 else "think" if belief.confidence > 0.4 else "suspect"
            lines.append(f"- I {certainty}: \"{belief.content}\"")
            if belief.is_actively_questioned:
                lines.append(f"  (Though I'm not so sure about this anymore)")
        
        return "\n".join(lines)
```

---

## Layer 5: Mental Models of Others (Theory of Mind)

### What It Is

Each agent builds and maintains an internal model of every person they know. These models can be wrong. They're built from observation, conversation, and gossip — and they can be updated or reinforced through experience.

### Implementation

```python
class MentalModel:
    target: str                      # Who this model is about
    
    # Personality model — who do I think they are?
    perceived_personality: str        # Free-text description
    perceived_values: list[str]      # What I think they care about
    perceived_fears: list[str]       # What I think they're afraid of
    perceived_strengths: list[str]   # What they're good at
    perceived_weaknesses: list[str]  # Where they struggle
    
    # Behavioral prediction — how do I think they'll act?
    how_they_handle_conflict: str
    how_they_handle_stress: str
    how_they_respond_to_kindness: str
    how_they_respond_to_authority: str
    what_motivates_them: str
    what_triggers_them: str
    
    # My assessment
    trustworthiness: float           # 0-1: How much can I rely on what they say?
    competence: float                # 0-1: How capable are they?
    predictability: float            # 0-1: How well do I understand them?
    alignment_with_me: float         # -1 to 1: Do we want the same things?
    
    # Status tracking
    what_i_think_they_think_of_me: str  # Meta-cognition
    current_suspected_goals: list[str]
    secrets_i_think_they_have: list[str]
    
    last_updated: int
    update_count: int
    
    async def update_from_interaction(self, interaction, agent):
        """After interacting with this person, update the model."""
        
        prompt = f"""
You are {agent.name}. You just had an interaction with {self.target}.

What happened: {interaction.summary}
Their exact words: {interaction.get_other_speech(agent.name)}
Their tone: {interaction.get_other_tone(agent.name)}
Their body language: {interaction.get_other_body_language(agent.name)}

Your CURRENT model of {self.target}:
Personality: {self.perceived_personality}
Values: {self.perceived_values}
What motivates them: {self.what_motivates_them}
How trustworthy: {self.trustworthiness}/1.0
What you think they think of you: {self.what_i_think_they_think_of_me}

Based on this interaction, has your understanding of {self.target} changed?
Be specific about what shifted and why. If nothing changed, say so — 
not every interaction reveals something new.

Return JSON:
{{
    "personality_update": "new observation or null",
    "motivation_update": "new insight into what drives them, or null",
    "trust_shift": 0.0 (number between -0.1 and 0.1),
    "competence_shift": 0.0,
    "what_they_think_of_me_update": "revised assessment or null",
    "new_suspected_goal": "something you think they're working toward, or null",
    "new_suspected_secret": "something they might be hiding, or null",
    "prediction": "based on this interaction, what do you think they'll do next?"
}}
"""
        result = await llm_call(prompt)
        
        if result.get("personality_update"):
            self.perceived_personality += f" {result['personality_update']}"
        if result.get("motivation_update"):
            self.what_motivates_them = result["motivation_update"]
        self.trustworthiness = max(0, min(1, self.trustworthiness + result.get("trust_shift", 0)))
        self.competence = max(0, min(1, self.competence + result.get("competence_shift", 0)))
        if result.get("what_they_think_of_me_update"):
            self.what_i_think_they_think_of_me = result["what_they_think_of_me_update"]
        if result.get("new_suspected_goal"):
            self.current_suspected_goals.append(result["new_suspected_goal"])
        if result.get("new_suspected_secret"):
            self.secrets_i_think_they_have.append(result["new_suspected_secret"])
        
        self.last_updated = current_tick()
        self.update_count += 1
```

---

## Layer 6: World Understanding

### What It Is

The agent's evolving knowledge of their physical and social world. This is especially important in Polis because the world starts unknown and agents must discover everything — where resources are, what the buildings are used for, who claims what, what rules exist.

```python
class WorldUnderstanding:
    # Physical knowledge (discovered through exploration)
    known_locations: dict = {}           # Location → what I know about it
    known_resources: dict = {}           # Resource → where I've found it, how much
    known_hazards: list = []             # Things I've learned are dangerous
    mental_map_completeness: float = 0.0 # How well I know the geography (0-1)
    
    # Social knowledge (learned through observation and conversation)
    known_claims: dict = {}              # Who claims which space
    known_roles: dict = {}               # Who does what ("John grows food")
    known_alliances: list = []           # Who is aligned with whom
    known_conflicts: list = []           # Who is in conflict with whom
    perceived_power_structure: str = ""  # Who has influence and why
    
    # Institutional knowledge
    known_rules: list = []               # Rules I'm aware of
    known_institutions: list = []        # Institutions I know about
    known_norms: list = []               # Social expectations I've observed
    
    # Economic knowledge
    known_trade_patterns: list = []      # Who trades what with whom
    known_prices: dict = {}              # What things are worth (in my experience)
    known_currency: str = None           # What's used as money, if anything
    
    # Skill knowledge
    discovered_skills: dict = {}         # Skills I've tried and results
    known_recipes: list = []             # Things I know how to make
    known_techniques: list = []          # Methods I've learned
    
    def learn_from_exploration(self, location, discoveries):
        """Update knowledge from visiting a new place."""
        self.known_locations[location] = discoveries
        self.mental_map_completeness = len(self.known_locations) / total_locations
    
    def learn_from_conversation(self, source_agent, information, trust_in_source):
        """Update knowledge from what someone told me."""
        # Information from trusted sources is stored with higher confidence
        # Information from untrusted sources is stored but flagged
        pass
    
    def learn_from_observation(self, what_i_saw):
        """Update knowledge from watching the world."""
        pass
    
    def get_knowledge_gaps(self) -> list[str]:
        """What don't I know that I probably should?"""
        gaps = []
        if self.mental_map_completeness < 0.5:
            gaps.append("I haven't explored much of the area yet")
        if not self.known_currency:
            gaps.append("I'm not sure if we have any system for trading")
        if not self.perceived_power_structure:
            gaps.append("I don't really know who's in charge around here")
        if len(self.known_roles) < 5:
            gaps.append("I don't know what everyone does around here")
        return gaps
```

---

## Layer 7: Identity (Self-Concept)

### What It Is

The agent's evolving sense of who they are in this community. Unlike personality (which is static), identity is dynamic — it forms through experience and can change.

```python
class Identity:
    # Core identity elements
    self_narrative: str = ""          # "I'm a builder. I came here to start over."
    role_in_community: str = None     # Emerges from reflection: "the farmer", "the peacekeeper"
    sense_of_belonging: float = 0.0   # 0 (outsider) to 1 (this is home)
    sense_of_purpose: float = 0.0     # 0 (lost) to 1 (know exactly why I'm here)
    
    # Values in practice (may differ from stated values)
    # Tracked by observing what the agent actually prioritizes
    demonstrated_values: dict = {}    # {"helping_others": 0.7, "self_interest": 0.3}
    
    # Reputation awareness — what I think others think of me
    perceived_reputation: str = ""    # "People see me as reliable but quiet"
    reputation_anxiety: float = 0.0   # How much I worry about what others think
    
    # Life satisfaction
    satisfaction_with_role: float = 0.5
    satisfaction_with_relationships: float = 0.5
    satisfaction_with_community: float = 0.5
    overall_life_satisfaction: float = 0.5
    
    async def update_from_reflection(self, agent, recent_episodes, recent_reflections):
        """
        Periodic identity update — am I becoming who I want to be?
        Called during evening reflection.
        """
        prompt = f"""
You are {agent.name}, reflecting on who you're becoming in this community.

Your original backstory: {agent.backstory}
Your values: {agent.values}
Your fears: {agent.fears}

What you've been doing lately:
{agent.skill_memory.get_activity_summary(last_n_days=7)}

How people have been treating you:
{agent.get_recent_social_summary()}

Your current role: {self.role_in_community or "You don't have a clear role yet"}
Your current narrative: {self.self_narrative or "You're still figuring things out"}

Reflect honestly:
- Are you becoming who you want to be here?
- Do you feel like you belong?
- What's your place in this community?
- Are you satisfied with how things are going?
- Is there a gap between who you are and who you want to be?

Return JSON:
{{
    "updated_self_narrative": "1-2 sentences: who am I becoming?",
    "role_in_community": "how would you describe your role? (or 'still finding it')",
    "sense_of_belonging": 0.0-1.0,
    "sense_of_purpose": 0.0-1.0,
    "satisfaction_with_role": 0.0-1.0,
    "satisfaction_with_relationships": 0.0-1.0,
    "satisfaction_with_community": 0.0-1.0,
    "perceived_reputation": "what you think others think of you",
    "identity_tension": "any gap between who you are and who you want to be, or null",
    "aspiration": "what you want your role to be in the future, if different from now"
}}
"""
        result = await llm_call(prompt)
        
        self.self_narrative = result["updated_self_narrative"]
        self.role_in_community = result["role_in_community"]
        self.sense_of_belonging = result["sense_of_belonging"]
        self.sense_of_purpose = result["sense_of_purpose"]
        self.satisfaction_with_role = result["satisfaction_with_role"]
        self.satisfaction_with_relationships = result["satisfaction_with_relationships"]
        self.satisfaction_with_community = result["satisfaction_with_community"]
        self.perceived_reputation = result["perceived_reputation"]
        self.overall_life_satisfaction = (
            self.satisfaction_with_role * 0.3 +
            self.satisfaction_with_relationships * 0.3 +
            self.satisfaction_with_community * 0.2 +
            self.sense_of_purpose * 0.2
        )
        
        # Identity tension can generate new goals
        if result.get("identity_tension"):
            agent.generate_goal_from_tension(result["identity_tension"])
        if result.get("aspiration"):
            agent.generate_goal_from_aspiration(result["aspiration"])
```

---

## The Decision Moment: When Everything Comes Together

### The Full Decision Prompt

When the novelty detector fires and the agent needs to actually think about what to do, ALL layers contribute to the prompt. But they contribute in their processed form — beliefs instead of raw episodes, emotional descriptions instead of numerical values, mental models instead of interaction logs.

```python
async def make_decision(agent, novel_situation) -> dict:
    """
    The moment of conscious deliberation.
    All layers of the mind contribute to this decision.
    """
    
    prompt = f"""
You are {agent.name}. You need to decide what to do.

═══ WHO YOU ARE ═══
{agent.identity.self_narrative or agent.backstory}
Your values: {', '.join(agent.values)}
Your deepest fears: {', '.join(agent.fears)}
Your role here: {agent.identity.role_in_community or "You're still finding your place"}

═══ WHAT YOU'RE EXPERIENCING RIGHT NOW ═══
{agent.attention.get_prompt_context()}

═══ HOW YOU FEEL ═══
{agent.emotional_state.get_prompt_description()}
Physical state: {agent.drives.get_physical_description()}

═══ WHAT JUST HAPPENED (the thing that made you stop and think) ═══
{novel_situation.description}

═══ WHAT YOU BELIEVE (your deepest convictions relevant to this moment) ═══
{agent.belief_system.get_beliefs_for_prompt(novel_situation.description)}

═══ YOUR UNDERSTANDING OF THE PEOPLE INVOLVED ═══
{agent.get_mental_model_summaries(novel_situation.agents_involved)}

═══ WHAT YOU KNOW ABOUT HOW THINGS WORK HERE ═══
{agent.world_understanding.get_relevant_context(novel_situation)}
Current community rules: {agent.world_understanding.known_rules or "No formal rules exist yet"}

═══ YOUR CURRENT GOALS ═══
{agent.format_goals()}

═══ YOUR SKILLS AND CAPABILITIES ═══
{agent.skill_memory.get_capability_summary()}
Physical: Strength {agent.physical_traits['strength']}, 
         Endurance {agent.physical_traits['endurance']}, 
         Dexterity {agent.physical_traits['dexterity']}

What do you do?

Think as {agent.name} would ACTUALLY think — not what's optimal, not what's 
heroic, but what a real person with these emotions, beliefs, drives, and 
personality would do. Consider:

- Your emotional state might override your rational judgment
- Your drives (hunger, tiredness, loneliness) affect your patience and risk tolerance
- Your beliefs filter how you interpret this situation
- Your mental model of the people involved shapes how you approach them
- Your identity and role affect what actions feel "like you"
- You might avoid something difficult even if you know you should face it
- You might act impulsively because you're frustrated or excited
- You might not know the best course of action and decide to wait and see

You can also do something COMPLETELY NOVEL — propose a new rule, create 
something that doesn't exist yet, start a new tradition, organize people 
in a new way, or do anything else a creative human might think of. You're 
not limited to pre-existing options.

Return JSON:
{{
    "inner_deliberation": "2-3 sentences of your actual thought process — the messy, honest reasoning",
    "action": {{
        "type": "what you decide to do (can be anything — not limited to a fixed list)",
        "description": "detailed description of the action",
        "target_location": "where, if moving",
        "target_agent": "who, if interacting with someone",
        "item": "what item is involved, if any",
        "speech": "what you say out loud, or null",
        "is_novel_action": true/false
    }},
    "inner_thought": "what you're thinking as you do this (1-2 sentences, shown in Mind tab)",
    "emotion_after_deciding": "how making this decision makes you feel",
    "confidence_in_decision": 0.0-1.0,
    "what_could_go_wrong": "your worry about this decision, or null",
    "belief_update": "if this moment changes a belief, describe it, or null",
    "goal_update": "if a new goal emerged or an old one changed, describe it, or null"
}}
"""
    result = await llm_call(prompt)
    
    # Process the decision's effects on the agent's mind
    if result.get("belief_update"):
        agent.belief_system.process_update(result["belief_update"])
    if result.get("goal_update"):
        agent.process_goal_update(result["goal_update"])
    if result.get("emotion_after_deciding"):
        agent.emotional_state.apply_shift_from_description(result["emotion_after_deciding"])
    
    # The inner_deliberation becomes a memory
    agent.episodic_memory.append(Episode(
        content=f"I had to make a decision: {novel_situation.description}. I decided to {result['action']['description']}. My reasoning: {result['inner_deliberation']}",
        emotional_intensity=0.4,
        memory_type="decision",
        my_interpretation=result["inner_thought"]
    ))
    
    return result
```

---

## Evening Reflection: Where The Mind Consolidates

### What It Is

Every evening, the agent processes their day. This is the most important cognitive event because it's where episodes become beliefs, mental models update, identity evolves, and tomorrow's intentions form.

```python
async def evening_reflection(agent) -> dict:
    """
    End-of-day processing. The agent alone with their thoughts.
    This is where the mind grows and changes.
    """
    
    todays_episodes = agent.episodic_memory.get_episodes_from_today()
    todays_conversations = [e for e in todays_episodes if e.memory_type == "conversation"]
    todays_decisions = [e for e in todays_episodes if e.memory_type == "decision"]
    todays_observations = [e for e in todays_episodes if e.memory_type in ["observation", "overheard"]]
    
    prompt = f"""
You are {agent.name}. The day is ending. You're settling in for the night 
and your mind is processing the day.

═══ WHO YOU ARE RIGHT NOW ═══
{agent.identity.self_narrative}
Day {agent.world_state.day_number} in this community.
Your current emotional state: {agent.emotional_state.get_full_description()}

═══ WHAT HAPPENED TODAY ═══

Conversations:
{[f"- Talked with {e.agents_involved}: {e.content}" for e in todays_conversations]}

Decisions I made:
{[f"- {e.content}" for e in todays_decisions]}

Things I noticed:
{[f"- {e.content}" for e in todays_observations]}

═══ MY CURRENT BELIEFS THAT MIGHT BE AFFECTED ═══
{agent.belief_system.get_all_beliefs_summary()}

═══ HOW I SEE THE PEOPLE I INTERACTED WITH TODAY ═══
{agent.get_mental_model_summaries([e.agents_involved[0] for e in todays_conversations if e.agents_involved])}

═══ MY SENSE OF SELF ═══
Role: {agent.identity.role_in_community}
Belonging: {agent.identity.sense_of_belonging}
Purpose: {agent.identity.sense_of_purpose}
Life satisfaction: {agent.identity.overall_life_satisfaction}

Reflect honestly as {agent.name} would, alone with their thoughts. Consider:

1. How did today make me feel overall? 
2. Did anything change how I see someone?
3. Did anything change how I see myself or my role here?
4. Did any of my beliefs get confirmed or challenged?
5. Is there something unresolved that's going to keep me up tonight?
6. What do I want to make sure I do tomorrow?
7. Is there something I've been avoiding that I should face?
8. Am I becoming who I want to be here?

Not every day needs deep insights. Some days the reflection is just 
"tired day, did my work, nothing special." Be honest about whether 
today actually changed anything.

Return JSON:
{{
    "evening_mood": "how you feel as the day ends",
    "day_summary": "1-2 sentences — how would you describe today?",
    "emotional_processing": "what emotions from today are you still sitting with?",
    
    "new_beliefs": [
        {{"content": "...", "confidence": 0.X, "category": "...", "source": "lived_experience"}}
    ],
    "updated_beliefs": [
        {{"belief_content": "...", "new_confidence": 0.X, "reason": "..."}}
    ],
    "challenged_beliefs": [
        {{"belief_content": "...", "challenge": "what made me question this"}}
    ],
    
    "updated_mental_models": [
        {{"agent": "...", "update": "...", "reason": "..."}}
    ],
    
    "self_reflection": "something I realized about myself today, or null",
    "identity_shift": "has my sense of who I am here changed? How?",
    
    "unresolved_tension": "something that's going to keep me up tonight, or null",
    "tomorrow_intention": "one thing I want to make sure I do tomorrow",
    "thing_im_avoiding": "something I should do but keep putting off, or null",
    
    "world_understanding_update": "anything I learned about how things work here, or null",
    
    "creative_idea": "did I have any new ideas for something to build, organize, create, or propose? Or null."
}}
"""
    result = await llm_call(prompt)
    
    # Process all reflection outputs
    
    # New beliefs
    for belief_data in result.get("new_beliefs", []):
        agent.belief_system.add_belief(Belief(**belief_data))
    
    # Updated beliefs
    for update in result.get("updated_beliefs", []):
        agent.belief_system.update_confidence(update["belief_content"], update["new_confidence"])
    
    # Challenged beliefs
    for challenge in result.get("challenged_beliefs", []):
        agent.belief_system.flag_as_questioned(challenge["belief_content"])
    
    # Updated mental models
    for model_update in result.get("updated_mental_models", []):
        agent.mental_models[model_update["agent"]].apply_reflection_update(model_update)
    
    # Identity update
    if result.get("identity_shift"):
        agent.identity.process_shift(result["identity_shift"])
    if result.get("self_reflection"):
        agent.identity.integrate_self_insight(result["self_reflection"])
    
    # Set up tomorrow
    if result.get("unresolved_tension"):
        agent.attention.background_worry = result["unresolved_tension"]
    if result.get("tomorrow_intention"):
        agent.tomorrow_priority = result["tomorrow_intention"]
    if result.get("thing_im_avoiding"):
        agent.attention.unfinished_business = result["thing_im_avoiding"]
    
    # Creative ideas feed into the meta-simulation
    if result.get("creative_idea"):
        agent.pending_proposals.append(result["creative_idea"])
    
    # World understanding
    if result.get("world_understanding_update"):
        agent.world_understanding.integrate_insight(result["world_understanding_update"])
    
    # Store the reflection itself as a high-importance memory
    agent.episodic_memory.append(Episode(
        content=f"Evening reflection: {result['day_summary']}",
        emotional_valence=result.get("evening_mood_valence", 0.0),
        emotional_intensity=0.5,
        memory_type="reflection",
        importance=8
    ))
    
    return result
```

---

## The Complete Cognitive Tick

```
Every tick, the agent mind processes in this order:

1. DRIVES UPDATE (deterministic, no LLM)
   Hunger++, thirst++, rest++, etc.
   Check for critical thresholds.

2. PERCEPTION (no LLM)
   What's in my environment? Who's nearby?
   Feed observations into Attention system.
   Generate observation memories for notable things.

3. ATTENTION UPDATE (no LLM)
   Process new observations, drive signals, emotional signals.
   Update the spotlight. Shift focus if warranted.

4. EMOTIONAL STATE UPDATE (no LLM)
   Decay emotions toward baseline.
   Apply any pending emotional shifts from events.

5. DRIVE INTERRUPT CHECK (no LLM)
   Is any drive above critical? If yes, override plan.

6. NOVELTY DETECTION (no LLM)
   Is anything in my attention novel, threatening, or goal-relevant?

7a. IF NOTHING NOVEL → ROUTINE BEHAVIOR (no LLM)
    Continue current activity. Walk, work, eat, sleep.

7b. IF NOVEL → FULL DECISION (LLM call)
    Construct the decision prompt from all layers.
    Get back action + inner thought + belief/goal updates.
    Feed action to the Action Interpreter.

8. INNER VOICE (LLM call, every 3-5 ticks)
   Generate a background thought.
   Store in inner monologue. Show in Mind tab.

9. MEMORY CREATION (LLM call if significant event)
   If something notable happened, create a subjective memory.
   Score importance. Generate embedding.

10. EVERY EVENING: REFLECTION (LLM call)
    Process the day. Update beliefs, mental models, identity.
    Set tomorrow's intentions. Generate creative ideas.

LLM calls per agent per day:
- Morning plan: 1
- Evening reflection: 1
- Inner voice thoughts: ~15 (every 3-5 ticks during waking hours)
- Novel decisions: 3-8 (depends on how eventful the day is)
- Subjective memory creation: 5-10 (only for significant events)
- Conversation turns: varies wildly (0-20)
- Mental model updates: 1-3

Total: roughly 25-60 LLM calls per agent per game day
With 15 agents: 375-900 LLM calls per game day

At 4o-mini pricing (~$0.0002/call): $0.08-0.18 per game day
Running for 30 days: $2.40-5.40 total
```

---

## What Makes This Different From Just Prompting

The standard approach: dump memories into a prompt, ask what the agent does, execute.

The Polis approach: the agent has a persistent emotional landscape that colors every thought. Beliefs that resist change based on evidence strength and emotional investment. Mental models of others that can be wrong and create realistic misunderstandings. An identity that evolves through experience and reflection. Drives that override rational thinking when urgent. An attention system that determines what the agent is even aware of. Memory distortion that makes two witnesses remember events differently. Background thoughts that reveal the inner life. And all of this feeds into a decision moment that's genuinely messy and human — not an optimization, but a person struggling with their situation.

The difference shows up in behavior. A prompted agent asked "what do you do about John's hunger?" generates a reasonable response. A Polis agent wrestling with John's hunger does it through layers: Ricky's drives (social need → comfort), his beliefs ("John would never accept charity" — confidence 0.9, based on years of observation), his mental model of John (proud, withdraws when struggling), his emotional state (guilt at 0.3, compassion at 0.6), his identity (self-concept: "the one who looks out for people"), and his current attention (John hasn't been to the tavern in 3 days — this has been nagging at him). All of that converges into a specific action (secretly leave food) with a specific emotional texture (inner conflict between wanting to help and respecting John's pride) that emerges from the architecture, not from a single prompt.

That's the difference between a character and a mind.
