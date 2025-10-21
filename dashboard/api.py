"""
FastAPI backend for the trading bot dashboard.
Provides REST API endpoints for monitoring and control.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from decimal import Decimal

from fastapi import FastAPI, HTTPException, Depends, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
import uvicorn

from ..bot.engine import TradingEngine
from ..bot.config import Config


class DashboardAPI:
    """Dashboard API server."""
    
    def __init__(self, config: Config, engine: Optional[TradingEngine] = None):
        """Initialize dashboard API."""
        self.config = config
        self.engine = engine
        self.logger = logging.getLogger(__name__)
        
        # WebSocket connections
        self.websocket_connections: List[WebSocket] = []
        
        # Create FastAPI app
        self.app = FastAPI(
            title="Trading Bot Dashboard",
            description="Real-time monitoring and control for the trading bot",
            version="1.0.0"
        )
        
        # Setup CORS
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
        
        # Setup routes
        self._setup_routes()
    
    def _setup_routes(self) -> None:
        """Setup API routes."""
        
        @self.app.get("/")
        async def root():
            """Root endpoint."""
            return {"message": "Trading Bot Dashboard API", "version": "1.0.0"}
        
        @self.app.get("/health")
        async def health_check():
            """Health check endpoint."""
            return {
                "status": "healthy",
                "timestamp": datetime.utcnow().isoformat(),
                "engine_running": self.engine.is_running if self.engine else False
            }
        
        @self.app.get("/status")
        async def get_status():
            """Get bot status."""
            if not self.engine:
                raise HTTPException(status_code=503, detail="Engine not available")
            
            return self.engine.get_status()
        
        @self.app.get("/strategies")
        async def get_strategies():
            """Get strategy information."""
            if not self.engine:
                raise HTTPException(status_code=503, detail="Engine not available")
            
            strategies = {}
            for name, strategy in self.engine.strategies.items():
                strategies[name] = strategy.get_stats()
            
            return strategies
        
        @self.app.post("/strategies/{strategy_name}/enable")
        async def enable_strategy(strategy_name: str):
            """Enable a strategy."""
            if not self.engine:
                raise HTTPException(status_code=503, detail="Engine not available")
            
            success = await self.engine.enable_strategy(strategy_name)
            if not success:
                raise HTTPException(status_code=400, detail="Failed to enable strategy")
            
            return {"message": f"Strategy {strategy_name} enabled"}
        
        @self.app.post("/strategies/{strategy_name}/disable")
        async def disable_strategy(strategy_name: str):
            """Disable a strategy."""
            if not self.engine:
                raise HTTPException(status_code=503, detail="Engine not available")
            
            success = await self.engine.disable_strategy(strategy_name)
            if not success:
                raise HTTPException(status_code=400, detail="Failed to disable strategy")
            
            return {"message": f"Strategy {strategy_name} disabled"}
        
        @self.app.get("/positions")
        async def get_positions():
            """Get current positions."""
            if not self.engine:
                raise HTTPException(status_code=503, detail="Engine not available")
            
            if not self.engine.accounting_manager:
                return {}
            
            positions = await self.engine.accounting_manager.get_positions()
            return {symbol: {
                "symbol": pos.symbol,
                "side": pos.side.value,
                "size": float(pos.size),
                "entry_price": float(pos.entry_price),
                "mark_price": float(pos.mark_price),
                "unrealized_pnl": float(pos.unrealized_pnl),
                "realized_pnl": float(pos.realized_pnl),
                "leverage": float(pos.leverage)
            } for symbol, pos in positions.items()}
        
        @self.app.get("/orders")
        async def get_orders():
            """Get recent orders."""
            if not self.engine:
                raise HTTPException(status_code=503, detail="Engine not available")
            
            if not self.engine.order_manager:
                return []
            
            orders = await self.engine.order_manager.get_order_history(limit=100)
            return [{
                "symbol": order.symbol,
                "order_id": order.order_id,
                "side": order.side.value,
                "type": order.type.value,
                "quantity": float(order.quantity),
                "price": float(order.price) if order.price else None,
                "status": order.status.value,
                "executed_qty": float(order.executed_qty),
                "avg_price": float(order.avg_price) if order.avg_price else None,
                "created_at": order.created_at.isoformat(),
                "updated_at": order.updated_at.isoformat()
            } for order in orders]
        
        @self.app.get("/trades")
        async def get_trades():
            """Get recent trades."""
            if not self.engine:
                raise HTTPException(status_code=503, detail="Engine not available")
            
            if not self.engine.accounting_manager:
                return []
            
            trades = await self.engine.accounting_manager.get_trades(limit=100)
            return [{
                "symbol": trade.symbol,
                "order_id": trade.order_id,
                "trade_id": trade.trade_id,
                "side": trade.side.value,
                "quantity": float(trade.quantity),
                "price": float(trade.price),
                "commission": float(trade.commission),
                "commission_asset": trade.commission_asset,
                "timestamp": trade.timestamp.isoformat(),
                "is_maker": trade.is_maker
            } for trade in trades]
        
        @self.app.get("/pnl")
        async def get_pnl():
            """Get P&L information."""
            if not self.engine:
                raise HTTPException(status_code=503, detail="Engine not available")
            
            if not self.engine.accounting_manager:
                return {"total_pnl": 0, "daily_pnl": {}}
            
            total_pnl = await self.engine.accounting_manager.get_total_pnl()
            daily_pnl = await self.engine.accounting_manager.get_daily_pnl()
            
            return {
                "total_pnl": float(total_pnl),
                "daily_pnl": {symbol: float(pnl) for symbol, pnl in daily_pnl.items()}
            }
        
        @self.app.get("/market-data/{symbol}")
        async def get_market_data(symbol: str):
            """Get market data for a symbol."""
            if not self.engine:
                raise HTTPException(status_code=503, detail="Engine not available")
            
            if not self.engine.data_ingester:
                raise HTTPException(status_code=503, detail="Data ingester not available")
            
            # Get latest price
            latest_price = await self.engine.data_ingester.get_latest_price(symbol)
            if not latest_price:
                raise HTTPException(status_code=404, detail="Symbol not found")
            
            # Get orderbook
            orderbook = await self.engine.data_ingester.get_orderbook(symbol)
            
            # Get VWAP
            vwap = await self.engine.data_ingester.get_vwap(symbol)
            
            return {
                "symbol": symbol,
                "price": float(latest_price),
                "vwap": float(vwap) if vwap else None,
                "orderbook": {
                    "bids": [{"price": float(level["price"]), "quantity": float(level["quantity"])} 
                            for level in orderbook.bids[:10]] if orderbook else [],
                    "asks": [{"price": float(level["price"]), "quantity": float(level["quantity"])} 
                            for level in orderbook.asks[:10]] if orderbook else []
                } if orderbook else None
            }
        
        @self.app.get("/monitoring")
        async def get_monitoring():
            """Get monitoring information."""
            if not self.engine:
                raise HTTPException(status_code=503, detail="Engine not available")
            
            if not self.engine.monitoring_manager:
                return {}
            
            return self.engine.monitoring_manager.get_metrics()
        
        @self.app.websocket("/ws")
        async def websocket_endpoint(websocket: WebSocket):
            """WebSocket endpoint for real-time updates."""
            await websocket.accept()
            self.websocket_connections.append(websocket)
            
            try:
                while True:
                    # Send periodic updates
                    if self.engine:
                        status = self.engine.get_status()
                        await websocket.send_json({
                            "type": "status_update",
                            "data": status,
                            "timestamp": datetime.utcnow().isoformat()
                        })
                    
                    await asyncio.sleep(1)  # Send updates every second
                    
            except WebSocketDisconnect:
                self.websocket_connections.remove(websocket)
    
    async def broadcast_update(self, data: Dict[str, Any]) -> None:
        """Broadcast update to all WebSocket connections."""
        if not self.websocket_connections:
            return
        
        message = {
            "type": "update",
            "data": data,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        # Send to all connected clients
        disconnected = []
        for websocket in self.websocket_connections:
            try:
                await websocket.send_json(message)
            except:
                disconnected.append(websocket)
        
        # Remove disconnected clients
        for websocket in disconnected:
            self.websocket_connections.remove(websocket)
    
    def run(self, host: str = "0.0.0.0", port: int = 8000) -> None:
        """Run the dashboard server."""
        uvicorn.run(
            self.app,
            host=host,
            port=port,
            log_level="info"
        )


def create_dashboard_app(config: Config, engine: Optional[TradingEngine] = None) -> FastAPI:
    """Create dashboard FastAPI app."""
    dashboard = DashboardAPI(config, engine)
    return dashboard.app


if __name__ == "__main__":
    # This would be run as a separate service
    import sys
    from pathlib import Path
    
    # Add parent directory to path
    sys.path.append(str(Path(__file__).parent.parent))
    
    from bot.config import load_config
    
    # Load config
    config = load_config()
    
    # Create dashboard
    dashboard = DashboardAPI(config)
    
    # Run server
    dashboard.run(
        host=config.dashboard.host,
        port=config.dashboard.port
    )
