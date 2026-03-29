import random


class TimeManager:
    WEATHER_TYPES = ["clear", "cloudy", "rain", "storm"]
    WEATHER_WEIGHTS = [0.5, 0.25, 0.15, 0.1]

    def __init__(self, ticks_per_day: int = 144):
        self.ticks_per_day = ticks_per_day
        self.tick_in_day = 0
        self.day = 1
        self.season = "spring"
        self.weather = "clear"
        self._weather_duration = 0
        self._seasons = ["spring", "summer", "autumn", "winter"]
        self._season_day = 0

    def advance(self):
        self.tick_in_day += 1
        if self.tick_in_day >= self.ticks_per_day:
            self.tick_in_day = 0
            self.day += 1
            self._season_day += 1
            if self._season_day >= 30:
                self._season_day = 0
                idx = self._seasons.index(self.season)
                self.season = self._seasons[(idx + 1) % 4]

        # Weather changes
        self._weather_duration -= 1
        if self._weather_duration <= 0:
            self.weather = random.choices(
                self.WEATHER_TYPES, weights=self.WEATHER_WEIGHTS
            )[0]
            self._weather_duration = random.randint(20, 60)

    @property
    def hour(self) -> float:
        """Current hour (0-24) as float."""
        return (self.tick_in_day / self.ticks_per_day) * 24.0

    @property
    def hour_int(self) -> int:
        return int(self.hour)

    @property
    def minute(self) -> int:
        return int((self.hour % 1) * 60)

    @property
    def time_of_day(self) -> str:
        h = self.hour
        if h < 5:
            return "night"
        elif h < 7:
            return "dawn"
        elif h < 12:
            return "morning"
        elif h < 14:
            return "midday"
        elif h < 17:
            return "afternoon"
        elif h < 20:
            return "evening"
        else:
            return "night"

    @property
    def is_night(self) -> bool:
        return self.hour < 6 or self.hour >= 22

    @property
    def time_string(self) -> str:
        h = self.hour_int
        m = self.minute
        ampm = "AM" if h < 12 else "PM"
        display_h = h % 12 or 12
        return f"{display_h}:{m:02d} {ampm}"

    def get_weather_modifier(self, action_type: str) -> float:
        from simulation.world import WEATHER_ACTION_MODIFIERS
        mods = WEATHER_ACTION_MODIFIERS.get(self.weather, {})
        return mods.get(action_type, 1.0)

    def get_season_resource_modifier(self, resource: str) -> float:
        from simulation.world import SEASON_RESOURCE_MODIFIERS
        mods = SEASON_RESOURCE_MODIFIERS.get(self.season, {})
        return mods.get(resource, 1.0)

    def get_energy_drain_modifier(self) -> float:
        from simulation.world import WEATHER_ENERGY_DRAIN, SEASON_ENERGY_DRAIN
        weather_mod = WEATHER_ENERGY_DRAIN.get(self.weather, 1.0)
        season_mod = SEASON_ENERGY_DRAIN.get(self.season, 1.0)
        return weather_mod * season_mod

    def to_dict(self) -> dict:
        return {
            "tick_in_day": self.tick_in_day,
            "day": self.day,
            "hour": round(self.hour, 2),
            "minute": self.minute,
            "time_string": self.time_string,
            "time_of_day": self.time_of_day,
            "season": self.season,
            "weather": self.weather,
            "is_night": self.is_night,
        }
