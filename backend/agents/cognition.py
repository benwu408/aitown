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

MAX_ACTIVE_GOALS = 5


class CognitionSystem:
    def __init__(self):
        self._reflection_counter: dict[str, int] = {}
        self._plan_day: dict[str, int] = {}

    async def maybe_reflect(self, agent, tick: int, interval: int = 80, day: int = 0) -> list[dict]:
        """Generate reflections, update goals and opinions."""
        events = []
        last = self._reflection_counter.get(agent.id, 0)

        if tick - last < interval:
            return events

        self._reflection_counter[agent.id] = tick

        recent = agent.memory.recent_text(20)
        if len(recent) < 3:
            return events

        profile = {
            "age": agent.profile.age,
            "job": agent.profile.job,
            "personality": agent.profile.personality,
            "values": agent.profile.values,
            "backstory": agent.profile.backstory,
            "secrets": agent.secrets,
        }
        sys_prompt = conversation_system_prompt(agent.name, profile)

        # Build social context — random selection of other agents' status
        import random as _rand
        all_agents = list(agent.relationships.keys())
        _rand.shuffle(all_agents)
        social_lines = []
        for other_name in all_agents[:4]:
            rel = agent.relationships.get(other_name, {})
            sentiment = rel.get("sentiment", 0.5)
            desc = "close friend" if sentiment > 0.7 else "acquaintance" if sentiment > 0.4 else "not close"
            social_lines.append(f"- {other_name} ({desc})")
        social_ctx = "\n".join(social_lines) if social_lines else ""

        # Determine what the town needs (for construction-capable agents)
        town_needs = ""
        if agent.profile.job in ("Builder", "Mayor", "Blacksmith") and agent.state.wealth > 100:
            from simulation.world import BUILDING_MAP
            existing_types = {b.building_type for b in BUILDING_MAP.values()}
            needs = []
            if "clinic" not in existing_types:
                needs.append("a clinic (Doctor Amara needs one badly)")
            if sum(1 for b in BUILDING_MAP.values() if b.building_type == "house") < 8:
                needs.append("more houses (some people are crowded)")
            if "market_stall" not in existing_types:
                needs.append("a market stall for traders")
            if needs:
                town_needs = "The town could use: " + ", ".join(needs) + f". You have {int(agent.state.wealth)} coins. Building costs 150-400 coins. If you want to build, set a goal like 'Build a clinic near the town hall'."

        result = await llm_client.generate_json(
            sys_prompt,
            reflection_prompt(agent.name, recent, agent.active_goals, agent.opinions, social_ctx, town_needs),
            default={"reflections": []},
        )

        # Process reflections
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

        # Process new goal
        new_goal = result.get("new_goal")
        if new_goal and isinstance(new_goal, str) and new_goal.strip() and new_goal != "null":
            # Check for duplicates
            existing_texts = [g["text"].lower() for g in agent.active_goals]
            if new_goal.lower() not in existing_texts:
                agent.active_goals.append({
                    "text": new_goal,
                    "created_tick": tick,
                    "source": "reflection",
                    "priority": 0.7,
                    "status": "active",
                    "progress_notes": [],
                })
                agent.memory.add(MemoryEntry(
                    tick=tick,
                    content=f"I've developed a new goal: {new_goal}",
                    importance=8.0,
                    memory_type="reflection",
                ))
                events.append({
                    "type": "agent_thought",
                    "agentId": agent.id,
                    "thought": f"New goal: {new_goal}",
                })
                # Enforce max goals
                active = [g for g in agent.active_goals if g["status"] == "active"]
                if len(active) > MAX_ACTIVE_GOALS:
                    # Drop lowest priority
                    active.sort(key=lambda g: g["priority"])
                    drop = active[0]
                    drop["status"] = "abandoned"

        # Process completed goal
        completed = result.get("completed_goal")
        if completed and isinstance(completed, str) and completed != "null":
            for g in agent.active_goals:
                if g["status"] == "active" and completed.lower() in g["text"].lower():
                    g["status"] = "completed"
                    agent.memory.add(MemoryEntry(
                        tick=tick,
                        content=f"I achieved my goal: {g['text']}!",
                        importance=9.0,
                        memory_type="emotion",
                    ))
                    agent.state.mood = min(1.0, agent.state.mood + 0.1)
                    break

        # Process abandoned goal
        abandoned = result.get("abandoned_goal")
        if abandoned and isinstance(abandoned, str) and abandoned != "null":
            for g in agent.active_goals:
                if g["status"] == "active" and abandoned.lower() in g["text"].lower():
                    g["status"] = "abandoned"
                    agent.memory.add(MemoryEntry(
                        tick=tick,
                        content=f"I've given up on: {g['text']}",
                        importance=6.0,
                        memory_type="emotion",
                    ))
                    break

        # Process goal progress
        progress = result.get("goal_progress")
        if progress and isinstance(progress, str) and progress != "null":
            for g in agent.active_goals:
                if g["status"] == "active":
                    g["progress_notes"].append(progress)
                    if len(g["progress_notes"]) > 10:
                        g["progress_notes"] = g["progress_notes"][-10:]
                    break

        # Process opinion shifts
        shifts = result.get("opinion_shifts", {})
        if isinstance(shifts, dict):
            for topic, stance_desc in shifts.items():
                if topic in agent.opinions and isinstance(stance_desc, str):
                    # Shift stance based on description
                    old = agent.opinions[topic]["stance"]
                    if any(w in stance_desc.lower() for w in ["more supportive", "in favor", "positive", "agree", "pro"]):
                        agent.opinions[topic]["stance"] = min(1.0, old + 0.15)
                    elif any(w in stance_desc.lower() for w in ["against", "negative", "disagree", "oppose", "anti"]):
                        agent.opinions[topic]["stance"] = max(-1.0, old - 0.15)
                    agent.opinions[topic]["confidence"] = min(1.0, agent.opinions[topic].get("confidence", 0.3) + 0.05)
                    agent.opinions[topic]["last_updated"] = tick

        # Process planned action (solo commitment from reflection)
        planned = result.get("planned_action")
        if planned and isinstance(planned, dict) and planned.get("description"):
            from simulation.world import BUILDING_MAP
            loc = planned.get("location", "")
            if loc in BUILDING_MAP:
                time_hint = str(planned.get("time", "noon")).lower()
                try:
                    plan_hour = int(time_hint)
                except (ValueError, TypeError):
                    plan_hour = {"morning": 9, "noon": 12, "afternoon": 15, "evening": 18}.get(time_hint, 12)

                # Deduplicate
                dup = any(c.get("where") == loc and c.get("when") == plan_hour for c in agent.social_commitments)
                if not dup:
                    agent.social_commitments.append({
                        "what": planned["description"],
                        "where": loc,
                        "when": plan_hour,
                        "with": [],
                        "day": day + 1 if day > 0 else tick // 288 + 2,
                        "recurring": False,
                    })
                agent.memory.add(MemoryEntry(
                    tick=tick,
                    content=f"I plan to: {planned['description']}",
                    importance=6.0,
                    memory_type="action",
                ))
                events.append({
                    "type": "agent_thought",
                    "agentId": agent.id,
                    "thought": f"Planning: {planned['description']}",
                })
                logger.info(f"{agent.name} planned solo action: {planned['description']} at {loc}")

        # Process bulletin board post
        bulletin_post = result.get("bulletin_post")
        if bulletin_post and isinstance(bulletin_post, str) and bulletin_post != "null" and len(bulletin_post) > 5:
            from systems.social import bulletin_board
            bulletin_board.add_post(agent.id, agent.name, bulletin_post, tick, day)
            events.append({
                "type": "system_event",
                "eventType": "bulletin_post",
                "label": "Bulletin Post",
                "description": f"{agent.name} posted: {bulletin_post[:60]}",
            })

        # Clean up goal list: keep max 5 active + 3 recent inactive
        active = [g for g in agent.active_goals if g["status"] == "active"]
        inactive = [g for g in agent.active_goals if g["status"] != "active"]
        agent.active_goals = active[-5:] + inactive[-3:]

        logger.info(f"{agent.name} reflected: {len(reflections)} insights, new_goal={bool(new_goal)}")
        return events

    async def maybe_plan(self, agent, day: int, tick: int) -> list[dict]:
        """Generate daily plan at the start of each day."""
        events = []
        last_plan_day = self._plan_day.get(agent.id, 0)

        if day <= last_plan_day:
            return events

        self._plan_day[agent.id] = day

        # Summarize default schedule as text
        sched_desc = ", ".join(
            f"{int(s.hour)}:00 {s.activity} at {s.location}"
            for s in agent.profile.schedule[:6]
        )
        # Include social commitments for today
        commitments_desc = ""
        today_commitments = [c for c in agent.social_commitments if c.get("day", 0) == day or c.get("recurring")]
        if today_commitments:
            parts = [f"{int(c['when'])}:00 {c['what']} at {c['where']} with {', '.join(c['with'])}" for c in today_commitments]
            commitments_desc = " YOU HAVE PLANS TODAY: " + "; ".join(parts) + ". Make sure to include these in your schedule!"

        profile = {
            "age": agent.profile.age,
            "job": agent.profile.job,
            "personality": agent.profile.personality,
            "values": agent.profile.values,
            "backstory": agent.profile.backstory,
            "goals": [g["text"] for g in agent.active_goals if g["status"] == "active"],
            "default_schedule": sched_desc + commitments_desc,
        }

        sys_prompt = conversation_system_prompt(agent.name, profile)
        result = await llm_client.generate_json(
            sys_prompt,
            daily_plan_prompt(
                agent.name, profile,
                agent.memory.reflections(5),
                agent.active_goals,
                day,
                agent.opinions,
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

        # Parse structured schedule from LLM response
        schedule_data = result.get("schedule", [])
        if schedule_data and isinstance(schedule_data, list) and len(schedule_data) >= 3:
            from agents.profiles import ScheduleEntry
            from simulation.world import BUILDING_MAP
            valid_locations = set(BUILDING_MAP.keys())
            new_schedule = []
            for entry in schedule_data:
                if not isinstance(entry, dict):
                    continue
                hour = entry.get("hour", 0)
                location = entry.get("location", "")
                activity = entry.get("activity", "idle")
                # Validate location exists
                if location in valid_locations:
                    new_schedule.append(ScheduleEntry(float(hour), location, activity))
            if len(new_schedule) >= 3:
                new_schedule.sort(key=lambda e: e.hour)
                agent.dynamic_schedule = new_schedule
                logger.info(f"{agent.name} set dynamic schedule: {len(new_schedule)} entries")
            else:
                # Not enough valid entries, keep static schedule
                agent.dynamic_schedule = None
        else:
            # No schedule from LLM, reset to static
            agent.dynamic_schedule = None

        return events


cognition_system = CognitionSystem()
