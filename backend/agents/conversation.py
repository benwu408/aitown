"""Conversation system — triggers and runs multi-turn LLM conversations between agents."""

import logging
from typing import Optional

from agents.memory import MemoryEntry
from llm.client import llm_client
from llm.prompts import (
    conversation_system_prompt,
    conversation_user_prompt,
    conversation_opener_prompt,
)

logger = logging.getLogger("agentica.conversation")

# Minimum ticks between conversations for an agent
CONVERSATION_COOLDOWN = 15
# Max conversation turns
MAX_TURNS = 4


class ConversationManager:
    def __init__(self):
        self.last_conversation_tick: dict[str, int] = {}
        self.active_conversations: set[frozenset[str]] = set()

    def can_converse(self, agent_a_id: str, agent_b_id: str, tick: int) -> bool:
        """Check if two agents can start a conversation."""
        pair = frozenset({agent_a_id, agent_b_id})
        if pair in self.active_conversations:
            return False

        for aid in [agent_a_id, agent_b_id]:
            last = self.last_conversation_tick.get(aid, -100)
            if tick - last < CONVERSATION_COOLDOWN:
                return False

        return True

    async def run_conversation(
        self, agent_a, agent_b, location: str, time_of_day: str, tick: int, day: int = 0
    ) -> list[dict]:
        """Run a multi-turn conversation between two agents. Returns events."""
        pair = frozenset({agent_a.id, agent_b.id})
        self.active_conversations.add(pair)
        events = []

        try:
            # Agent A opens the conversation
            a_profile = {
                "age": agent_a.profile.age,
                "job": agent_a.profile.job,
                "personality": agent_a.profile.personality,
                "values": agent_a.profile.values,
                "backstory": agent_a.profile.backstory,
                "secrets": agent_a.secrets,
            }
            b_profile = {
                "age": agent_b.profile.age,
                "job": agent_b.profile.job,
                "personality": agent_b.profile.personality,
                "values": agent_b.profile.values,
                "backstory": agent_b.profile.backstory,
                "secrets": agent_b.secrets,
            }

            rel_a = agent_a.relationships.get(agent_b.name, {})
            rel_b = agent_b.relationships.get(agent_a.name, {})
            rel_notes_a = rel_a.get("notes", "Acquaintance")
            rel_notes_b = rel_b.get("notes", "Acquaintance")
            trust_a = rel_a.get("trust", 0.5)
            trust_b = rel_b.get("trust", 0.5)

            a_goals = [g["text"] for g in agent_a.active_goals if g["status"] == "active"]
            b_goals = [g["text"] for g in agent_b.active_goals if g["status"] == "active"]

            # Opening line from Agent A
            sys_prompt = conversation_system_prompt(agent_a.name, a_profile)
            opener_prompt = conversation_opener_prompt(
                agent_a.name,
                agent_b.name,
                location,
                time_of_day,
                agent_a.emotion,
                rel_notes_a,
                agent_a.memory.recent_text(5),
                a_goals,
                agent_a.opinions,
            )

            opener = await llm_client.generate_json(
                sys_prompt, opener_prompt,
                default={"speech": f"Hey {agent_b.name}, how's it going?", "inner_thought": "", "emotion": "neutral"}
            )

            current_speech = opener.get("speech", f"Hello, {agent_b.name}.")
            events.append({
                "type": "agent_speak",
                "agentId": agent_a.id,
                "targetId": agent_b.id,
                "speech": current_speech,
                "location": location,
            })
            events.append({
                "type": "agent_thought",
                "agentId": agent_a.id,
                "thought": opener.get("inner_thought", ""),
            })

            # Store memory for A
            agent_a.memory.add(MemoryEntry(
                tick=tick,
                content=f"I said to {agent_b.name}: \"{current_speech}\"",
                importance=5,
                memory_type="conversation",
                related_agents=[agent_b.name],
                location=location,
            ))

            # Multi-turn exchange
            speakers = [agent_b, agent_a]
            profiles = [b_profile, a_profile]
            rel_notes = [rel_notes_b, rel_notes_a]
            trusts = [trust_b, trust_a]
            goals_list = [b_goals, a_goals]

            for turn in range(MAX_TURNS):
                speaker = speakers[turn % 2]
                listener = speakers[(turn + 1) % 2]
                sp_profile = profiles[turn % 2]
                rn = rel_notes[turn % 2]
                tr = trusts[turn % 2]
                gl = goals_list[turn % 2]

                sys_p = conversation_system_prompt(speaker.name, sp_profile)
                user_p = conversation_user_prompt(
                    speaker.name,
                    listener.name,
                    current_speech,
                    location,
                    time_of_day,
                    speaker.emotion,
                    rn,
                    speaker.memory.recent_text(5),
                    trust_level=tr,
                    opinions=speaker.opinions,
                    active_goals=gl,
                )

                response = await llm_client.generate_json(
                    sys_p, user_p,
                    default={"speech": "Hmm, interesting.", "inner_thought": "", "emotion": "neutral", "relationship_change": "neutral", "wants_to_end_conversation": False}
                )

                current_speech = response.get("speech", "...")
                events.append({
                    "type": "agent_speak",
                    "agentId": speaker.id,
                    "targetId": listener.id,
                    "speech": current_speech,
                    "location": location,
                })

                thought = response.get("inner_thought", "")
                if thought:
                    events.append({
                        "type": "agent_thought",
                        "agentId": speaker.id,
                        "thought": thought,
                    })

                # Store memory
                speaker.memory.add(MemoryEntry(
                    tick=tick,
                    content=f"{listener.name} said: \"{response.get('speech', '...')}\" I replied: \"{current_speech}\"" if turn > 0 else f"{listener.name} said: \"{current_speech}\"",
                    importance=6,
                    memory_type="conversation",
                    related_agents=[listener.name],
                    location=location,
                ))

                # Update relationship
                rel_change = response.get("relationship_change", "neutral")
                if rel_change == "slightly_positive":
                    self._update_relationship(speaker, listener.name, 0.05)
                elif rel_change == "slightly_negative":
                    self._update_relationship(speaker, listener.name, -0.05)

                # Update emotion
                emotion = response.get("emotion", speaker.emotion)
                speaker.emotion = emotion
                speaker.inner_thought = thought

                # Handle secret sharing
                shared_secret = response.get("shared_secret")
                if shared_secret and isinstance(shared_secret, str) and shared_secret != "null":
                    for secret in speaker.secrets:
                        if listener.name not in secret.get("known_by", []):
                            secret["known_by"].append(listener.name)
                            secret["discovered_tick"] = secret.get("discovered_tick") or tick
                            listener.memory.add(MemoryEntry(
                                tick=tick,
                                content=f"{speaker.name} confided in me: {shared_secret}",
                                importance=9.0,
                                memory_type="conversation",
                                related_agents=[speaker.name],
                                location=location,
                            ))
                            events.append({
                                "type": "agent_thought",
                                "agentId": listener.id,
                                "thought": f"{speaker.name} shared a secret with me...",
                            })
                            # Check if secret is now public (3+ know)
                            if len(secret["known_by"]) >= 3:
                                events.append({
                                    "type": "system_event",
                                    "eventType": "secret_exposed",
                                    "label": "Secret Exposed",
                                    "description": f"{speaker.name}'s secret has become public knowledge!",
                                })
                            break  # Only share one secret per conversation

                # Handle opinion expression
                opinion_expr = response.get("opinion_expressed")
                if opinion_expr and isinstance(opinion_expr, str) and opinion_expr != "null":
                    # Listener's opinion may shift slightly toward speaker if trusted
                    listener_trust = listener.relationships.get(speaker.name, {}).get("trust", 0.5)
                    if listener_trust > 0.4:
                        for topic in listener.opinions:
                            if topic in opinion_expr.lower():
                                shift = 0.05 if listener_trust > 0.6 else 0.02
                                # Shift toward speaker's stance
                                speaker_stance = speaker.opinions.get(topic, {}).get("stance", 0)
                                if speaker_stance > 0:
                                    listener.opinions[topic]["stance"] = min(1.0, listener.opinions[topic]["stance"] + shift)
                                else:
                                    listener.opinions[topic]["stance"] = max(-1.0, listener.opinions[topic]["stance"] - shift)
                                break

                # Handle gossip sharing
                gossip = response.get("gossip_to_share")
                if gossip and isinstance(gossip, str) and gossip != "null":
                    from systems.social import social_system
                    # Figure out who the gossip is about
                    gossip_about = None
                    for other_agent in [agent_a, agent_b]:
                        for a_name in [a.name for a in [agent_a, agent_b]]:
                            pass  # Skip self
                    # Try to find a name mentioned in the gossip
                    all_names = {a.name: a for a in [agent_a, agent_b]}
                    for agent_check in list(self.last_conversation_tick.keys()):
                        pass
                    # Just use the gossip content directly
                    social_system.add_gossip(
                        source=speaker.name,
                        about=gossip.split(" ")[0] if " " in gossip else listener.name,
                        content=gossip,
                        importance=6.0,
                    )
                    # Store as memory for the listener
                    listener.memory.add(MemoryEntry(
                        tick=tick,
                        content=f"{speaker.name} told me: {gossip}",
                        importance=6.0,
                        memory_type="conversation",
                        related_agents=[speaker.name],
                        location=location,
                    ))
                    events.append({
                        "type": "gossip",
                        "agentId": speaker.id,
                        "about": listener.name,
                        "content": f"{speaker.name} shared gossip: {gossip[:60]}",
                    })

                # Handle proposed activity (meetup suggestion)
                proposed = response.get("proposed_activity")
                if proposed and proposed != "null":
                    # Parse the proposal — supports both dict and string format
                    description = ""
                    meet_location = "tavern"
                    meet_hour = 12
                    involves = []
                    is_recurring = False

                    from simulation.world import BUILDING_MAP
                    valid_locs = set(BUILDING_MAP.keys())

                    if isinstance(proposed, dict):
                        # Structured format from LLM
                        description = proposed.get("description", "Meet up")
                        loc = proposed.get("location", "")
                        if loc in valid_locs:
                            meet_location = loc
                        time_hint = str(proposed.get("time", "noon")).lower()
                        involves = proposed.get("involves", [])
                        is_recurring = proposed.get("recurring", False)
                    elif isinstance(proposed, str):
                        description = proposed
                        time_hint = proposed.lower()
                    else:
                        description = str(proposed)
                        time_hint = ""

                    # Parse time from hint
                    if isinstance(proposed, str) or (isinstance(proposed, dict) and proposed.get("location", "") not in valid_locs):
                        # Keyword fallback for location
                        text = description.lower() if isinstance(proposed, dict) else proposed.lower()
                        loc_hints = {
                            "tavern": "tavern", "pub": "tavern", "drinks": "tavern", "ale": "tavern",
                            "lunch": "bakery", "bakery": "bakery", "bread": "bakery",
                            "park": "park", "walk": "park", "stroll": "park", "pond": "pond",
                            "church": "church", "pray": "church", "farm": "farm",
                            "store": "general_store", "shop": "general_store",
                            "school": "school", "workshop": "workshop", "town_hall": "town_hall",
                        }
                        for hint, loc in loc_hints.items():
                            if hint in text:
                                meet_location = loc
                                break

                    # Parse time
                    try:
                        meet_hour = int(time_hint)
                    except (ValueError, TypeError):
                        if "morning" in time_hint or "breakfast" in time_hint:
                            meet_hour = 8
                        elif "afternoon" in time_hint:
                            meet_hour = 15
                        elif "evening" in time_hint or "dinner" in time_hint or "after work" in time_hint:
                            meet_hour = 18
                        elif "night" in time_hint:
                            meet_hour = 20
                        else:
                            meet_hour = 12  # default noon

                    if isinstance(proposed, str):
                        is_recurring = "every" in proposed.lower() or "weekly" in proposed.lower()

                    # Create commitments for both speakers
                    tomorrow = day + 1 if day > 0 else tick // 288 + 2
                    commitment = {
                        "what": description,
                        "where": meet_location,
                        "when": meet_hour,
                        "with": [listener.name] + [n for n in involves if n != speaker.name and n != listener.name],
                        "day": tomorrow,
                        "recurring": is_recurring,
                    }
                    # Deduplicate: skip if similar commitment already exists
                    speaker_dup = any(
                        c.get("where") == meet_location and c.get("when") == meet_hour
                        and listener.name in c.get("with", [])
                        for c in speaker.social_commitments
                    )
                    if not speaker_dup:
                        speaker.social_commitments.append(commitment)
                    listener_commitment = dict(commitment)
                    listener_commitment["with"] = [speaker.name] + [n for n in involves if n != speaker.name and n != listener.name]
                    listener_dup = any(
                        c.get("where") == meet_location and c.get("when") == meet_hour
                        and speaker.name in c.get("with", [])
                        for c in listener.social_commitments
                    )
                    if not listener_dup:
                        listener.social_commitments.append(listener_commitment)

                    # Also create commitments for any third parties involved
                    # (they won't know about it from conversation, but we add it so they show up)
                    for name in involves:
                        if name != speaker.name and name != listener.name:
                            # We'd need access to the agents dict here — skip for now
                            pass

                    speaker.memory.add(MemoryEntry(
                        tick=tick,
                        content=f"Made plans with {listener.name}: {proposed}",
                        importance=7.0,
                        memory_type="action",
                        related_agents=[listener.name],
                        location=location,
                    ))
                    listener.memory.add(MemoryEntry(
                        tick=tick,
                        content=f"Made plans with {speaker.name}: {proposed}",
                        importance=7.0,
                        memory_type="action",
                        related_agents=[speaker.name],
                        location=location,
                    ))
                    events.append({
                        "type": "system_event",
                        "eventType": "plans_made",
                        "label": "Plans Made",
                        "description": f"{speaker.name} and {listener.name} planned: {proposed}",
                    })
                    logger.info(f"Plans made: {speaker.name} & {listener.name}: {proposed}")

                if response.get("wants_to_end_conversation", False):
                    break

            logger.info(f"Conversation between {agent_a.name} and {agent_b.name}: {len(events)} events")

        except Exception as e:
            logger.error(f"Conversation failed: {e}")
        finally:
            self.active_conversations.discard(pair)
            self.last_conversation_tick[agent_a.id] = tick
            self.last_conversation_tick[agent_b.id] = tick

        return events

    def _update_relationship(self, agent, other_name: str, delta: float):
        if other_name not in agent.relationships:
            agent.relationships[other_name] = {"sentiment": 0.5, "trust": 0.5, "familiarity": 0.1, "notes": "New acquaintance"}
        rel = agent.relationships[other_name]
        rel["sentiment"] = max(-1.0, min(1.0, rel.get("sentiment", 0.5) + delta))
        # Trust changes: positive interactions build trust slowly, negative erode it faster
        if delta > 0:
            rel["trust"] = min(1.0, rel.get("trust", 0.5) + 0.02)
        elif delta < 0:
            rel["trust"] = max(0.0, rel.get("trust", 0.5) - 0.03)
        # Familiarity always increases with interaction
        rel["familiarity"] = min(1.0, rel.get("familiarity", 0.1) + 0.02)


conversation_manager = ConversationManager()
