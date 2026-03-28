"""Inventory-based peer-to-peer economy — barter, emergent currency, price discovery. No LLM."""

import logging
from dataclasses import dataclass, field

logger = logging.getLogger("agentica.economy")

# Rough "effort" values for barter fairness — how hard is 1 unit to get?
EFFORT_VALUES = {
    "wood": 3.0,
    "stone": 4.0,
    "wild_berries": 1.5,
    "wild_plants": 1.0,
    "fish": 2.5,
    "wild_herbs": 3.0,
    "clay": 2.0,
    "minerals": 5.0,
    "wild_grass": 0.5,
    "fresh_water": 0.2,
}

# Items that satisfy specific drives
FOOD_ITEMS = {"wild_berries", "fish", "wild_plants", "wild_herbs"}
BUILDING_ITEMS = {"wood", "stone", "clay"}

# Seasonal multipliers on effort values (scarcity = higher value)
SEASON_EFFORT_MULT = {
    "spring": {"wild_berries": 1.2, "fish": 1.0, "wood": 1.0},
    "summer": {"wild_berries": 0.8, "fish": 0.9, "wood": 1.0},
    "autumn": {"wild_berries": 0.6, "fish": 1.0, "wood": 1.1},
    "winter": {"wild_berries": 2.0, "fish": 1.5, "wood": 1.3},
}


@dataclass
class TradeRecord:
    tick: int
    giver: str
    receiver: str
    given_item: str
    given_qty: int
    received_item: str
    received_qty: int
    fairness: float  # ratio of effort values, 1.0 = perfectly fair
    context: str  # "barter", "gift", "currency", "debt_repayment"


class EconomySystem:
    """Tracks the emergent economy: trade history, price discovery, currency adoption."""

    def __init__(self):
        self.trade_history: list[TradeRecord] = []
        self.total_trades: int = 0
        # Emergent price memory: item -> list of recent exchange ratios vs other items
        self.exchange_rates: dict[str, dict[str, float]] = {}
        # Currency tracking: which item (if any) is being used as medium of exchange
        self.currency_item: str | None = None
        self.currency_adoption: float = 0.0  # 0-1, how many trades use it
        # Per-agent trade stats
        self.agent_trade_counts: dict[str, int] = {}
        self.agent_trade_volume: dict[str, float] = {}  # total effort-value traded

    def get_effort_value(self, item: str, season: str = "spring") -> float:
        base = EFFORT_VALUES.get(item, 2.0)
        mult = SEASON_EFFORT_MULT.get(season, {}).get(item, 1.0)
        return base * mult

    def calculate_fairness(self, given_item: str, given_qty: int, received_item: str, received_qty: int, season: str = "spring") -> float:
        give_val = self.get_effort_value(given_item, season) * given_qty
        recv_val = self.get_effort_value(received_item, season) * received_qty
        if give_val == 0 or recv_val == 0:
            return 0.5
        return min(give_val, recv_val) / max(give_val, recv_val)

    def record_trade(self, tick: int, giver: str, receiver: str, given_item: str, given_qty: int, received_item: str, received_qty: int, context: str = "barter", season: str = "spring"):
        fairness = self.calculate_fairness(given_item, given_qty, received_item, received_qty, season)
        record = TradeRecord(
            tick=tick, giver=giver, receiver=receiver,
            given_item=given_item, given_qty=given_qty,
            received_item=received_item, received_qty=received_qty,
            fairness=fairness, context=context,
        )
        self.trade_history.append(record)
        self.trade_history = self.trade_history[-200:]
        self.total_trades += 1

        # Track per-agent stats
        for name in (giver, receiver):
            self.agent_trade_counts[name] = self.agent_trade_counts.get(name, 0) + 1
            effort = self.get_effort_value(given_item, season) * given_qty
            self.agent_trade_volume[name] = self.agent_trade_volume.get(name, 0) + effort

        # Update exchange rates
        self._update_exchange_rate(given_item, received_item, given_qty, received_qty)

    def _update_exchange_rate(self, item_a: str, item_b: str, qty_a: int, qty_b: int):
        if qty_a <= 0 or qty_b <= 0:
            return
        rate_a_to_b = qty_b / qty_a  # how many B per 1 A
        rate_b_to_a = qty_a / qty_b

        self.exchange_rates.setdefault(item_a, {})
        self.exchange_rates.setdefault(item_b, {})

        # Exponential moving average
        old = self.exchange_rates[item_a].get(item_b, rate_a_to_b)
        self.exchange_rates[item_a][item_b] = round(old * 0.7 + rate_a_to_b * 0.3, 2)
        old = self.exchange_rates[item_b].get(item_a, rate_b_to_a)
        self.exchange_rates[item_b][item_a] = round(old * 0.7 + rate_b_to_a * 0.3, 2)

    def detect_currency(self):
        """Check if any single item is appearing on one side of most trades (medium of exchange)."""
        if len(self.trade_history) < 10:
            self.currency_item = None
            self.currency_adoption = 0.0
            return

        recent = self.trade_history[-50:]
        item_counts: dict[str, int] = {}
        for trade in recent:
            item_counts[trade.given_item] = item_counts.get(trade.given_item, 0) + 1
            item_counts[trade.received_item] = item_counts.get(trade.received_item, 0) + 1

        if not item_counts:
            return

        # The "currency" is the item that appears in the most trades
        top_item = max(item_counts, key=lambda k: item_counts[k])
        frequency = item_counts[top_item] / len(recent)

        if frequency > 0.4:
            self.currency_item = top_item
            self.currency_adoption = round(frequency, 2)
        else:
            self.currency_item = None
            self.currency_adoption = 0.0

    def get_suggested_rate(self, offer_item: str, want_item: str, season: str = "spring") -> float:
        """How many want_items should 1 offer_item buy, based on trade history or effort values."""
        # Check trade history first
        rates = self.exchange_rates.get(offer_item, {})
        if want_item in rates:
            return rates[want_item]
        # Fall back to effort ratio
        offer_val = self.get_effort_value(offer_item, season)
        want_val = self.get_effort_value(want_item, season)
        if want_val == 0:
            return 1.0
        return round(offer_val / want_val, 2)

    def get_top_traders(self, n: int = 5) -> list[tuple[str, int]]:
        return sorted(self.agent_trade_counts.items(), key=lambda x: x[1], reverse=True)[:n]

    def get_avg_fairness(self) -> float:
        recent = self.trade_history[-30:]
        if not recent:
            return 1.0
        return round(sum(t.fairness for t in recent) / len(recent), 2)

    def to_dict(self) -> dict:
        return {
            "totalTrades": self.total_trades,
            "recentTrades": [
                {
                    "tick": t.tick,
                    "giver": t.giver,
                    "receiver": t.receiver,
                    "givenItem": t.given_item,
                    "givenQty": t.given_qty,
                    "receivedItem": t.received_item,
                    "receivedQty": t.received_qty,
                    "fairness": t.fairness,
                    "context": t.context,
                }
                for t in self.trade_history[-20:]
            ],
            "exchangeRates": self.exchange_rates,
            "currencyItem": self.currency_item,
            "currencyAdoption": self.currency_adoption,
            "avgFairness": self.get_avg_fairness(),
            "topTraders": [{"name": n, "trades": c} for n, c in self.get_top_traders()],
            "effortValues": EFFORT_VALUES,
        }
