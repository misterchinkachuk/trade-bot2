"""
Order execution and management module.
Handles order placement, tracking, and lifecycle management.
"""

import asyncio
import logging
import time
from datetime import datetime
from typing import Dict, List, Optional, Callable, Any
from decimal import Decimal
import uuid

from .config import Config
from .types import Order, OrderSide, OrderType, TimeInForce, OrderStatus, Fill, TradingSignal
from .connectors import BinanceRESTClient


class OrderManager:
    """
    Order execution and management.
    
    Handles:
    - Order placement and tracking
    - Order lifecycle management
    - Fill processing
    - Order state reconciliation
    """
    
    def __init__(self, config: Config):
        """Initialize order manager."""
        self.config = config
        self.logger = logging.getLogger(__name__)
        
        # REST client
        self.rest_client: Optional[BinanceRESTClient] = None
        
        # Order tracking
        self.active_orders: Dict[str, Order] = {}
        self.order_history: List[Order] = []
        self.fills: List[Fill] = []
        
        # Event handlers
        self.on_order_update: Optional[Callable] = None
        self.on_fill: Optional[Callable] = None
        
        # Statistics
        self.orders_placed = 0
        self.orders_filled = 0
        self.orders_canceled = 0
        self.total_volume = Decimal('0')
        self.total_fees = Decimal('0')
    
    async def initialize(self) -> None:
        """Initialize the order manager."""
        try:
            # Initialize REST client
            self.rest_client = BinanceRESTClient(
                api_key=self.config.binance.api_key or "",
                api_secret=self.config.binance.api_secret or "",
                base_url=self.config.binance.base_url,
                testnet=self.config.binance.testnet
            )
            
            await self.rest_client.initialize()
            
            # Load existing orders
            await self._load_existing_orders()
            
            self.logger.info("Order manager initialized")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize order manager: {e}")
            raise
    
    async def close(self) -> None:
        """Close the order manager."""
        if self.rest_client:
            await self.rest_client.close()
    
    async def _load_existing_orders(self) -> None:
        """Load existing open orders from exchange."""
        try:
            if not self.rest_client:
                return
            
            for symbol in self.config.trading.symbols:
                orders = await self.rest_client.get_open_orders(symbol)
                
                for order in orders:
                    self.active_orders[order.client_order_id or str(order.order_id)] = order
                    self.order_history.append(order)
            
            self.logger.info(f"Loaded {len(self.active_orders)} existing orders")
            
        except Exception as e:
            self.logger.error(f"Error loading existing orders: {e}")
    
    async def submit_signal(self, signal: TradingSignal) -> Optional[Order]:
        """
        Submit a trading signal for execution.
        
        Args:
            signal: Trading signal to execute
            
        Returns:
            Created order or None if failed
        """
        try:
            if not self.rest_client:
                self.logger.error("REST client not initialized")
                return None
            
            # Generate client order ID
            client_order_id = f"{signal.strategy_name}_{int(time.time() * 1000)}_{uuid.uuid4().hex[:8]}"
            
            # Place order
            order = await self.rest_client.place_order(
                symbol=signal.symbol,
                side=signal.side,
                order_type=signal.order_type,
                quantity=float(signal.quantity),
                price=float(signal.price) if signal.price else None,
                time_in_force=signal.time_in_force,
                stop_price=float(signal.stop_price) if signal.stop_price else None,
                client_order_id=client_order_id
            )
            
            # Track order
            self.active_orders[client_order_id] = order
            self.order_history.append(order)
            self.orders_placed += 1
            
            # Notify handlers
            if self.on_order_update:
                await self.on_order_update(order)
            
            self.logger.info(f"Order placed: {order}")
            return order
            
        except Exception as e:
            self.logger.error(f"Failed to submit signal: {e}")
            return None
    
    async def cancel_order(self, order_id: str) -> bool:
        """
        Cancel an order.
        
        Args:
            order_id: Order ID or client order ID
            
        Returns:
            True if canceled successfully
        """
        try:
            if not self.rest_client:
                return False
            
            # Find order
            order = self.active_orders.get(order_id)
            if not order:
                self.logger.warning(f"Order not found: {order_id}")
                return False
            
            # Cancel order
            canceled_order = await self.rest_client.cancel_order(
                symbol=order.symbol,
                order_id=order.order_id,
                client_order_id=order.client_order_id
            )
            
            # Update local state
            self.active_orders.pop(order_id, None)
            canceled_order.status = OrderStatus.CANCELED
            self.order_history.append(canceled_order)
            self.orders_canceled += 1
            
            # Notify handlers
            if self.on_order_update:
                await self.on_order_update(canceled_order)
            
            self.logger.info(f"Order canceled: {order_id}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to cancel order {order_id}: {e}")
            return False
    
    async def cancel_all_orders(self, symbol: Optional[str] = None) -> int:
        """
        Cancel all orders for a symbol or all symbols.
        
        Args:
            symbol: Symbol to cancel orders for (None for all)
            
        Returns:
            Number of orders canceled
        """
        canceled_count = 0
        
        try:
            orders_to_cancel = []
            
            for order_id, order in self.active_orders.items():
                if symbol is None or order.symbol == symbol:
                    orders_to_cancel.append(order_id)
            
            # Cancel orders concurrently
            tasks = [self.cancel_order(order_id) for order_id in orders_to_cancel]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            canceled_count = sum(1 for result in results if result is True)
            
            self.logger.info(f"Canceled {canceled_count} orders")
            
        except Exception as e:
            self.logger.error(f"Error canceling orders: {e}")
        
        return canceled_count
    
    async def update_order_status(self, order_id: str) -> Optional[Order]:
        """
        Update order status from exchange.
        
        Args:
            order_id: Order ID or client order ID
            
        Returns:
            Updated order or None if not found
        """
        try:
            if not self.rest_client:
                return None
            
            # Find order
            order = self.active_orders.get(order_id)
            if not order:
                return None
            
            # Get updated order from exchange
            updated_order = await self.rest_client.get_order(
                symbol=order.symbol,
                order_id=order.order_id,
                client_order_id=order.client_order_id
            )
            
            # Update local state
            self.active_orders[order_id] = updated_order
            
            # Check for fills
            if updated_order.status in [OrderStatus.FILLED, OrderStatus.PARTIALLY_FILLED]:
                await self._process_fills(order, updated_order)
            
            # Notify handlers
            if self.on_order_update:
                await self.on_order_update(updated_order)
            
            return updated_order
            
        except Exception as e:
            self.logger.error(f"Error updating order status: {e}")
            return None
    
    async def _process_fills(self, old_order: Order, new_order: Order) -> None:
        """Process order fills."""
        try:
            # Calculate fill quantity
            fill_qty = new_order.executed_qty - old_order.executed_qty
            
            if fill_qty <= 0:
                return
            
            # Calculate fill price (approximate)
            if new_order.avg_price:
                fill_price = new_order.avg_price
            elif new_order.executed_qty > 0:
                fill_price = new_order.cummulative_quote_qty / new_order.executed_qty
            else:
                fill_price = old_order.price or Decimal('0')
            
            # Create fill record
            fill = Fill(
                symbol=new_order.symbol,
                order_id=new_order.order_id,
                trade_id=int(time.time() * 1000),  # Generate trade ID
                side=new_order.side,
                quantity=fill_qty,
                price=fill_price,
                commission=Decimal('0'),  # Will be updated from exchange
                commission_asset=new_order.symbol.split('USDT')[1] if 'USDT' in new_order.symbol else 'USDT',
                timestamp=datetime.utcnow(),
                is_maker=False  # Will be updated from exchange
            )
            
            # Track fill
            self.fills.append(fill)
            self.orders_filled += 1
            self.total_volume += fill_qty
            
            # Notify handlers
            if self.on_fill:
                await self.on_fill(fill)
            
            self.logger.info(f"Order filled: {fill}")
            
        except Exception as e:
            self.logger.error(f"Error processing fills: {e}")
    
    async def get_order(self, order_id: str) -> Optional[Order]:
        """Get order by ID."""
        return self.active_orders.get(order_id)
    
    async def get_active_orders(self, symbol: Optional[str] = None) -> List[Order]:
        """Get active orders."""
        if symbol:
            return [order for order in self.active_orders.values() if order.symbol == symbol]
        return list(self.active_orders.values())
    
    async def get_order_history(self, symbol: Optional[str] = None, limit: int = 100) -> List[Order]:
        """Get order history."""
        orders = self.order_history
        
        if symbol:
            orders = [order for order in orders if order.symbol == symbol]
        
        return orders[-limit:]
    
    async def get_fills(self, symbol: Optional[str] = None, limit: int = 100) -> List[Fill]:
        """Get fill history."""
        fills = self.fills
        
        if symbol:
            fills = [fill for fill in fills if fill.symbol == symbol]
        
        return fills[-limit:]
    
    def get_stats(self) -> Dict[str, Any]:
        """Get order manager statistics."""
        return {
            'orders_placed': self.orders_placed,
            'orders_filled': self.orders_filled,
            'orders_canceled': self.orders_canceled,
            'active_orders': len(self.active_orders),
            'total_volume': float(self.total_volume),
            'total_fees': float(self.total_fees),
        }
