"""Economic engine — wages, production, trade, prices, taxes, debt. All deterministic math, no LLM."""

import logging
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
    "Shopkeeper": {},
    "Blacksmith": {"tools": 1},
    "Baker": {"bread": 2},
    "Bartender": {"ale": 2},
    "Artist": {"crafts": 1},
    "Doctor": {"medicine": 1},
}

# Daily wages by job
DAILY_WAGES = {
    "Mayor": 20,
    "Farmer": 12,
    "Shopkeeper": 15,
    "Blacksmith": 15,
    "Baker": 12,
    "Teacher": 15,
    "Bartender": 12,
    "Doctor": 20,
    "Builder": 14,
    "Teaching Assistant": 12,
    "Handyman": 12,
    "Artist": 10,
    "Journalist": 12,
    "Reverend": 12,
    "Odd Jobs": 10,
    "Retired": 8,
}

# Jobs paid from treasury (public sector)
PUBLIC_JOBS = {"Mayor", "Teacher", "Teaching Assistant", "Doctor", "Journalist", "Reverend", "Retired"}

# Daily cost of living
FOOD_COST_PER_DAY = 5
RENT_PER_DAY = 2
SUPPLIES_PER_DAY = 1

TAX_RATE = 0.05

# Seasonal production multipliers
SEASON_PRODUCTION = {
    "spring": {"food": 0.8, "bread": 1.0, "tools": 1.0, "crafts": 1.0, "medicine": 1.0, "ale": 1.0},
    "summer": {"food": 1.2, "bread": 1.0, "tools": 1.0, "crafts": 1.0, "medicine": 1.2, "ale": 1.2},
    "autumn": {"food": 2.0, "bread": 1.2, "tools": 0.8, "crafts": 1.0, "medicine": 1.0, "ale": 1.0},
    "winter": {"food": 0.3, "bread": 0.8, "tools": 1.2, "crafts": 1.2, "medicine": 0.8, "ale": 0.8},
}
SEASON_DEMAND_MULT = {"spring": 1.0, "summer": 0.9, "autumn": 0.8, "winter": 1.5}

