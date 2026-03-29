"""Working memory -- scored attention buffer with priority-based eviction."""

from dataclasses import dataclass, field


MAX_ITEMS = 7


@dataclass
class MemoryItem:
    content: str
    priority: float = 0.5
    persistent: bool = False
    source: str = ""
    tick_added: int = 0


class WorkingMemory:
    def __init__(self):
        self.items: list[MemoryItem] = []
        self.current_focus: str = ""
        self.background_worry: str = ""
        self.background_desire: str = ""
        self.unfinished_business: str = ""
        self.latest_observation: str = ""
        self.latest_sensation: str = ""
        self.current_goal: str = ""
        self.interrupted_task: str = ""

    def push(self, content: str, priority: float = 0.5, persistent: bool = False,
             source: str = "", tick: int = 0):
        # Remove duplicate content
        self.items = [i for i in self.items if i.content != content]
        item = MemoryItem(content=content, priority=max(0.0, min(1.0, priority)),
                          persistent=persistent, source=source, tick_added=tick)
        self.items.append(item)
        # Evict lowest priority non-persistent item if over capacity
        while len(self.items) > MAX_ITEMS:
            evict_candidates = [i for i in self.items if not i.persistent]
            if not evict_candidates:
                evict_candidates = self.items[:]
            worst = min(evict_candidates, key=lambda i: i.priority)
            self.items.remove(worst)
        self.current_focus = content

    def get_top_items(self, n: int = 5) -> list[MemoryItem]:
        return sorted(self.items, key=lambda i: i.priority, reverse=True)[:n]

    def decay_priorities(self, amount: float = 0.02):
        for item in self.items:
            if not item.persistent:
                item.priority = max(0.0, item.priority - amount)
        # Remove items that decayed to zero and are not persistent
        self.items = [i for i in self.items if i.priority > 0.0 or i.persistent]

    def force_from_drive(self, content: str, source: str = "drive", tick: int = 0):
        self.push(content, priority=0.85, persistent=False, source=source, tick=tick)

    def set_focus(self, focus: str):
        self.current_focus = focus
        if focus:
            existing = [i for i in self.items if i.content == focus]
            if existing:
                existing[0].priority = min(1.0, existing[0].priority + 0.1)
            else:
                self.push(focus, priority=0.6)

    def set_worry(self, worry: str):
        self.background_worry = worry

    def set_desire(self, desire: str):
        self.background_desire = desire

    def set_goal(self, goal: str):
        self.current_goal = goal

    def interrupt(self, new_focus: str):
        if self.current_goal:
            self.interrupted_task = self.current_goal
        self.push(new_focus, priority=0.8)

    def clear_interrupt(self):
        if self.interrupted_task:
            self.current_goal = self.interrupted_task
            self.interrupted_task = ""

    def update_from_drives(self, drives):
        if drives.hunger > 0.7 and not any("hungry" in i.content for i in self.items):
            self.force_from_drive("I'm getting really hungry", source="hunger")
            self.latest_sensation = "My stomach is growling"
        if drives.rest > 0.8 and not any("tired" in i.content or "exhausted" in i.content for i in self.items):
            self.force_from_drive("I'm exhausted", source="rest")
            self.latest_sensation = "My body feels heavy. I need to rest."
        if getattr(drives, "thirst", 0) > 0.65 and not any("thirst" in i.content for i in self.items):
            self.force_from_drive("I need water", source="thirst")
            self.latest_sensation = "My throat is dry and scratchy."
        if getattr(drives, "energy", 1.0) < 0.2 and not any("drained" in i.content for i in self.items):
            self.force_from_drive("I feel completely drained", source="energy")
            self.latest_sensation = "Every movement costs effort."
        if getattr(drives, "health", 1.0) < 0.3 and not any("unwell" in i.content for i in self.items):
            self.force_from_drive("I feel unwell", source="health")
            self.latest_sensation = "Something is wrong with my body."
        if drives.social_need > 0.7 and not any("lonely" in i.content or "talked" in i.content for i in self.items):
            self.background_worry = "I haven't really talked to anyone today"
        if getattr(drives, "belonging", 0) > 0.7 and not any("belong" in i.content or "outsider" in i.content for i in self.items):
            self.background_worry = "I don't feel like I belong here"
        if drives.purpose_need > 0.7:
            self.background_worry = "What am I even doing here? I need to figure out my place."
        if drives.shelter_need > 0.6 and not any("shelter" in i.content for i in self.items):
            self.force_from_drive("I need to build some kind of shelter", source="shelter")
            self.latest_sensation = "The wind is biting. I need protection from the elements."

    def get_prompt_context(self) -> str:
        parts = []
        if self.items:
            top = self.get_top_items(5)
            parts.append("What's on your mind right now:\n" + "\n".join(f"- {i.content}" for i in top))
        if self.current_focus:
            parts.append(f"You're focused on: {self.current_focus}")
        if self.background_worry:
            parts.append(f"A nagging worry: {self.background_worry}")
        if self.background_desire:
            parts.append(f"Something you've been wanting: {self.background_desire}")
        if self.unfinished_business:
            parts.append(f"Something unresolved: {self.unfinished_business}")
        if self.latest_sensation:
            parts.append(f"Physical sensation: {self.latest_sensation}")
        if self.current_goal:
            parts.append(f"You're trying to: {self.current_goal}")
        if self.interrupted_task:
            parts.append(f"(You were doing: {self.interrupted_task} before getting distracted)")
        return "\n".join(parts) if parts else "Your mind is relatively clear."

    def to_dict(self) -> dict:
        return {
            "items": [{"content": i.content, "priority": round(i.priority, 2),
                        "persistent": i.persistent, "source": i.source}
                       for i in self.items],
            "focus": self.current_focus,
            "worry": self.background_worry,
            "desire": self.background_desire,
            "unfinished": self.unfinished_business,
            "observation": self.latest_observation,
            "sensation": self.latest_sensation,
            "goal": self.current_goal,
            "interrupted": self.interrupted_task,
        }

    def load_from_dict(self, d: dict):
        raw_items = d.get("items", [])
        self.items = []
        for entry in raw_items:
            if isinstance(entry, str):
                self.items.append(MemoryItem(content=entry))
            elif isinstance(entry, dict):
                self.items.append(MemoryItem(
                    content=entry.get("content", ""),
                    priority=entry.get("priority", 0.5),
                    persistent=entry.get("persistent", False),
                    source=entry.get("source", ""),
                ))
        self.items = self.items[:MAX_ITEMS]
        self.current_focus = d.get("focus", "")
        self.background_worry = d.get("worry", "")
        self.background_desire = d.get("desire", "")
        self.unfinished_business = d.get("unfinished", "")
        self.latest_observation = d.get("observation", "")
        self.latest_sensation = d.get("sensation", "")
        self.current_goal = d.get("goal", "")
        self.interrupted_task = d.get("interrupted", "")
