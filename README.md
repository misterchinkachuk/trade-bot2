# 🤖 Binance Trading Bot

A production-ready algorithmic trading bot for Binance with professional dashboard and comprehensive risk management.

## 🚀 Quick Installation

### For Fresh Ubuntu 22.04 Server:

```bash
# Download and run the installation script
curl -sSL https://raw.githubusercontent.com/misterchinkachuk/trade-bot/main/install.sh | bash
```

### Manual Installation:

```bash
# Clone the repository
git clone https://github.com/misterchinkachuk/trade-bot.git
cd trade-bot

# Make script executable and run
chmod +x install.sh
sudo ./install.sh
```

## 📋 What Gets Installed

- ✅ **Python 3.11+** with virtual environment
- ✅ **Docker & Docker Compose** for database services
- ✅ **TA-Lib** for technical analysis
- ✅ **PostgreSQL** database container
- ✅ **Redis** cache container
- ✅ **All Python dependencies** automatically
- ✅ **Systemd service** for automatic startup
- ✅ **Complete configuration** with user settings

## 🎯 Usage

### Start the Bot
```bash
cd /opt/trading_bot
./start_bot.sh
```

### Access Dashboard
- **URL**: `http://your-server-ip:8000`
- **Health Check**: `http://your-server-ip:8000/health`

### Enable Automatic Startup
```bash
sudo systemctl enable trading-bot
sudo systemctl start trading-bot
```

## 🔧 Configuration

- **Main Config**: `/opt/trading_bot/config_local.yaml`
- **Logs**: `/opt/trading_bot/logs/trading_bot.log`
- **Project Directory**: `/opt/trading_bot`

## 🚨 Important Notes

### Before Live Trading:
1. **Configure API Credentials** - Add your Binance API keys
2. **Test in Paper Mode** - Always test strategies first
3. **Set Risk Limits** - Configure appropriate position sizes
4. **Monitor Performance** - Watch the bot's performance closely

### Security:
- Use trading-only API keys (no withdrawal permissions)
- Enable IP restrictions if possible
- Regularly rotate API keys
- Monitor bot activity

## 📊 Features

- **Real-time Trading** - WebSocket market data with REST API orders
- **Multiple Strategies** - Scalper, Market Maker, Pairs Arbitrage
- **Risk Management** - Position limits, drawdown controls, circuit breakers
- **Professional Dashboard** - Real-time monitoring and control
- **Backtesting** - Historical strategy testing
- **Monitoring** - Prometheus metrics and alerts

## ⚠️ Disclaimer

This software is for educational purposes only. Trading cryptocurrencies involves substantial risk. Always test thoroughly in paper mode before using real funds.

---

**Happy Trading! 🚀**