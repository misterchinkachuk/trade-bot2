# 🚀 Fresh Server Installation Guide

This guide provides automated installation scripts for setting up the Binance Trading Bot on a fresh Ubuntu 22.04 LTS server.

## 📋 Quick Installation Options

### Option 1: One-Command Installation (Recommended)
```bash
# Download and run the complete installation
curl -sSL https://raw.githubusercontent.com/misterchinkachuk/trade-bot/main/download_and_install.sh | bash
```

### Option 2: Manual Download and Install
```bash
# Download the installation script
curl -o fresh_install.sh https://raw.githubusercontent.com/misterchinkachuk/trade-bot/main/fresh_install.sh

# Make it executable and run
chmod +x fresh_install.sh
./fresh_install.sh
```

### Option 3: Full Installation with Advanced Features
```bash
# Download the full installation script
curl -o install.sh https://raw.githubusercontent.com/misterchinkachuk/trade-bot/main/install.sh

# Make it executable and run
chmod +x install.sh
sudo ./install.sh
```

## 🎯 What Gets Installed

### System Requirements
- **OS**: Ubuntu 22.04 LTS
- **RAM**: 4GB+ (8GB+ recommended)
- **Storage**: 10GB+ free space
- **Network**: Stable internet connection

### Software Installed
- ✅ **Python 3.11+** with virtual environment
- ✅ **Docker & Docker Compose** for database services
- ✅ **TA-Lib** for technical analysis
- ✅ **PostgreSQL** database container
- ✅ **Redis** cache container
- ✅ **All Python dependencies** from requirements.txt
- ✅ **Systemd service** for automatic startup
- ✅ **Configuration files** with user settings

## 🔧 Installation Process

### During Installation, You'll Be Asked For:

