"""Working memory — the 5-7 item spotlight of conscious attention."""


MAX_ITEMS = 7


class WorkingMemory:
    def __init__(self):
        self.items: list[str] = []
        self.current_focus: str = ""
        self.background_worry: str = ""
        self.background_desire: str = ""
        self.unfinished_business: str = ""
        self.latest_observation: str = ""
        self.latest_sensation: str = ""
        self.current_goal: str = ""
        self.interrupted_task: str = ""

    def push(self, item: str):
        """Add something to working memory. Oldest item drops off if full."""
        if item in self.items:
            self.items.remove(item)
        self.items.insert(0, item)
        if len(self.items) > MAX_ITEMS:
            self.items.pop()
        self.current_focus = item

    def set_focus(self, focus: str):
        self.current_focus = focus
        if focus and focus not in self.items:
            self.push(focus)

    def set_worry(self, worry: str):
        self.background_worry = worry

    def set_desire(self, desire: str):
        self.background_desire = desire

    def set_goal(self, goal: str):
        self.current_goal = goal

    def interrupt(self, new_focus: str):
        if self.current_goal:
            self.interrupted_task = self.current_goal
        self.push(new_focus)

    def clear_interrupt(self):
        if self.interrupted_task:
            self.current_goal = self.interrupted_task
            self.interrupted_task = ""

    def update_from_drives(self, drives):
        """Drives that cross thresholds force their way into attention."""
        if drives.hunger > 0.7 and "hungry" not in str(self.items):
            self.push("I'm getting really hungry")
            self.latest_sensation = "My stomach is growling"
        if drives.rest > 0.8 and "tired" not in str(self.items):
            self.push("I'm exhausted")
            self.latest_sensation = "My body feels heavy. I need to rest."
        if drives.social_need > 0.7 and "lonely" not in str(self.items):
            self.background_worry = "I haven't really talked to anyone today"
        if drives.purpose_need > 0.7:
            self.background_worry = "What am I even doing here? I need to figure out my place."
        if drives.shelter_need > 0.6 and "shelter" not in str(self.items):
            self.push("I need to build some kind of shelter")
            self.latest_sensation = "The wind is biting. I need protection from the elements."

    def get_prompt_context(self) -> str:
        parts = []
        if self.items:
            parts.append("What's on your mind right now:\n" + "\n".join(f"- {i}" for i in self.items[:5]))
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
            "items": self.items[:],
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
        self.items = d.get("items", [])[:MAX_ITEMS]
        self.current_focus = d.get("focus", "")
        self.background_worry = d.get("worry", "")
        self.background_desire = d.get("desire", "")
        self.unfinished_business = d.get("unfinished", "")
        self.latest_observation = d.get("observation", "")
        self.latest_sensation = d.get("sensation", "")
        self.current_goal = d.get("goal", "")
        self.interrupted_task = d.get("interrupted", "")