DEBT_INTEREST_RATE = 0.01  # 1% per day


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
        self.treasury_income_today: float = 0
        self.treasury_expenses_today: float = 0
        self.transactions: list[Transaction] = []
        self.total_transactions: int = 0
        self.price_history: dict[str, list[float]] = {k: [v] for k, v in BASE_PRICES.items()}
        self._daily_demand_counter: dict[str, float] = {k: 0.0 for k in BASE_PRICES}
        self._last_expense_day: int = 0

    def tick(self, agents: dict, hour: float, tick: int, season: str = "spring", ticks_per_day: int = 288) -> list[dict]:
        """Process one economic tick. Returns events."""
        events = []
        season_prod = SEASON_PRODUCTION.get(season, {})
        season_demand = SEASON_DEMAND_MULT.get(season, 1.0)

        for agent in agents.values():
            # --- WAGES: paid each tick agent is working ---
            if agent.current_action.value == "working":
                daily_wage = DAILY_WAGES.get(agent.profile.job, 5)
                tick_wage = daily_wage / ticks_per_day
                if tick_wage > 0:
                    if agent.profile.job in PUBLIC_JOBS:
                        # Public sector: paid from treasury
                        if self.treasury >= tick_wage:
                            agent.state.wealth += tick_wage
                            agent.daily_income += tick_wage
                            self.treasury -= tick_wage
                            self.treasury_expenses_today += tick_wage
                        else:
                            # Treasury can't afford wages — partial pay
                            partial = max(0, self.treasury * 0.1)
                            agent.state.wealth += partial
                            agent.daily_income += partial
                            self.treasury -= partial
                    else:
                        # Private sector: self-employed or business
                        agent.state.wealth += tick_wage
                        agent.daily_income += tick_wage

            # --- PRODUCTION ---
            if agent.current_action.value == "working":
                produced = PRODUCTION.get(agent.profile.job, {})
                for item, qty in produced.items():
                    if agent.profile.job == "Baker" and item == "bread":
                        if self.supply.get("food", 0) >= 1:
                            self.supply["food"] -= 1
                        else:
                            continue
                    seasonal_mult = season_prod.get(item, 1.0)
                    self.supply[item] = self.supply.get(item, 0) + qty * 0.1 * seasonal_mult

            # --- BUYING FOOD ---
            if agent.current_action.value in ("buying", "eating"):
                food_price = self.prices.get("food", 5) * season_demand
                if agent.state.wealth >= food_price and self.supply.get("food", 0) > 0:
                    agent.state.wealth -= int(food_price)
                    agent.daily_expenses += food_price
                    self.supply["food"] -= 1
                    self._daily_demand_counter["food"] += 1

                    # Tax goes to treasury
                    tax = food_price * TAX_RATE
                    self.treasury += tax
                    self.treasury_income_today += tax

                    txn = {"tick": tick, "item": "food", "price": int(food_price), "action": "buy"}
                    agent.transactions.append(txn)
                    self.total_transactions += 1
                    events.append({"type": "transaction", "agentId": agent.id, **txn})

                elif agent.state.wealth < food_price:
                    # Can't afford food
                    agent.state.mood = max(0, agent.state.mood - 0.02)
                    # Borrow from treasury if desperate
                    if agent.state.wealth < 5 and agent.debt < 50:
                        loan = min(10, self.treasury * 0.02)
                        if loan > 0:
                            agent.state.wealth += loan
                            agent.debt += loan
                            self.treasury -= loan

            # --- SELLING ---
            if agent.current_action.value == "selling":
                produced = PRODUCTION.get(agent.profile.job, {})
                for item in produced:
                    if self.supply.get(item, 0) > 5:
                        price = self.prices.get(item, 10)
                        agent.state.wealth += int(price)
                        agent.daily_income += price
                        self.supply[item] -= 1

                        tax = price * TAX_RATE
                        self.treasury += tax
                        self.treasury_income_today += tax

                        txn = {"tick": tick, "item": item, "price": int(price), "action": "sell"}
                        agent.transactions.append(txn)
                        self.total_transactions += 1
                        events.append({"type": "transaction", "agentId": agent.id, **txn})

        # --- DAILY EXPENSES (once per day at start) ---
        current_day = tick // max(ticks_per_day, 1)
        if current_day > self._last_expense_day:
            self._last_expense_day = current_day
            for agent in agents.values():
                # Food cost (separate from buying — this is base cost of living)
                # Rent (skip if agent owns home)
                rent = RENT_PER_DAY
                # Check if agent owns their home (owner field matches)
                supplies = SUPPLIES_PER_DAY
                total_daily = rent + supplies
                agent.state.wealth -= total_daily
                agent.daily_expenses += total_daily

                # Debt interest
                if agent.debt > 0:
                    interest = agent.debt * DEBT_INTEREST_RATE
                    agent.debt += interest

                # Welfare: if broke, give one-time payment every 5 days
                if agent.state.wealth < 5 and current_day % 5 == 0 and self.treasury > 50:
                    welfare = 30
                    agent.state.wealth += welfare
                    self.treasury -= welfare

                # Reset daily tracking
                agent.daily_income = 0
                agent.daily_expenses = 0

            # Reset treasury daily tracking
            self.treasury_income_today = 0
            self.treasury_expenses_today = 0

        # Adjust prices (every 10 ticks)
        if tick % 10 == 0:
            self._adjust_prices()

        return events

    def _adjust_prices(self):
        for item in self.prices:
            supply = max(self.supply.get(item, 1), 0.1)
            demand = max(self._daily_demand_counter.get(item, 1), 0.1)
            ratio = demand / supply
            target = BASE_PRICES.get(item, 10) * ratio
            self.prices[item] = self.prices[item] * 0.9 + target * 0.1
            self.prices[item] = max(1, min(self.prices[item], BASE_PRICES.get(item, 10) * 5))

        for item in self.prices:
            if item not in self.price_history:
                self.price_history[item] = []
            self.price_history[item].append(round(self.prices[item], 1))
            if len(self.price_history[item]) > 100:
                self.price_history[item] = self.price_history[item][-100:]

        for item in self._daily_demand_counter:
            self._daily_demand_counter[item] *= 0.8

    def to_dict(self) -> dict:
        return {
            "prices": {k: round(v, 1) for k, v in self.prices.items()},
            "basePrices": dict(BASE_PRICES),
            "supply": {k: round(v, 1) for k, v in self.supply.items()},
            "demand": {k: round(v, 1) for k, v in self._daily_demand_counter.items()},
            "treasury": round(self.treasury, 1),
            "treasuryIncomeToday": round(self.treasury_income_today, 1),
            "treasuryExpensesToday": round(self.treasury_expenses_today, 1),
            "totalTransactions": self.total_transactions,
            "priceHistory": {k: v[-50:] for k, v in self.price_history.items()},
            "wages": DAILY_WAGES,
            "taxRate": TAX_RATE,
        }
