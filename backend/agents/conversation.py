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
        self, agent_a, agent_b, location: str, time_of_day: str, tick: int
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
            }
            b_profile = {
                "age": agent_b.profile.age,
                "job": agent_b.profile.job,
                "personality": agent_b.profile.personality,
                "values": agent_b.profile.values,
                "backstory": agent_b.profile.backstory,
            }

            rel_a = agent_a.relationships.get(agent_b.name, {})
            rel_b = agent_b.relationships.get(agent_a.name, {})
            rel_notes_a = rel_a.get("notes", "Acquaintance")
            rel_notes_b = rel_b.get("notes", "Acquaintance")

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
                agent_a.profile.goals,
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
            speakers = [agent_b, agent_a]  # Alternate starting with B responding
            profiles = [b_profile, a_profile]
            rel_notes = [rel_notes_b, rel_notes_a]

            for turn in range(MAX_TURNS):
                speaker = speakers[turn % 2]
                listener = speakers[(turn + 1) % 2]
                sp_profile = profiles[turn % 2]
                rn = rel_notes[turn % 2]

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
