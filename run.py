#!/usr/bin/env python3
"""
Main entry point for the Binance trading bot.
Supports paper trading, live trading, and backtesting modes.
"""

import asyncio
import argparse
import logging
import sys
import os
from pathlib import Path
from typing import Optional

from bot.config import load_config
from bot.engine import TradingEngine
from bot.backtest import Backtester
from bot.strategies import ScalperStrategy, MarketMakerStrategy, PairsArbitrageStrategy


def setup_logging(config) -> None:
    """Setup logging configuration."""
    log_level = getattr(logging, config.logging.level.upper(), logging.INFO)
    
    # Create logs directory if it doesn't exist
    log_file = Path(config.logging.file)
    log_file.parent.mkdir(parents=True, exist_ok=True)
    
    # Configure logging
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler(sys.stdout)
        ]
    )


def get_api_credentials() -> tuple[str, str]:
    """Get API credentials from user input."""
    print("Binance API Credentials Required")
    print("=" * 40)
    
    api_key = input("Enter your Binance API Key: ").strip()
    if not api_key:
        raise ValueError("API Key is required")
    
    api_secret = input("Enter your Binance API Secret: ").strip()
    if not api_secret:
        raise ValueError("API Secret is required")
    
    print("\nWARNING: Never share your API credentials with anyone!")
    print("Make sure to use API keys with trading permissions only (not withdrawal)")
    
    return api_key, api_secret


async def run_paper_trading(config) -> None:
    """Run in paper trading mode."""
    print("Starting Paper Trading Mode")
    print("=" * 40)
    
    # Create engine
    engine = TradingEngine(config)
    
    try:
        # Initialize engine
        await engine.initialize()
        
        # Start engine
        await engine.run()
        
    except KeyboardInterrupt:
        print("\nShutting down paper trading...")
    except Exception as e:
        print(f"Error in paper trading: {e}")
        raise
    finally:
        await engine.shutdown()


async def run_live_trading(config) -> None:
    """Run in live trading mode."""
    print("Starting Live Trading Mode")
    print("=" * 40)
    
    # Get API credentials
    api_key, api_secret = get_api_credentials()
    
    # Update config with credentials
    config.binance.api_key = api_key
    config.binance.api_secret = api_secret
    config.trading.mode = "live"
    
    # Create engine
    engine = TradingEngine(config)
    
    try:
        # Initialize engine
        await engine.initialize()
        
        # Start engine
        await engine.run()
        
    except KeyboardInterrupt:
        print("\nShutting down live trading...")
    except Exception as e:
        print(f"Error in live trading: {e}")
        raise
    finally:
        await engine.shutdown()


async def run_backtest(config) -> None:
    """Run backtest mode."""
    print("Starting Backtest Mode")
    print("=" * 40)
    
    # Load historical data (this would typically load from database or files)
    historical_data = await load_historical_data(config)
    
    if not historical_data:
        print("No historical data found. Please ensure data is available.")
        return
    
    # Create backtester
    backtester = Backtester(config)
    
    # Test each strategy
    strategies = [
        ScalperStrategy("scalper", config.strategies.get('scalper', {}).params, config.trading.symbols),
        MarketMakerStrategy("market_maker", config.strategies.get('market_maker', {}).params, config.trading.symbols),
        PairsArbitrageStrategy("pairs_arbitrage", config.strategies.get('pairs_arbitrage', {}).params, config.trading.symbols)
    ]
    
    results = []
    
    for strategy in strategies:
        try:
            print(f"\nBacktesting strategy: {strategy.name}")
            print("-" * 30)
            
            # Run backtest
            result = await backtester.run_backtest(strategy, historical_data, config.trading.symbols)
            results.append(result)
            
            # Print results
            print(f"Strategy: {result.strategy_name}")
            print(f"Period: {result.start_date} to {result.end_date}")
            print(f"Initial Capital: ${result.initial_capital:,.2f}")
            print(f"Final Capital: ${result.final_capital:,.2f}")
            print(f"Total Return: {result.total_return_pct:.2%}")
            print(f"Max Drawdown: {result.max_drawdown_pct:.2%}")
            print(f"Sharpe Ratio: {result.sharpe_ratio:.2f}")
            print(f"Win Rate: {result.win_rate:.2%}")
            print(f"Total Trades: {result.total_trades}")
            print(f"Profit Factor: {result.profit_factor:.2f}")
            
        except Exception as e:
            print(f"Error backtesting {strategy.name}: {e}")
            continue
    
    # Print summary
    if results:
        print("\nBacktest Summary")
        print("=" * 40)
        
        best_strategy = max(results, key=lambda r: r.total_return_pct)
        print(f"Best Strategy: {best_strategy.strategy_name} ({best_strategy.total_return_pct:.2%})")
        
        worst_strategy = min(results, key=lambda r: r.total_return_pct)
        print(f"Worst Strategy: {worst_strategy.strategy_name} ({worst_strategy.total_return_pct:.2%})")
        
        avg_return = sum(r.total_return_pct for r in results) / len(results)
        print(f"Average Return: {avg_return:.2%}")


async def load_historical_data(config) -> dict:
    """Load historical data for backtesting."""
    # This is a placeholder - in practice, you'd load from database or files
    print("Loading historical data...")
    
    # For now, return empty dict
    # In a real implementation, you'd load actual historical data
    return {}


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Binance Trading Bot")
    parser.add_argument(
        "--mode",
        choices=["paper", "live", "backtest"],
        required=True,
        help="Trading mode"
    )
    parser.add_argument(
        "--config",
        default="config.yaml",
        help="Configuration file path"
    )
    parser.add_argument(
        "--symbols",
        nargs="+",
        help="Trading symbols (overrides config)"
    )
    parser.add_argument(
        "--strategy",
        help="Specific strategy to run (overrides config)"
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose logging"
    )
    
    args = parser.parse_args()
    
    try:
        # Load configuration
        config = load_config(args.config)
        
        # Override config with command line arguments
        if args.symbols:
            config.trading.symbols = args.symbols
        
        if args.verbose:
            config.logging.level = "DEBUG"
        
        # Setup logging
        setup_logging(config)
        
        # Run appropriate mode
        if args.mode == "paper":
            asyncio.run(run_paper_trading(config))
        elif args.mode == "live":
            asyncio.run(run_live_trading(config))
        elif args.mode == "backtest":
            asyncio.run(run_backtest(config))
        
    except KeyboardInterrupt:
        print("\nExiting...")
        sys.exit(0)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
