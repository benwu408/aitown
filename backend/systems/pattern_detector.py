"""PatternDetector -- scans recent actions for emergent patterns every 50 ticks."""

import logging
from collections import Counter, defaultdict

logger = logging.getLogger("agentica.patterns")


class PatternDetector:
    def __init__(self):
        self._last_check_tick = 0
        self._action_log: list[dict] = []
        self._gathering_counts: defaultdict = defaultdict(lambda: defaultdict(int))
        self._activity_time: defaultdict = defaultdict(lambda: defaultdict(float))
        self._influence_counts: defaultdict = defaultdict(lambda: defaultdict(int))

    def record_action(self, agent_name: str, action: dict, tick: int):
        entry = {"agent": agent_name, "tick": tick, **action}
        self._action_log.append(entry)
        self._action_log = self._action_log[-500:]

        action_type = action.get("type", "")
        location = action.get("location", "")

        if action_type in ("gathering", "building", "working", "trading", "art"):
            self._activity_time[agent_name][action_type] += 1.0

        if location:
            self._gathering_counts[location][action_type or "activity"] += 1

        if action_type in ("proposal", "support_signal", "alliance_signal"):
            target = action.get("target", "")
            if target:
                self._influence_counts[target][agent_name] += 1

    def check(self, agents: dict, world, tick: int, day: int) -> list[dict]:
        if tick - self._last_check_tick < 50:
            return []
        self._last_check_tick = tick
        events = []

        events.extend(self._detect_social_patterns(agents, world, tick, day))
        events.extend(self._detect_gathering_place_patterns(world, tick, day))
        events.extend(self._detect_norm_emergence(world, tick, day))
        events.extend(self._detect_conflict_patterns(agents, world, tick, day))

        return events

    def _detect_social_patterns(self, agents: dict, world, tick: int, day: int) -> list[dict]:
        events = []

        for agent_name, activities in self._activity_time.items():
            total = sum(activities.values())
            if total < 10:
                continue
            for activity, time_spent in activities.items():
                if time_spent / total > 0.6:
                    name = f"{agent_name} specializes in {activity}"
                    if not self._norm_exists(world, name):
                        pct = int(time_spent / total * 100)
                        self._register_pattern(world, name, "social",
                            f"{agent_name} spends {pct}% of active time on {activity}",
                            day, tick)
                        events.append({"type": "system_event", "eventType": "pattern_detected",
                            "label": "Role Specialization",
                            "description": f"{agent_name} is becoming a {activity} specialist"})

        influence_totals: Counter = Counter()
        for target, influencers in self._influence_counts.items():
            for influencer, count in influencers.items():
                influence_totals[influencer] += count

        if influence_totals:
            leader, lead_count = influence_totals.most_common(1)[0]
            if lead_count >= 5:
                name = f"Agents repeatedly defer to {leader}"
                if not self._norm_exists(world, name):
                    self._register_pattern(
                        world,
                        name,
                        "social",
                        f"{leader} consistently influences others ({lead_count} influence events)",
                        day,
                        tick,
                    )
                    events.append({
                        "type": "system_event",
                        "eventType": "pattern_detected",
                        "label": "Social Pattern",
                        "description": f"Others increasingly orient around {leader}.",
                    })

        return events

    def _detect_gathering_place_patterns(self, world, tick: int, day: int) -> list[dict]:
        events = []
        if not self._gathering_counts:
            return events

        for location, counts in self._gathering_counts.items():
            total = sum(counts.values())
            if total < 8 or not location:
                continue
            name = f"Regular gathering at {location}"
            if self._norm_exists(world, name):
                continue
            top_activity = max(counts, key=counts.get)
            self._register_pattern(
                world,
                name,
                "social",
                f"Agents repeatedly converge on {location} around {top_activity} ({total} recent actions).",
                day,
                tick,
            )
            events.append({
                "type": "system_event",
                "eventType": "pattern_detected",
                "label": "Gathering Place",
                "description": f"{location} is becoming a regular gathering place.",
            })
        return events

    def _detect_norm_emergence(self, world, tick: int, day: int) -> list[dict]:
        events = []
        action_counts: defaultdict = defaultdict(lambda: {"agents": set(), "count": 0})

        for entry in self._action_log:
            action_type = entry.get("type", "")
            if not action_type:
                continue
            record = action_counts[action_type]
            record["agents"].add(entry.get("agent", ""))
            record["count"] += 1

        for action_type, record in action_counts.items():
            unique_agents = len(record["agents"])
            total_count = record["count"]
            if unique_agents >= 7 and total_count >= 10:
                name = f"Common practice: {action_type}"
                if not self._norm_exists(world, name):
                    self._register_pattern(world, name, "norm",
                        f"{action_type} is performed by {unique_agents} agents ({total_count} times)",
                        day, tick)
                    events.append({"type": "system_event", "eventType": "pattern_detected",
                        "label": "Norm Emergence",
                        "description": f"{action_type} is becoming a community norm"})

        return events

    def _detect_conflict_patterns(self, agents: dict, world, tick: int, day: int) -> list[dict]:
        events = []
        conflict_pairs: Counter = Counter()
        conflict_issues: Counter = Counter()

        for agent in agents.values():
            for conflict in getattr(agent, "active_conflicts", []):
                if conflict.get("status") != "active":
                    continue
                pair = tuple(sorted([agent.name, conflict.get("with", "")]))
                conflict_pairs[pair] += 1
                summary = conflict.get("summary", "")
                if summary:
                    for keyword in ("claim", "steal", "food", "space", "respect"):
                        if keyword in summary.lower():
                            conflict_issues[keyword] += 1

        for pair, count in conflict_pairs.items():
            if count >= 3:
                name = f"Recurring conflict: {pair[0]} vs {pair[1]}"
                if not self._norm_exists(world, name):
                    self._register_pattern(world, name, "conflict",
                        f"{pair[0]} and {pair[1]} have {count} unresolved disputes",
                        day, tick)
                    events.append({"type": "system_event", "eventType": "pattern_detected",
                        "label": "Conflict Pattern",
                        "description": f"Recurring conflict between {pair[0]} and {pair[1]}"})

        for issue, count in conflict_issues.items():
            if count >= 4:
                name = f"Systemic issue: {issue}"
                if not self._norm_exists(world, name):
                    self._register_pattern(world, name, "conflict",
                        f"'{issue}' is a recurring source of conflict ({count} instances)",
                        day, tick)
                    events.append({"type": "system_event", "eventType": "pattern_detected",
                        "label": "Systemic Issue",
                        "description": f"'{issue}' is causing repeated disputes"})

        return events

    def _norm_exists(self, world, name: str) -> bool:
        for norm in world.constitution.social_norms:
            text = norm["text"] if isinstance(norm, dict) else str(norm)
            if text == name:
                return True
        for inst in world.constitution.institutions:
            if inst.get("name") == name:
                return True
        for pattern in getattr(world.constitution, "detected_patterns", []):
            if pattern.get("name") == name:
                return True
        return False

    def _register_pattern(self, world, name: str, pattern_type: str, description: str, day: int, tick: int):
        pattern = {
            "id": f"pattern_{len(getattr(world.constitution, 'detected_patterns', [])) + 1}",
            "name": name,
            "text": name,
            "category": pattern_type,
            "origin": "pattern_detection",
            "strength": 0.4,
            "scope": "settlement",
            "recognized_by": [],
            "violations": 0,
            "created_tick": tick,
            "emerged_on": day,
            "status": "informal",
            "adherence_rate": 0.0,
            "description": description,
            "history": [{"tick": tick, "type": "detected", "description": description}],
        }
        world.constitution.detected_patterns.append(pattern)
        world.constitution.social_norms.append(pattern)
        world.constitution.change_history.append({
            "tick": tick, "type": "pattern_detected",
            "description": f"[{pattern_type}] {name}: {description}",
        })
        logger.info("Pattern detected: [%s] %s", pattern_type, name)


pattern_detector = PatternDetector()
