"""DB tables. Owned by the main session; feature sessions read/write rows but don't change the schema.

Convention: columns that are filtered or sorted on are real columns; the rest lives in JSON.
`DecisionRow.payload` holds the full `contracts.Decision` JSON.
"""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import JSON, Column, DateTime
from sqlmodel import Field, SQLModel


def _ts(index: bool = False, nullable: bool = False):
    return Field(sa_column=Column(DateTime(timezone=True), index=index, nullable=nullable))


def _json(default=dict):
    return Field(default_factory=default, sa_column=Column(JSON))


class CustomerRow(SQLModel, table=True):
    __tablename__ = "customers"
    id: str = Field(primary_key=True)
    first_name: str
    age: int | None = None
    gender: str | None = None
    city: str
    city_tier: int = Field(index=True)
    signup_date: date
    channel: str
    device: str
    preferred_payment: str
    persona: str = Field(index=True)
    response_type: str  # hidden ground truth
    telegram_chat_id: int | None = Field(default=None, index=True)
    is_lab_bot: bool = False
    opt_in_festivals: list = _json(list)
    opted_out: bool = False
    paused_until: datetime | None = _ts(nullable=True)
    is_holdout: bool = Field(default=False, index=True)
    points_balance: int = 0
    tier: str = "Bronze"
    suppressed: dict = _json()  # {category: until_iso}
    attrs: dict = _json()  # free-form generator extras


class ProductRow(SQLModel, table=True):
    __tablename__ = "products"
    id: str = Field(primary_key=True)
    name: str
    category: str = Field(index=True)
    price: int
    margin: float


class EventRow(SQLModel, table=True):
    __tablename__ = "events"
    id: str = Field(primary_key=True)
    customer_id: str = Field(index=True, foreign_key="customers.id")
    type: str = Field(index=True)
    ts: datetime = _ts(index=True)
    category: str | None = None
    item: str | None = None
    value: int | None = None
    meta: dict = _json()


class OrderRow(SQLModel, table=True):
    __tablename__ = "orders"
    id: str = Field(primary_key=True)
    customer_id: str = Field(index=True, foreign_key="customers.id")
    ts: datetime = _ts(index=True)
    category: str = Field(index=True)
    items: int = 1
    value: int
    discount: int = 0
    coupon_code: str | None = None
    payment_method: str = "upi"
    returned: bool = False


class PointsLedgerRow(SQLModel, table=True):
    __tablename__ = "points_ledger"
    id: int | None = Field(default=None, primary_key=True)
    customer_id: str = Field(index=True, foreign_key="customers.id")
    ts: datetime = _ts()
    delta: int
    reason: str
    expires_on: date | None = None


class CampaignHistoryRow(SQLModel, table=True):
    """Simulated past campaigns (offers_sent + redemptions) — training data for the uplift model."""

    __tablename__ = "campaign_history"
    id: int | None = Field(default=None, primary_key=True)
    campaign_id: str = Field(index=True)
    customer_id: str = Field(index=True, foreign_key="customers.id")
    sent_at: datetime = _ts()
    offer_type: str
    params: dict = _json()
    is_control: bool = False
    converted: bool = False
    revenue: int = 0


class OfferRow(SQLModel, table=True):
    __tablename__ = "offers"
    id: str = Field(primary_key=True)
    type: str
    name: str
    description: str
    categories: list | None = Field(default=None, sa_column=Column(JSON))
    param_schema: dict = _json()
    base_cost_model: str
    enabled: bool = True


class RuleRow(SQLModel, table=True):
    __tablename__ = "rules"
    id: str = Field(primary_key=True)
    layer: str = Field(index=True)
    type: str
    severity: str
    conditions: dict = _json()
    params: dict = _json()
    enabled: bool = True
    priority: int = 100
    version: int = 1
    description: str = ""
    updated_by: str = "system"
    updated_at: datetime = _ts()


class RuleVersionRow(SQLModel, table=True):
    __tablename__ = "rule_versions"
    id: int | None = Field(default=None, primary_key=True)
    rule_id: str = Field(index=True)
    version: int
    snapshot: dict = _json()  # full contracts.Rule JSON
    created_at: datetime = _ts()


class DecisionRow(SQLModel, table=True):
    __tablename__ = "decisions"
    id: str = Field(primary_key=True)
    ts: datetime = _ts(index=True)
    customer_id: str = Field(index=True)
    policy: str = Field(index=True)
    trigger: str = Field(index=True)
    decided_by: str = Field(index=True)
    status: str = Field(index=True)
    final_offer_id: str | None = None
    coupon_code: str | None = Field(default=None, index=True)
    cost: int = 0
    expected_incremental_profit: int = 0
    channel: str = "none"
    is_holdout: bool = False
    outcome: str = Field(default="pending", index=True)
    outcome_at: datetime | None = _ts(nullable=True)
    revenue: int | None = None
    telegram_message_id: int | None = None
    payload: dict = _json()  # full contracts.Decision


class FestivalRow(SQLModel, table=True):
    __tablename__ = "festivals"
    id: str = Field(primary_key=True)
    date: date
    payload: dict = _json()  # full contracts.Festival


class SettingRow(SQLModel, table=True):
    """Key-value runtime settings: killswitch, budgets, demo time override."""

    __tablename__ = "settings"
    key: str = Field(primary_key=True)
    value: dict = _json()
    updated_at: datetime = _ts()


class CustomerBotRow(SQLModel, table=True):
    """Customer Lab: which bot (by username, never the token) plays which synthetic customer."""

    __tablename__ = "customer_bots"
    username: str = Field(primary_key=True)
    customer_id: str = Field(foreign_key="customers.id")
    persona: str
