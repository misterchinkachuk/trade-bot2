# 🤖 Binance Trading Bot

A production-ready, fully-auditable, and secure algorithmic trading system for Binance with a professional dashboard. The bot features modular architecture, comprehensive risk management, and real-time market data processing.

## ✨ Features

- **Modular Architecture**: Pluggable strategies, execution engine, risk manager, data layer, and backtester
- **Real-time Trading**: WebSocket market data streams with REST API for orders
- **Risk Management**: Position limits, drawdown controls, and circuit breakers
- **Multiple Strategies**: Scalper, Market Maker, and Pairs Arbitrage strategies
- **Backtesting**: Deterministic backtester with realistic latency and slippage simulation
- **Professional Dashboard**: Real-time monitoring and control interface
- **Production Ready**: Docker deployment, systemd service, and comprehensive monitoring
- **Security**: Encrypted API key storage, rate limiting, and audit trails

## 🏗️ Architecture

```
bot/
├── engine.py              # Main trading engine
├── config.py              # Configuration management
├── types.py               # Type definitions
├── connectors/            # Binance API connectors
│   ├── binance_ws.py     # WebSocket client
│   ├── binance_rest.py   # REST API client
│   └── rate_limiter.py   # Rate limiting
├── strategies/            # Trading strategies
│   ├── base.py           # Base strategy class
│   ├── scalper.py        # Scalper strategy
│   ├── market_maker.py   # Market maker strategy
│   └── pairs_arbitrage.py # Pairs arbitrage strategy
├── execution.py           # Order management
├── risk.py               # Risk management
├── accounting.py         # P&L tracking
├── monitoring.py         # Monitoring and alerts
├── data_ingest.py        # Market data processing
└── backtest.py           # Backtesting engine

dashboard/
├── api.py                # FastAPI backend
└── static/               # Frontend assets
    └── index.html        # Dashboard UI

ops/
├── docker-compose.yml    # Docker deployment
├── init.sql             # Database schema
├── prometheus.yml       # Monitoring config
└── trading-bot.service  # Systemd service
```

## 🚀 Quick Start

### Prerequisites

- Python 3.11+
- Docker and Docker Compose
- Binance API credentials (for live trading)

### Installation

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd binance-trading-bot
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure the bot**
   ```bash
   cp config.yaml config_local.yaml
   # Edit config_local.yaml with your settings
   ```

4. **Start with Docker Compose**
   ```bash
   docker-compose up -d
   ```

5. **Access the dashboard**
   - Open http://localhost:8000 in your browser
   - Monitor bot status, positions, and performance

### Manual Setup

1. **Start PostgreSQL and Redis**
   ```bash
   # Using Docker
   docker run -d --name postgres -e POSTGRES_PASSWORD=secure_password -p 5432:5432 postgres:15
   docker run -d --name redis -p 6379:6379 redis:7
   ```

2. **Initialize database**
   ```bash
   psql -h localhost -U postgres -f ops/init.sql
   ```

3. **Run the bot**
   ```bash
   # Paper trading mode
   python run.py --mode paper

   # Live trading mode (requires API credentials)
   python run.py --mode live

   # Backtest mode
   python run.py --mode backtest
   ```

## 📊 Trading Strategies

### 1. Scalper Strategy
- **Purpose**: High-frequency trading using orderbook imbalance
- **Indicators**: EMA crossover, orderbook imbalance (OBI)
- **Logic**: Buy when OBI > threshold and EMA_short > EMA_long
- **Risk Management**: Position sizing based on risk fraction and stop distance

### 2. Market Maker Strategy
- **Purpose**: Provide liquidity with continuous limit orders
- **Logic**: Place symmetric orders around fair price with inventory skewing
- **Features**: Dynamic spread adjustment, volatility-based sizing
- **Risk Management**: Maximum inventory limits, spread controls

### 3. Pairs Arbitrage Strategy
- **Purpose**: Statistical arbitrage between correlated assets
- **Logic**: Cointegration model with mean reversion signals
- **Features**: Z-score based entry/exit, Kelly position sizing
- **Risk Management**: Maximum position ratios, rebalancing intervals

