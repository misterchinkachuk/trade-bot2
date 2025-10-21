"""
Accounting and P&L tracking module.
Handles trade recording, P&L calculation, and financial reporting.
"""

import logging
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from decimal import Decimal
from collections import defaultdict
import asyncpg

from .config import Config
from .types import Order, Fill, Position, OrderSide, PositionSide


class AccountingManager:
    """
    Accounting and P&L tracking.
    
    Handles:
    - Trade recording and storage
    - P&L calculation
    - Fee tracking
    - Financial reporting
    """
    
    def __init__(self, config: Config):
        """Initialize accounting manager."""
        self.config = config
        self.logger = logging.getLogger(__name__)
        
        # Database connection
        self.db_pool: Optional[asyncpg.Pool] = None
        
        # In-memory tracking
        self.trades: List[Fill] = []
        self.positions: Dict[str, Position] = {}
        self.daily_pnl: Dict[str, Decimal] = defaultdict(Decimal)
        self.total_pnl: Decimal = Decimal('0')
        self.total_fees: Decimal = Decimal('0')
        
        # Statistics
        self.trades_recorded = 0
        self.positions_updated = 0
        self.pnl_calculations = 0
    
    async def initialize(self) -> None:
        """Initialize the accounting manager."""
        try:
            # Initialize database pool
            self.db_pool = await asyncpg.create_pool(
                host=self.config.database.host,
                port=self.config.database.port,
                database=self.config.database.database,
                user=self.config.database.username,
                password=self.config.database.password,
                min_size=5,
                max_size=20
            )
            
            # Create tables if they don't exist
            await self._create_tables()
            
            # Load existing data
            await self._load_existing_data()
            
            self.logger.info("Accounting manager initialized")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize accounting manager: {e}")
            raise
    
    async def close(self) -> None:
        """Close the accounting manager."""
        if self.db_pool:
            await self.db_pool.close()
    
    async def _create_tables(self) -> None:
        """Create database tables if they don't exist."""
        try:
            if not self.db_pool:
                return
            
            async with self.db_pool.acquire() as conn:
                # Create trades table
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS trades (
                        id SERIAL PRIMARY KEY,
                        symbol VARCHAR(20) NOT NULL,
                        order_id BIGINT NOT NULL,
                        trade_id BIGINT NOT NULL,
                        side VARCHAR(10) NOT NULL,
                        quantity DECIMAL(20, 8) NOT NULL,
                        price DECIMAL(20, 8) NOT NULL,
                        commission DECIMAL(20, 8) NOT NULL,
                        commission_asset VARCHAR(10) NOT NULL,
                        timestamp TIMESTAMP NOT NULL,
                        is_maker BOOLEAN NOT NULL DEFAULT FALSE,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # Create positions table
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS positions (
                        id SERIAL PRIMARY KEY,
                        symbol VARCHAR(20) NOT NULL,
                        side VARCHAR(10) NOT NULL,
                        size DECIMAL(20, 8) NOT NULL,
                        entry_price DECIMAL(20, 8) NOT NULL,
                        mark_price DECIMAL(20, 8) NOT NULL,
                        unrealized_pnl DECIMAL(20, 8) NOT NULL DEFAULT 0,
                        realized_pnl DECIMAL(20, 8) NOT NULL DEFAULT 0,
                        margin DECIMAL(20, 8) NOT NULL DEFAULT 0,
                        leverage DECIMAL(10, 4) NOT NULL DEFAULT 1.0,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # Create daily_pnl table
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS daily_pnl (
                        id SERIAL PRIMARY KEY,
                        date DATE NOT NULL,
                        symbol VARCHAR(20) NOT NULL,
                        realized_pnl DECIMAL(20, 8) NOT NULL DEFAULT 0,
                        unrealized_pnl DECIMAL(20, 8) NOT NULL DEFAULT 0,
                        total_pnl DECIMAL(20, 8) NOT NULL DEFAULT 0,
                        fees DECIMAL(20, 8) NOT NULL DEFAULT 0,
                        volume DECIMAL(20, 8) NOT NULL DEFAULT 0,
                        trades_count INTEGER NOT NULL DEFAULT 0,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE(date, symbol)
                    )
                """)
                
                # Create indexes
                await conn.execute("CREATE INDEX IF NOT EXISTS idx_trades_symbol ON trades(symbol)")
                await conn.execute("CREATE INDEX IF NOT EXISTS idx_trades_timestamp ON trades(timestamp)")
                await conn.execute("CREATE INDEX IF NOT EXISTS idx_positions_symbol ON positions(symbol)")
                await conn.execute("CREATE INDEX IF NOT EXISTS idx_daily_pnl_date ON daily_pnl(date)")
                
        except Exception as e:
            self.logger.error(f"Error creating tables: {e}")
            raise
    
    async def _load_existing_data(self) -> None:
        """Load existing data from database."""
        try:
            if not self.db_pool:
                return
            
            async with self.db_pool.acquire() as conn:
                # Load recent trades
                rows = await conn.fetch("""
                    SELECT * FROM trades 
                    ORDER BY timestamp DESC 
                    LIMIT 1000
                """)
                
                for row in rows:
                    trade = Fill(
                        symbol=row['symbol'],
                        order_id=row['order_id'],
                        trade_id=row['trade_id'],
                        side=OrderSide(row['side']),
                        quantity=row['quantity'],
                        price=row['price'],
                        commission=row['commission'],
                        commission_asset=row['commission_asset'],
                        timestamp=row['timestamp'],
                        is_maker=row['is_maker']
                    )
                    self.trades.append(trade)
                
                # Load current positions
                rows = await conn.fetch("SELECT * FROM positions")
                
                for row in rows:
                    position = Position(
                        symbol=row['symbol'],
                        side=PositionSide(row['side']),
                        size=row['size'],
                        entry_price=row['entry_price'],
                        mark_price=row['mark_price'],
                        unrealized_pnl=row['unrealized_pnl'],
                        realized_pnl=row['realized_pnl'],
                        margin=row['margin'],
                        leverage=row['leverage'],
                        created_at=row['created_at'],
                        updated_at=row['updated_at']
                    )
                    self.positions[row['symbol']] = position
                
                # Load daily P&L for current month
                today = datetime.now().date()
                month_start = today.replace(day=1)
                
                rows = await conn.fetch("""
                    SELECT * FROM daily_pnl 
                    WHERE date >= $1
                """, month_start)
                
                for row in rows:
                    self.daily_pnl[row['symbol']] = row['total_pnl']
                
                self.logger.info(f"Loaded {len(self.trades)} trades and {len(self.positions)} positions")
                
        except Exception as e:
            self.logger.error(f"Error loading existing data: {e}")
    
    async def record_fill(self, fill: Fill) -> None:
        """Record a trade fill."""
        try:
            # Add to in-memory list
            self.trades.append(fill)
            self.trades_recorded += 1
            
            # Store in database
            if self.db_pool:
                async with self.db_pool.acquire() as conn:
                    await conn.execute("""
                        INSERT INTO trades (symbol, order_id, trade_id, side, quantity, price, 
                                          commission, commission_asset, timestamp, is_maker)
                        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                        ON CONFLICT (trade_id) DO NOTHING
                    """, 
                    fill.symbol, fill.order_id, fill.trade_id, fill.side.value,
                    fill.quantity, fill.price, fill.commission, fill.commission_asset,
                    fill.timestamp, fill.is_maker
                    )
            
            # Update position
            await self._update_position(fill)
            
            # Update daily P&L
            await self._update_daily_pnl(fill)
            
            # Update total fees
            self.total_fees += fill.commission
            
            self.logger.info(f"Recorded fill: {fill}")
            
        except Exception as e:
            self.logger.error(f"Error recording fill: {e}")
    
    async def _update_position(self, fill: Fill) -> None:
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
                
                # Calculate realized P&L if position is closed
                if current_position.size > 0 and new_size <= 0:
                    # Position closed or reversed
                    realized_pnl = (price - current_position.entry_price) * current_position.size
                    current_position.realized_pnl += realized_pnl
                    self.total_pnl += realized_pnl
                
                # Update position
                current_position.size = new_size
                current_position.entry_price = new_entry_price
                current_position.updated_at = datetime.utcnow()
                
            else:
                # Create new position
                new_position = Position(
                    symbol=symbol,
                    side=PositionSide.LONG if side == OrderSide.BUY else PositionSide.SHORT,
                    size=quantity if side == OrderSide.BUY else -quantity,
                    entry_price=price,
                    mark_price=price,
                    unrealized_pnl=Decimal('0'),
                    realized_pnl=Decimal('0'),
                    leverage=Decimal('1.0')
                )
                
                self.positions[symbol] = new_position
            
            # Store position in database
            if self.db_pool:
                await self._store_position(self.positions[symbol])
            
            self.positions_updated += 1
            
        except Exception as e:
            self.logger.error(f"Error updating position: {e}")
    
    async def _store_position(self, position: Position) -> None:
        """Store position in database."""
        try:
            if not self.db_pool:
                return
            
            async with self.db_pool.acquire() as conn:
                await conn.execute("""
                    INSERT INTO positions (symbol, side, size, entry_price, mark_price, 
                                         unrealized_pnl, realized_pnl, margin, leverage)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                    ON CONFLICT (symbol) DO UPDATE SET
                        side = EXCLUDED.side,
                        size = EXCLUDED.size,
                        entry_price = EXCLUDED.entry_price,
                        mark_price = EXCLUDED.mark_price,
                        unrealized_pnl = EXCLUDED.unrealized_pnl,
                        realized_pnl = EXCLUDED.realized_pnl,
                        margin = EXCLUDED.margin,
                        leverage = EXCLUDED.leverage,
                        updated_at = CURRENT_TIMESTAMP
                """, 
                position.symbol, position.side.value, position.size, position.entry_price,
                position.mark_price, position.unrealized_pnl, position.realized_pnl,
                position.margin, position.leverage
                )
                
        except Exception as e:
            self.logger.error(f"Error storing position: {e}")
    
    async def _update_daily_pnl(self, fill: Fill) -> None:
        """Update daily P&L."""
        try:
            symbol = fill.symbol
            today = datetime.now().date()
            
            # Calculate P&L for this trade
            # This is simplified - in practice, you'd calculate based on position changes
            pnl = fill.quantity * fill.price * Decimal('0.001')  # Simplified P&L
            
            # Update in-memory tracking
            self.daily_pnl[symbol] += pnl
            
            # Store in database
            if self.db_pool:
                async with self.db_pool.acquire() as conn:
                    await conn.execute("""
                        INSERT INTO daily_pnl (date, symbol, realized_pnl, total_pnl, 
                                             fees, volume, trades_count)
                        VALUES ($1, $2, $3, $4, $5, $6, 1)
                        ON CONFLICT (date, symbol) DO UPDATE SET
                            realized_pnl = daily_pnl.realized_pnl + EXCLUDED.realized_pnl,
                            total_pnl = daily_pnl.total_pnl + EXCLUDED.total_pnl,
                            fees = daily_pnl.fees + EXCLUDED.fees,
                            volume = daily_pnl.volume + EXCLUDED.volume,
                            trades_count = daily_pnl.trades_count + 1
                    """, 
                    today, symbol, pnl, pnl, fill.commission, fill.quantity
                    )
            
        except Exception as e:
            self.logger.error(f"Error updating daily P&L: {e}")
    
    async def update_order(self, order: Order) -> None:
        """Update order information."""
        try:
            # This would typically update order status in database
            # For now, we'll just log it
            self.logger.debug(f"Order updated: {order}")
            
        except Exception as e:
            self.logger.error(f"Error updating order: {e}")
    
    async def get_positions(self) -> Dict[str, Position]:
        """Get current positions."""
        return self.positions.copy()
    
    async def get_daily_pnl(self, symbol: Optional[str] = None) -> Dict[str, Decimal]:
        """Get daily P&L."""
        if symbol:
            return {symbol: self.daily_pnl.get(symbol, Decimal('0'))}
        return self.daily_pnl.copy()
    
    async def get_total_pnl(self) -> Decimal:
        """Get total P&L."""
        return self.total_pnl
    
    async def get_trades(self, symbol: Optional[str] = None, limit: int = 100) -> List[Fill]:
        """Get recent trades."""
        trades = self.trades
        
        if symbol:
            trades = [trade for trade in trades if trade.symbol == symbol]
        
        return trades[-limit:]
    
    async def get_pnl_report(self, days: int = 30) -> Dict[str, Any]:
        """Get P&L report for specified days."""
        try:
            if not self.db_pool:
                return {}
            
            end_date = datetime.now().date()
            start_date = end_date - timedelta(days=days)
            
            async with self.db_pool.acquire() as conn:
                rows = await conn.fetch("""
                    SELECT date, symbol, total_pnl, fees, volume, trades_count
                    FROM daily_pnl
                    WHERE date >= $1 AND date <= $2
                    ORDER BY date DESC
                """, start_date, end_date)
                
                report = {
                    'period': f"{start_date} to {end_date}",
                    'total_pnl': Decimal('0'),
                    'total_fees': Decimal('0'),
                    'total_volume': Decimal('0'),
                    'total_trades': 0,
                    'daily_breakdown': []
                }
                
                for row in rows:
                    daily_data = {
                        'date': row['date'],
                        'symbol': row['symbol'],
                        'pnl': row['total_pnl'],
                        'fees': row['fees'],
                        'volume': row['volume'],
                        'trades': row['trades_count']
                    }
                    report['daily_breakdown'].append(daily_data)
                    
                    report['total_pnl'] += row['total_pnl']
                    report['total_fees'] += row['fees']
                    report['total_volume'] += row['volume']
                    report['total_trades'] += row['trades_count']
                
                return report
                
        except Exception as e:
            self.logger.error(f"Error generating P&L report: {e}")
            return {}
    
    def get_stats(self) -> Dict[str, Any]:
        """Get accounting manager statistics."""
        return {
            'trades_recorded': self.trades_recorded,
            'positions_updated': self.positions_updated,
            'total_pnl': float(self.total_pnl),
            'total_fees': float(self.total_fees),
            'active_positions': len(self.positions),
            'total_trades': len(self.trades),
        }
