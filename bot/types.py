"""
Type definitions and data models for the trading bot.
"""

from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Dict, List, Optional, Union, Any
from pydantic import BaseModel, Field


class OrderSide(str, Enum):
    """Order side enumeration."""
    BUY = "BUY"
    SELL = "SELL"


class OrderType(str, Enum):
    """Order type enumeration."""
    LIMIT = "LIMIT"
    MARKET = "MARKET"
    STOP_LOSS = "STOP_LOSS"
    STOP_LOSS_LIMIT = "STOP_LOSS_LIMIT"
    TAKE_PROFIT = "TAKE_PROFIT"
    TAKE_PROFIT_LIMIT = "TAKE_PROFIT_LIMIT"
    LIMIT_MAKER = "LIMIT_MAKER"


class OrderStatus(str, Enum):
    """Order status enumeration."""
    NEW = "NEW"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    FILLED = "FILLED"
    CANCELED = "CANCELED"
    PENDING_CANCEL = "PENDING_CANCEL"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"


class TimeInForce(str, Enum):
    """Time in force enumeration."""
    GTC = "GTC"  # Good Till Canceled
    IOC = "IOC"  # Immediate or Cancel
    FOK = "FOK"  # Fill or Kill


class PositionSide(str, Enum):
    """Position side enumeration."""
    LONG = "LONG"
    SHORT = "SHORT"
    BOTH = "BOTH"


class MarketData(BaseModel):
    """Market data structure."""
    symbol: str
    timestamp: datetime
    price: Decimal
    volume: Decimal
    side: OrderSide


class OrderBookLevel(BaseModel):
    """Order book level."""
    price: Decimal
    quantity: Decimal


class OrderBook(BaseModel):
    """Order book snapshot."""
    symbol: str
    timestamp: datetime
    bids: List[OrderBookLevel]
    asks: List[OrderBookLevel]
    last_update_id: int


class Kline(BaseModel):
    """Kline/candlestick data."""
    symbol: str
    open_time: datetime
    close_time: datetime
    open_price: Decimal
    high_price: Decimal
    low_price: Decimal
    close_price: Decimal
    volume: Decimal
    quote_volume: Decimal
    trades_count: int
    taker_buy_volume: Decimal
    taker_buy_quote_volume: Decimal
    is_closed: bool


class Order(BaseModel):
    """Order structure."""
    symbol: str
    order_id: Optional[int] = None
    client_order_id: Optional[str] = None
    side: OrderSide
    type: OrderType
    quantity: Decimal
    price: Optional[Decimal] = None
    stop_price: Optional[Decimal] = None
    time_in_force: TimeInForce = TimeInForce.GTC
    status: OrderStatus = OrderStatus.NEW
    executed_qty: Decimal = Decimal("0")
    cummulative_quote_qty: Decimal = Decimal("0")
    avg_price: Optional[Decimal] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class Fill(BaseModel):
    """Trade fill structure."""
    symbol: str
    order_id: int
    trade_id: int
    side: OrderSide
    quantity: Decimal
    price: Decimal
    commission: Decimal
    commission_asset: str
    timestamp: datetime
    is_maker: bool = False


class Position(BaseModel):
    """Position structure."""
    symbol: str
    side: PositionSide
    size: Decimal
    entry_price: Decimal
    mark_price: Decimal
    unrealized_pnl: Decimal
    realized_pnl: Decimal = Decimal("0")
    margin: Decimal = Decimal("0")
    leverage: Decimal = Decimal("1")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class AccountInfo(BaseModel):
    """Account information."""
    account_type: str
    can_trade: bool
    can_deposit: bool
    can_withdraw: bool
    update_time: datetime
    balances: Dict[str, Decimal] = Field(default_factory=dict)
    permissions: List[str] = Field(default_factory=list)


class TradingSignal(BaseModel):
    """Trading signal from strategy."""
    symbol: str
    side: OrderSide
    quantity: Decimal
    price: Optional[Decimal] = None
    order_type: OrderType = OrderType.LIMIT
    time_in_force: TimeInForce = TimeInForce.GTC
    stop_price: Optional[Decimal] = None
    strategy_name: str
    confidence: float = 1.0
    metadata: Dict[str, Any] = Field(default_factory=dict)


class RiskEvent(BaseModel):
    """Risk management event."""
    event_type: str
    symbol: Optional[str] = None
    message: str
    severity: str = "WARNING"  # INFO, WARNING, ERROR, CRITICAL
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class BacktestResult(BaseModel):
    """Backtest result."""
    strategy_name: str
    start_date: datetime
    end_date: datetime
    initial_capital: Decimal
    final_capital: Decimal
    total_return: Decimal
    total_return_pct: Decimal
    max_drawdown: Decimal
    max_drawdown_pct: Decimal
    sharpe_ratio: Decimal
    win_rate: Decimal
    total_trades: int
    winning_trades: int
    losing_trades: int
    avg_win: Decimal
    avg_loss: Decimal
    profit_factor: Decimal
    trades: List[Fill] = Field(default_factory=list)


class ExchangeInfo(BaseModel):
    """Exchange information."""
    timezone: str
    server_time: datetime
    rate_limits: List[Dict[str, Any]] = Field(default_factory=list)
    symbols: List[Dict[str, Any]] = Field(default_factory=list)
    exchange_filters: List[Dict[str, Any]] = Field(default_factory=list)


class WebSocketMessage(BaseModel):
    """WebSocket message wrapper."""
    stream: str
    data: Dict[str, Any]
    timestamp: datetime = Field(default_factory=datetime.utcnow)


# Type aliases for common use cases
Symbol = str
Price = Decimal
Quantity = Decimal
Timestamp = datetime
StrategyName = str
OrderId = Union[int, str]
