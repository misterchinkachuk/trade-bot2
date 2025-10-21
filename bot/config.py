"""
Configuration management for the trading bot.
Handles loading and validation of configuration from YAML files and environment variables.
"""

import os
import yaml
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, validator
from pathlib import Path


class DatabaseConfig(BaseModel):
    """Database configuration."""
    host: str = "localhost"
    port: int = 5432
    database: str = "trading_bot"
    username: str = "trading_bot"
    password: str = "secure_password"
    pool_size: int = 10
    max_overflow: int = 20


class RedisConfig(BaseModel):
    """Redis configuration."""
    host: str = "localhost"
    port: int = 6379
    database: int = 0
    password: Optional[str] = None
    max_connections: int = 10


class BinanceConfig(BaseModel):
    """Binance API configuration."""
    testnet: bool = True
    base_url: str = "https://testnet.binance.vision"
    ws_base_url: str = "wss://testnet.binance.vision/ws"
    api_key: Optional[str] = None
    api_secret: Optional[str] = None
    
    @validator('api_key', 'api_secret', pre=True)
    def load_from_env(cls, v, field):
        """Load API credentials from environment variables if not provided."""
        if v is None:
            env_var = f"BINANCE_{field.name.upper()}"
            return os.getenv(env_var)
        return v


class RiskConfig(BaseModel):
    """Risk management configuration."""
    max_leverage: float = 1.0
    position_limits: Dict[str, float] = Field(default_factory=dict)
    stop_loss_pct: float = 0.02
    take_profit_pct: float = 0.04


class StrategyParams(BaseModel):
    """Base strategy parameters."""
    enabled: bool = True
    params: Dict[str, Any] = Field(default_factory=dict)


class TradingConfig(BaseModel):
    """Trading configuration."""
    mode: str = "paper"  # paper, live, backtest
    base_currency: str = "USDT"
    symbols: List[str] = ["BTCUSDT", "ETHUSDT"]
    max_position_size: float = 10000
    max_daily_drawdown: float = 0.05
    max_consecutive_losses: int = 5


class BacktestConfig(BaseModel):
    """Backtesting configuration."""
    start_date: str = "2024-01-01"
    end_date: str = "2024-12-31"
    initial_capital: float = 10000
    commission: float = 0.001
    slippage: float = 0.0005


class DashboardConfig(BaseModel):
    """Dashboard configuration."""
    host: str = "0.0.0.0"
    port: int = 8000
    debug: bool = False
    secret_key: str = "your_secret_key_here"


class LoggingConfig(BaseModel):
    """Logging configuration."""
    level: str = "INFO"
    format: str = "json"
    file: str = "logs/trading_bot.log"
    max_size: str = "10MB"
    backup_count: int = 5


class MonitoringConfig(BaseModel):
    """Monitoring configuration."""
    prometheus_enabled: bool = True
    prometheus_port: int = 9090
    telegram_enabled: bool = False
    telegram_bot_token: Optional[str] = None
    telegram_chat_id: Optional[str] = None
    email_enabled: bool = False
    email_smtp_server: Optional[str] = None
    email_smtp_port: Optional[int] = None
    email_username: Optional[str] = None
    email_password: Optional[str] = None


class Config(BaseModel):
    """Main configuration class."""
    trading: TradingConfig
    binance: BinanceConfig
    database: DatabaseConfig
    redis: RedisConfig
    risk: RiskConfig
    strategies: Dict[str, StrategyParams]
    backtest: BacktestConfig
    dashboard: DashboardConfig
    logging: LoggingConfig
    monitoring: MonitoringConfig

    @classmethod
    def load_from_file(cls, config_path: str) -> "Config":
        """Load configuration from YAML file."""
        config_file = Path(config_path)
        if not config_file.exists():
            raise FileNotFoundError(f"Configuration file not found: {config_path}")
        
        with open(config_file, 'r') as f:
            config_data = yaml.safe_load(f)
        
        return cls(**config_data)

    @classmethod
    def load_from_env(cls) -> "Config":
        """Load configuration from environment variables."""
        return cls(
            trading=TradingConfig(
                mode=os.getenv("TRADING_MODE", "paper"),
                base_currency=os.getenv("TRADING_BASE_CURRENCY", "USDT"),
                symbols=os.getenv("TRADING_SYMBOLS", "BTCUSDT,ETHUSDT").split(","),
                max_position_size=float(os.getenv("TRADING_MAX_POSITION_SIZE", "10000")),
                max_daily_drawdown=float(os.getenv("TRADING_MAX_DAILY_DRAWDOWN", "0.05")),
                max_consecutive_losses=int(os.getenv("TRADING_MAX_CONSECUTIVE_LOSSES", "5")),
            ),
            binance=BinanceConfig(),
            database=DatabaseConfig(
                host=os.getenv("DB_HOST", "localhost"),
                port=int(os.getenv("DB_PORT", "5432")),
                database=os.getenv("DB_NAME", "trading_bot"),
                username=os.getenv("DB_USER", "trading_bot"),
                password=os.getenv("DB_PASSWORD", "secure_password"),
            ),
            redis=RedisConfig(
                host=os.getenv("REDIS_HOST", "localhost"),
                port=int(os.getenv("REDIS_PORT", "6379")),
                database=int(os.getenv("REDIS_DB", "0")),
                password=os.getenv("REDIS_PASSWORD"),
            ),
            risk=RiskConfig(
                max_leverage=float(os.getenv("RISK_MAX_LEVERAGE", "1.0")),
                stop_loss_pct=float(os.getenv("RISK_STOP_LOSS_PCT", "0.02")),
                take_profit_pct=float(os.getenv("RISK_TAKE_PROFIT_PCT", "0.04")),
            ),
            strategies={},
            backtest=BacktestConfig(),
            dashboard=DashboardConfig(),
            logging=LoggingConfig(),
            monitoring=MonitoringConfig(),
        )


def load_config(config_path: Optional[str] = None) -> Config:
    """
    Load configuration from file or environment variables.
    
    Args:
        config_path: Path to configuration file. If None, loads from environment.
    
    Returns:
        Loaded configuration object.
    """
    if config_path:
        return Config.load_from_file(config_path)
    else:
        return Config.load_from_env()