## 🔧 Configuration

### Environment Variables

```bash
# Trading mode
TRADING_MODE=paper  # paper, live, backtest

# Binance API (for live trading)
BINANCE_API_KEY=your_api_key
BINANCE_API_SECRET=your_api_secret

# Database
DB_HOST=localhost
DB_PORT=5432
DB_NAME=trading_bot
DB_USER=trading_bot
DB_PASSWORD=secure_password

# Redis
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0
```

### Configuration File

Edit `config.yaml` to customize:

- **Trading parameters**: Symbols, position limits, risk settings
- **Strategy settings**: Parameters for each strategy
- **Database configuration**: Connection settings
- **Monitoring**: Alert settings, metrics collection

## 🛡️ Security

### API Key Management

- **Never hardcode API keys** in the source code
- **Use environment variables** or encrypted storage
- **Enable only trading permissions** (not withdrawal)
- **Use testnet** for development and testing

### Security Checklist

- [ ] API keys stored securely (environment variables)
- [ ] HTTPS enabled for dashboard
- [ ] CORS and CSRF protections enabled
- [ ] Rate limiting implemented
- [ ] Audit trail for all actions
- [ ] Regular security updates

## 📈 Monitoring

### Dashboard Features

- **Real-time Status**: Engine status, active strategies, P&L
- **Position Management**: Current positions, unrealized P&L
- **Order Tracking**: Recent orders and fills
- **Market Data**: Live prices, orderbook, VWAP
- **Performance Charts**: P&L over time

### Prometheus Metrics

- **Trading Metrics**: Orders, fills, P&L
- **System Metrics**: Latency, throughput, error rates
- **Risk Metrics**: Position sizes, drawdowns
- **Strategy Metrics**: Signal generation, performance

### Alerts

- **Risk Alerts**: Drawdown breaches, position limits
- **System Alerts**: Connection failures, high latency
- **Performance Alerts**: Strategy performance degradation

## 🧪 Testing

### Backtesting

```bash
# Run backtest for all strategies
python run.py --mode backtest

# Run specific strategy
python run.py --mode backtest --strategy scalper

# Run with specific symbols
python run.py --mode backtest --symbols BTCUSDT ETHUSDT
```

### Paper Trading

```bash
# Start paper trading
python run.py --mode paper

# Monitor via dashboard
open http://localhost:8000
```

### Live Trading

```bash
# Start live trading (requires API credentials)
python run.py --mode live
```

## 🚀 Deployment

### Docker Deployment

```bash
# Build and start all services
docker-compose up -d

# View logs
docker-compose logs -f trading_bot

# Stop services
docker-compose down
```

### Systemd Service

```bash
# Copy service file
sudo cp ops/trading-bot.service /etc/systemd/system/

# Enable and start service
sudo systemctl enable trading_bot
sudo systemctl start trading_bot

# View logs
sudo journalctl -u trading_bot -f
```

## 📚 API Reference

### REST API Endpoints

- `GET /health` - Health check
- `GET /status` - Bot status
- `GET /strategies` - Strategy information
- `POST /strategies/{name}/enable` - Enable strategy
- `POST /strategies/{name}/disable` - Disable strategy
- `GET /positions` - Current positions
- `GET /orders` - Recent orders
- `GET /trades` - Recent trades
- `GET /pnl` - P&L information
- `GET /market-data/{symbol}` - Market data
- `GET /monitoring` - Monitoring metrics

### WebSocket

- `ws://localhost:8000/ws` - Real-time updates

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## ⚠️ Disclaimer

This software is for educational and research purposes only. Trading cryptocurrencies involves substantial risk of loss and is not suitable for all investors. Past performance is not indicative of future results. Always test thoroughly in paper trading mode before using real funds.

## 🆘 Support

- **Documentation**: Check this README and code comments
- **Issues**: Create an issue on GitHub
- **Discussions**: Use GitHub Discussions for questions

## 🔄 Changelog

### v1.0.0
- Initial release
- Core trading engine
- Three trading strategies
- Professional dashboard
- Docker deployment
- Comprehensive monitoring