1. **Git Repository URL** (default: https://github.com/misterchinkachuk/trade-bot.git)
2. **Server IP Address** (for dashboard access)
3. **Telegram Bot Token** (optional, for alerts)
4. **Telegram Chat ID** (optional, for alerts)
5. **Database Password** (default: secure_password)
6. **Trading Symbols** (default: BTCUSDT,ETHUSDT)

### What Happens During Installation:

1. **System Update** - Updates Ubuntu packages
2. **Dependency Installation** - Installs Python, Docker, build tools
3. **Repository Cloning** - Downloads the trading bot code
4. **Python Environment** - Creates virtual environment and installs packages
5. **Database Setup** - Starts PostgreSQL and Redis containers
6. **Configuration** - Creates config_local.yaml with your settings
7. **Service Setup** - Creates systemd service for automatic startup
8. **Testing** - Tests the installation

## 🚀 After Installation

### Start the Bot
```bash
# Navigate to the project directory
cd /opt/trading_bot

# Start the bot
./start_bot.sh

# Or manually
source venv/bin/activate
python run.py --mode live --verbose
```

### Access Dashboard
- **URL**: `http://your-server-ip:8000`
- **Health Check**: `http://your-server-ip:8000/health`

### Enable Automatic Startup
```bash
# Enable systemd service
sudo systemctl enable trading-bot
sudo systemctl start trading-bot

# Check status
sudo systemctl status trading-bot
```

## 🔧 Configuration

### Main Configuration File
- **Location**: `/opt/trading_bot/config_local.yaml`
- **Contains**: All bot settings, database config, trading parameters

### Key Settings to Review:
- **Trading Mode**: `paper` (safe) or `live` (real money)
- **Symbols**: Trading pairs (e.g., BTCUSDT, ETHUSDT)
- **Risk Limits**: Position sizes and stop losses
- **API Credentials**: Binance API key and secret

### Database Configuration
- **PostgreSQL**: `localhost:5432`
- **Redis**: `localhost:6379`
- **Database**: `trading_bot`
- **User**: `trading_bot`

## 🚨 Security Setup

### Before Live Trading

1. **Configure API Credentials**
   ```bash
   # Edit the configuration file
   nano /opt/trading_bot/config_local.yaml
   
   # Add your Binance API credentials
   binance:
     api_key: "your_api_key_here"
     api_secret: "your_api_secret_here"
   ```

2. **Test in Paper Mode First**
   ```bash
   cd /opt/trading_bot
   source venv/bin/activate
   python run.py --mode paper --verbose
   ```

3. **Set Risk Limits**
   - Review position sizes in config_local.yaml
   - Set appropriate stop losses
   - Configure maximum daily drawdown

4. **API Key Security**
   - Use trading-only permissions (no withdrawal)
   - Enable IP restrictions if possible
   - Regularly rotate API keys

## 📊 Monitoring

### Dashboard Features
- Real-time bot status
- Position tracking
- P&L monitoring
- Order history
- Market data visualization

### Log Files
- **Bot Logs**: `/opt/trading_bot/logs/trading_bot.log`
- **Docker Logs**: `docker logs postgres`, `docker logs redis`
- **System Logs**: `journalctl -u trading-bot`

### Health Checks
```bash
# Check bot status
curl http://localhost:8000/health

# Check database
docker exec postgres psql -U trading_bot -d trading_bot -c "SELECT 1;"

# Check Redis
docker exec redis redis-cli ping
```

## 🔄 Maintenance

### Update the Bot
```bash
cd /opt/trading_bot
git pull origin main
source venv/bin/activate
pip install -r requirements.txt
```

### Restart Services
```bash
# Restart bot
sudo systemctl restart trading-bot

# Restart databases
docker restart postgres redis
```

### Backup Configuration
```bash
cp /opt/trading_bot/config_local.yaml /opt/trading_bot/config_backup_$(date +%Y%m%d).yaml
```

## 🐛 Troubleshooting

### Common Issues

#### 1. Installation Fails
```bash
# Check system requirements
free -h  # Check RAM
df -h    # Check disk space
uname -r # Check kernel version
```

#### 2. Docker Issues
```bash
# Check Docker status
sudo systemctl status docker
sudo systemctl start docker
```

#### 3. Python Dependencies
```bash
cd /opt/trading_bot
source venv/bin/activate
pip install -r requirements.txt
```

#### 4. Database Connection
```bash
# Check containers
docker ps
docker logs postgres
docker logs redis
```

#### 5. Configuration Issues
```bash
# Validate configuration
cd /opt/trading_bot
source venv/bin/activate
python -c "from bot.config import load_config; print('Config OK')"
```

### Log Analysis
```bash
# View bot logs
tail -f /opt/trading_bot/logs/trading_bot.log

# View system logs
journalctl -u trading-bot -f

# View Docker logs
docker logs -f postgres
docker logs -f redis
```

## 📞 Support

### If You Encounter Issues:

1. **Check Logs**: `tail -f /opt/trading_bot/logs/trading_bot.log`
2. **Verify Services**: `docker ps`, `sudo systemctl status trading-bot`
3. **Test Configuration**: `python run.py --mode paper --verbose`
4. **Check Network**: `curl http://localhost:8000/health`

### Useful Commands:
```bash
# Check bot status
sudo systemctl status trading-bot

# View logs
journalctl -u trading-bot -f

# Restart bot
sudo systemctl restart trading-bot

# Check database
docker exec postgres psql -U trading_bot -d trading_bot -c "SELECT 1;"
```

## ⚠️ Important Notes

### Before Live Trading:
- ✅ Test thoroughly in paper mode
- ✅ Configure API credentials securely
- ✅ Set appropriate risk limits
- ✅ Monitor the bot's performance
- ✅ Backup your configuration

### Security Best Practices:
- 🔒 Use trading-only API keys
- 🔒 Enable IP restrictions
- 🔒 Regularly rotate credentials
- 🔒 Monitor bot activity
- 🔒 Keep software updated

## 🎯 Quick Start Commands

```bash
# One-command installation
curl -sSL https://raw.githubusercontent.com/misterchinkachuk/trade-bot/main/download_and_install.sh | bash

# Start the bot
cd /opt/trading_bot
./start_bot.sh

# Access dashboard
# Open http://your-server-ip:8000 in your browser
```

---

**Happy Trading! 🚀**

## 📚 Additional Resources

- [Installation Guide](INSTALLATION_GUIDE.md) - Detailed manual installation
- [Configuration Reference](config.yaml) - Configuration options
- [Docker Compose](docker-compose.yml) - Container orchestration
- [Systemd Service](ops/trading-bot.service) - Service management
