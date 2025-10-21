"""
Risk management module.
Handles position limits, drawdown controls, and risk monitoring.
"""

import logging
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Callable, Any
from decimal import Decimal
from collections import defaultdict

from .config import Config
from .types import TradingSignal, RiskEvent, Position, Fill, OrderSide


class RiskManager:
    """
    Risk management and position monitoring.
    
    Handles:
    - Position size limits
    - Drawdown controls
    - Risk event monitoring
    - Position tracking
    """
    
    def __init__(self, config: Config):
        """Initialize risk manager."""
        self.config = config
        self.logger = logging.getLogger(__name__)
        
        # Position tracking
        self.positions: Dict[str, Position] = {}
        self.daily_pnl: Dict[str, Decimal] = defaultdict(Decimal)
        self.consecutive_losses: Dict[str, int] = defaultdict(int)
        
        # Risk limits
        self.max_position_size = Decimal(str(config.trading.max_position_size))
        self.max_daily_drawdown = Decimal(str(config.risk.max_daily_drawdown))
        self.max_consecutive_losses = config.trading.max_consecutive_losses
        self.position_limits = config.risk.position_limits
        
        # Risk state
        self.is_risk_breach = False
        self.risk_breach_reason = ""
        self.last_risk_check = 0
        
        # Event handlers
        self.on_risk_event: Optional[Callable] = None
        
        # Statistics
        self.risk_checks_performed = 0
        self.risk_events_triggered = 0
        self.signals_rejected = 0
    
    async def initialize(self) -> None:
        """Initialize the risk manager."""
        try:
            # Load existing positions
            await self._load_positions()
            
            self.logger.info("Risk manager initialized")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize risk manager: {e}")
            raise
    
    async def _load_positions(self) -> None:
        """Load existing positions from exchange."""
        # This would typically load from the exchange or database
        # For now, we'll start with empty positions
        pass
    
    async def check_signal(self, signal: TradingSignal) -> bool:
        """
        Check if a trading signal is allowed by risk management.
        
        Args:
            signal: Trading signal to check
            
        Returns:
            True if signal is allowed, False otherwise
        """
        try:
            self.risk_checks_performed += 1
            self.last_risk_check = time.time()
            
            # Check if risk management is disabled due to breach
            if self.is_risk_breach:
                await self._trigger_risk_event(
                    "RISK_BREACH",
                    f"Risk management disabled due to: {self.risk_breach_reason}",
                    "CRITICAL"
                )
                self.signals_rejected += 1
                return False
            
            # Check position size limits
            if not await self._check_position_limits(signal):
                self.signals_rejected += 1
                return False
            
            # Check daily drawdown
            if not await self._check_daily_drawdown(signal):
                self.signals_rejected += 1
                return False
            
            # Check consecutive losses
            if not await self._check_consecutive_losses(signal):
                self.signals_rejected += 1
                return False
            
            # Check leverage limits
            if not await self._check_leverage_limits(signal):
                self.signals_rejected += 1
                return False
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error checking signal: {e}")
            return False
    
    async def _check_position_limits(self, signal: TradingSignal) -> bool:
        """Check position size limits."""
        try:
            symbol = signal.symbol
            
            # Get current position
            current_position = self.positions.get(symbol)
            current_size = current_position.size if current_position else Decimal('0')
            
            # Calculate new position size
            if signal.side == OrderSide.BUY:
                new_size = current_size + signal.quantity
            else:
                new_size = current_size - signal.quantity
            
            # Check absolute position size limit
            if abs(new_size) > self.max_position_size:
                await self._trigger_risk_event(
                    "POSITION_LIMIT_EXCEEDED",
                    f"Position size {new_size} exceeds limit {self.max_position_size}",
                    "WARNING",
                    symbol=symbol
                )
                return False
            
            # Check symbol-specific position limits
            if symbol in self.position_limits:
                max_ratio = Decimal(str(self.position_limits[symbol]))
                # This would need account equity to calculate properly
                # For now, we'll use a simple check
                if abs(new_size) > self.max_position_size * max_ratio:
                    await self._trigger_risk_event(
                        "SYMBOL_POSITION_LIMIT_EXCEEDED",
                        f"Position size {new_size} exceeds symbol limit {max_ratio}",
                        "WARNING",
                        symbol=symbol
                    )
                    return False
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error checking position limits: {e}")
            return False
    
    async def _check_daily_drawdown(self, signal: TradingSignal) -> bool:
        """Check daily drawdown limits."""
        try:
            # Calculate current daily P&L
            total_daily_pnl = sum(self.daily_pnl.values())
            
            # Check if drawdown limit is exceeded
            if total_daily_pnl < -self.max_daily_drawdown:
                await self._trigger_risk_event(
                    "DAILY_DRAWDOWN_EXCEEDED",
                    f"Daily P&L {total_daily_pnl} exceeds drawdown limit {self.max_daily_drawdown}",
                    "CRITICAL"
                )
                self.is_risk_breach = True
                self.risk_breach_reason = "Daily drawdown exceeded"
                return False
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error checking daily drawdown: {e}")
            return False
    
    async def _check_consecutive_losses(self, signal: TradingSignal) -> bool:
        """Check consecutive loss limits."""
        try:
            symbol = signal.symbol
            consecutive_losses = self.consecutive_losses.get(symbol, 0)
            
            if consecutive_losses >= self.max_consecutive_losses:
                await self._trigger_risk_event(
                    "CONSECUTIVE_LOSSES_EXCEEDED",
                    f"Consecutive losses {consecutive_losses} exceeds limit {self.max_consecutive_losses}",
                    "WARNING",
                    symbol=symbol
                )
                return False
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error checking consecutive losses: {e}")
            return False
    
    async def _check_leverage_limits(self, signal: TradingSignal) -> bool:
        """Check leverage limits."""
        try:
            # This would need to check current leverage vs. max leverage
            # For spot trading, leverage is always 1.0
            # For futures, this would check the actual leverage
            
            max_leverage = Decimal(str(self.config.risk.max_leverage))
            
            if max_leverage < Decimal('1.0'):
                await self._trigger_risk_event(
                    "LEVERAGE_LIMIT_EXCEEDED",
                    f"Leverage exceeds limit {max_leverage}",
                    "WARNING",
                    symbol=signal.symbol
                )
                return False
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error checking leverage limits: {e}")
            return False
    
    async def update_position(self, fill: Fill) -> None:
        """Update position based on fill."""
        try:
            symbol = fill.symbol
            side = fill.side
            quantity = fill.quantity
            price = fill.price
            
            # Get current position
            current_position = self.positions.get(symbol)
            
            if current_position:
                # Update existing position
                if side == OrderSide.BUY:
                    new_size = current_position.size + quantity
                    new_entry_price = (
                        (current_position.entry_price * current_position.size + price * quantity) / 
                        new_size if new_size != 0 else current_position.entry_price
                    )
                else:
                    new_size = current_position.size - quantity
                    new_entry_price = current_position.entry_price
                
                # Update position
                current_position.size = new_size
                current_position.entry_price = new_entry_price
                current_position.updated_at = datetime.utcnow()
                
                # Update P&L
                current_position.unrealized_pnl = self._calculate_unrealized_pnl(current_position)
                
            else:
                # Create new position
                new_position = Position(
                    symbol=symbol,
                    side=PositionSide.LONG if side == OrderSide.BUY else PositionSide.SHORT,
                    size=quantity if side == OrderSide.BUY else -quantity,
                    entry_price=price,
                    mark_price=price,
                    unrealized_pnl=Decimal('0'),
                    leverage=Decimal('1.0')
                )
                
                self.positions[symbol] = new_position
            
            # Update daily P&L
            self._update_daily_pnl(symbol, fill)
            
            # Update consecutive losses
            self._update_consecutive_losses(symbol, fill)
            
        except Exception as e:
            self.logger.error(f"Error updating position: {e}")
    
    def _calculate_unrealized_pnl(self, position: Position) -> Decimal:
        """Calculate unrealized P&L for a position."""
        try:
            if position.size == 0:
                return Decimal('0')
            
            # This would need current market price
            # For now, we'll use entry price as approximation
            current_price = position.mark_price
            
            if position.side == PositionSide.LONG:
                return (current_price - position.entry_price) * position.size
            else:
                return (position.entry_price - current_price) * abs(position.size)
                
        except Exception as e:
            self.logger.error(f"Error calculating unrealized P&L: {e}")
            return Decimal('0')
    
    def _update_daily_pnl(self, symbol: str, fill: Fill) -> None:
        """Update daily P&L for a symbol."""
        try:
            # This is a simplified calculation
            # In practice, you'd calculate realized P&L from fills
            pnl = fill.quantity * fill.price * Decimal('0.001')  # Simplified P&L
            self.daily_pnl[symbol] += pnl
            
        except Exception as e:
            self.logger.error(f"Error updating daily P&L: {e}")
    
    def _update_consecutive_losses(self, symbol: str, fill: Fill) -> None:
        """Update consecutive loss count for a symbol."""
        try:
            # This is a simplified calculation
            # In practice, you'd track actual wins/losses
            # For now, we'll reset on any fill
            self.consecutive_losses[symbol] = 0
            
        except Exception as e:
            self.logger.error(f"Error updating consecutive losses: {e}")
    
    async def update_market_data(self, market_data) -> None:
        """Update positions with latest market data."""
        try:
            symbol = market_data.symbol
            price = market_data.price
            
            if symbol in self.positions:
                position = self.positions[symbol]
                position.mark_price = price
                position.unrealized_pnl = self._calculate_unrealized_pnl(position)
                position.updated_at = datetime.utcnow()
                
        except Exception as e:
            self.logger.error(f"Error updating market data: {e}")
    
    async def _trigger_risk_event(
        self, 
        event_type: str, 
        message: str, 
        severity: str,
        symbol: Optional[str] = None
    ) -> None:
        """Trigger a risk event."""
        try:
            risk_event = RiskEvent(
                event_type=event_type,
                symbol=symbol,
                message=message,
                severity=severity,
                metadata={
                    'timestamp': time.time(),
                    'positions': {k: float(v.size) for k, v in self.positions.items()},
                    'daily_pnl': {k: float(v) for k, v in self.daily_pnl.items()},
                }
            )
            
            self.risk_events_triggered += 1
            
            # Notify handlers
            if self.on_risk_event:
                await self.on_risk_event(risk_event)
            
            self.logger.warning(f"Risk event: {message}")
            
        except Exception as e:
            self.logger.error(f"Error triggering risk event: {e}")
    
    async def reset_daily_pnl(self) -> None:
        """Reset daily P&L (typically called at start of day)."""
        self.daily_pnl.clear()
        self.logger.info("Daily P&L reset")
    
    async def reset_risk_breach(self) -> None:
        """Reset risk breach state."""
        self.is_risk_breach = False
        self.risk_breach_reason = ""
        self.logger.info("Risk breach state reset")
    
    def get_positions(self) -> Dict[str, Position]:
        """Get current positions."""
        return self.positions.copy()
    
    def get_daily_pnl(self) -> Dict[str, Decimal]:
        """Get daily P&L by symbol."""
        return self.daily_pnl.copy()
    
    def get_risk_status(self) -> Dict[str, Any]:
        """Get current risk status."""
        return {
            'is_risk_breach': self.is_risk_breach,
            'risk_breach_reason': self.risk_breach_reason,
            'total_positions': len(self.positions),
            'total_daily_pnl': sum(self.daily_pnl.values()),
            'max_daily_drawdown': self.max_daily_drawdown,
            'risk_checks_performed': self.risk_checks_performed,
            'risk_events_triggered': self.risk_events_triggered,
            'signals_rejected': self.signals_rejected,
        }
