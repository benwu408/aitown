"""Economic engine — production, trade, prices, wages, taxes. All deterministic math, no LLM."""

import logging
import random
from dataclasses import dataclass, field

logger = logging.getLogger("agentica.economy")

# Base prices for goods
BASE_PRICES = {
    "food": 5,
    "bread": 8,
    "tools": 15,
    "crafts": 12,
    "medicine": 20,
    "ale": 6,
}

# What each job produces per work-tick
PRODUCTION = {
    "Farmer": {"food": 3},
    "Shopkeeper": {},  # Buys and resells
    "Blacksmith": {"tools": 1},
    "Baker": {"bread": 2},  # Consumes food, produces bread
    "Bartender": {"ale": 2},
    "Artist": {"crafts": 1},
    "Doctor": {"medicine": 1},
}

# Daily food consumption per agent
DAILY_FOOD_COST = 5

TAX_RATE = 0.05


@dataclass
class Transaction:
    tick: int
    buyer: str
    seller: str
    item: str
    quantity: int
    price: float
    total: float


class EconomySystem:
    def __init__(self):
        self.prices: dict[str, float] = dict(BASE_PRICES)
        self.supply: dict[str, float] = {k: 20.0 for k in BASE_PRICES}
        self.demand: dict[str, float] = {k: 0.0 for k in BASE_PRICES}
        self.treasury: float = 500.0
        self.transactions: list[Transaction] = []
        self.total_transactions: int = 0
        self.price_history: dict[str, list[float]] = {k: [v] for k, v in BASE_PRICES.items()}
        self._daily_demand_counter: dict[str, float] = {k: 0.0 for k in BASE_PRICES}

    def tick(self, agents: dict, hour: float, tick: int) -> list[dict]:
        """Process one economic tick. Returns events."""
        events = []

        for agent in agents.values():
            # Production during work hours
            if agent.current_action.value == "working":
                produced = PRODUCTION.get(agent.profile.job, {})
                for item, qty in produced.items():
                    # Baker needs food to make bread
                    if agent.profile.job == "Baker" and item == "bread":
                        if self.supply.get("food", 0) >= 1:
                            self.supply["food"] -= 1
                        else:
                            continue  # Can't bake without food

                    self.supply[item] = self.supply.get(item, 0) + qty * 0.1  # Scale down per-tick

            # Buying during buy/eat actions
            if agent.current_action.value in ("buying", "eating"):
                # Try to buy food
                food_price = self.prices.get("food", 5)
                if agent.state.wealth >= food_price and self.supply.get("food", 0) > 0:
                    agent.state.wealth -= int(food_price)
                    self.supply["food"] -= 1
                    self._daily_demand_counter["food"] += 1
                    tax = food_price * TAX_RATE
                    self.treasury += tax

                    txn = {"tick": tick, "item": "food", "price": int(food_price), "action": "buy"}
                    agent.transactions.append(txn)
                    self.total_transactions += 1
                    events.append({
                        "type": "transaction",
                        "agentId": agent.id,
                        **txn,
                    })
                elif agent.state.wealth < food_price:
                    # Can't afford food — mood drops
                    agent.state.mood = max(0, agent.state.mood - 0.02)

            # Selling during sell actions
            if agent.current_action.value == "selling":
                produced = PRODUCTION.get(agent.profile.job, {})
                for item in produced:
                    if self.supply.get(item, 0) > 5:  # Only sell excess
                        price = self.prices.get(item, 10)
                        agent.state.wealth += int(price)
                        self.supply[item] -= 1
                        txn = {"tick": tick, "item": item, "price": int(price), "action": "sell"}
                        agent.transactions.append(txn)
                        self.total_transactions += 1
                        events.append({
                            "type": "transaction",
                            "agentId": agent.id,
                            **txn,
                        })

        # Adjust prices based on supply/demand (every 10 ticks)
        if tick % 10 == 0:
            self._adjust_prices()

        return events

    def _adjust_prices(self):
        """Simple supply/demand price adjustment."""
        for item in self.prices:
            supply = max(self.supply.get(item, 1), 0.1)
            demand = max(self._daily_demand_counter.get(item, 1), 0.1)
            ratio = demand / supply

            # Move price toward equilibrium
            target = BASE_PRICES.get(item, 10) * ratio
            self.prices[item] = self.prices[item] * 0.9 + target * 0.1
            self.prices[item] = max(1, min(self.prices[item], BASE_PRICES.get(item, 10) * 5))

        # Record price history
        for item in self.prices:
            if item not in self.price_history:
                self.price_history[item] = []
            self.price_history[item].append(round(self.prices[item], 1))
            if len(self.price_history[item]) > 100:
                self.price_history[item] = self.price_history[item][-100:]

        # Decay demand counter
        for item in self._daily_demand_counter:
            self._daily_demand_counter[item] *= 0.8

    def to_dict(self) -> dict:
        return {
            "prices": {k: round(v, 1) for k, v in self.prices.items()},
            "basePrices": dict(BASE_PRICES),
            "supply": {k: round(v, 1) for k, v in self.supply.items()},
            "demand": {k: round(v, 1) for k, v in self._daily_demand_counter.items()},
            "treasury": round(self.treasury, 1),
            "totalTransactions": self.total_transactions,
            "priceHistory": {k: v[-50:] for k, v in self.price_history.items()},
        }
