"""Agent cognitive architecture — perception, reflection, planning, decision-making."""

import logging
from typing import Optional

from agents.memory import MemoryEntry
from llm.client import llm_client
from llm.prompts import (
    conversation_system_prompt,
    reflection_prompt,
    daily_plan_prompt,
    decision_prompt,
)

logger = logging.getLogger("agentica.cognition")


class CognitionSystem:
    def __init__(self):
        self._reflection_counter: dict[str, int] = {}
        self._plan_day: dict[str, int] = {}

    async def maybe_reflect(self, agent, tick: int, interval: int = 50) -> list[dict]:
        """Generate reflections if enough ticks have passed."""
        events = []
        last = self._reflection_counter.get(agent.id, 0)

        if tick - last < interval:
            return events

        self._reflection_counter[agent.id] = tick

        recent = agent.memory.recent_text(20)
        if len(recent) < 3:
            return events

        sys_prompt = conversation_system_prompt(agent.name, {
            "age": agent.profile.age,
            "job": agent.profile.job,
            "personality": agent.profile.personality,
            "values": agent.profile.values,
            "backstory": agent.profile.backstory,
        })

        result = await llm_client.generate_json(
            sys_prompt,
            reflection_prompt(agent.name, recent),
            default={"reflections": []},
        )

        reflections = result.get("reflections", [])
        for r in reflections[:3]:
            if isinstance(r, str) and r.strip():
                agent.memory.add(MemoryEntry(
                    tick=tick,
                    content=r,
                    importance=8.0,
                    memory_type="reflection",
                ))
                events.append({
                    "type": "agent_thought",
                    "agentId": agent.id,
                    "thought": r,
                })
                agent.inner_thought = r

        logger.info(f"{agent.name} reflected: {len(reflections)} insights")
        return events

    async def maybe_plan(self, agent, day: int, tick: int) -> list[dict]:
        """Generate daily plan at the start of each day."""
        events = []
        last_plan_day = self._plan_day.get(agent.id, 0)

        if day <= last_plan_day:
            return events

        self._plan_day[agent.id] = day

        profile = {
            "age": agent.profile.age,
            "job": agent.profile.job,
            "personality": agent.profile.personality,
            "values": agent.profile.values,
            "backstory": agent.profile.backstory,
            "goals": agent.profile.goals,
        }

        sys_prompt = conversation_system_prompt(agent.name, profile)
        result = await llm_client.generate_json(
            sys_prompt,
            daily_plan_prompt(
                agent.name, profile,
                agent.memory.reflections(5),
                agent.profile.goals,
                day,
            ),
            default={"plan": "Go about my usual routine.", "priority_goal": ""},
        )

        plan = result.get("plan", "")
        if plan:
            agent.daily_plan = plan
            agent.memory.add(MemoryEntry(
                tick=tick,
                content=f"Today's plan: {plan}",
                importance=6.0,
                memory_type="action",
            ))
            events.append({
                "type": "agent_thought",
                "agentId": agent.id,
                "thought": f"Plan: {plan}",
            })

        return events


cognition_system = CognitionSystem()
