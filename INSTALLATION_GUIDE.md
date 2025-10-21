# Binance Trading Bot - Automated Installation Guide

This guide provides automated installation scripts for Ubuntu 22.04 LTS that handle all common issues and set up the trading bot properly.

## 🚀 Quick Installation

### Option 1: Automated Installation (Recommended)

```bash
# Make the script executable
chmod +x quick_install.sh

# Run the installation
./quick_install.sh
```

### Option 2: Full Installation with Advanced Configuration

```bash
# Make the script executable
chmod +x install.sh

# Run the full installation
sudo ./install.sh
```

## 📋 What the Scripts Do

### Quick Installation (`quick_install.sh`)
- ✅ Fixes apt_pkg errors
- ✅ Installs Python 3.11+ and dependencies
- ✅ Installs Docker and Docker Compose
- ✅ Installs TA-Lib from source
- ✅ Creates virtual environment
- ✅ Installs all Python packages
- ✅ Starts PostgreSQL and Redis containers
- ✅ Initializes database schema
- ✅ Creates proper configuration file
- ✅ Creates startup script

### Full Installation (`install.sh`)
- ✅ Everything from quick installation
- ✅ Creates systemd service
- ✅ Sets up proper permissions
- ✅ Configures monitoring and alerts
- ✅ Creates comprehensive configuration
- ✅ Tests installation
- ✅ Provides detailed setup information

## 🔧 Manual Installation Steps

If you prefer to install manually, follow these steps:

### 1. System Update
```bash
sudo apt update && sudo apt upgrade -y
sudo apt remove -y command-not-found 2>/dev/null || true
sudo apt update
sudo apt install -y command-not-found
```

### 2. Install Dependencies
```bash
sudo apt install -y curl wget git build-essential python3.11 python3.11-venv python3.11-dev python3-pip
sudo update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.11 1
```

### 3. Install Docker
```bash
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
sudo systemctl start docker
sudo systemctl enable docker
sudo usermod -aG docker $USER
```

### 4. Install TA-Lib
```bash
cd /tmp
wget http://prdownloads.sourceforge.net/ta-lib/ta-lib-0.4.0-src.tar.gz
tar -xzf ta-lib-0.4.0-src.tar.gz
cd ta-lib/
./configure --prefix=/usr
make
sudo make install
sudo ldconfig
```

### 5. Setup Python Environment
```bash
python3.11 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
pip install pyyaml python-dotenv
```

### 6. Start Database Services
```bash
docker run -d --name postgres \
  -e POSTGRES_DB=trading_bot \
  -e POSTGRES_USER=trading_bot \
  -e POSTGRES_PASSWORD=secure_password \
  -p 5432:5432 \
  postgres:15-alpine

docker run -d --name redis \
  -p 6379:6379 \
  redis:7-alpine

sleep 15
docker exec -i postgres psql -U trading_bot -d trading_bot < ops/init.sql
```

### 7. Create Configuration
```bash
cp config.yaml config_local.yaml
# Edit config_local.yaml with your settings
```

### 8. Test Installation
```bash
source venv/bin/activate
python run.py --mode paper --verbose
```

## 🎯 Usage After Installation

### Start the Bot
```bash
# Quick start
./start_bot.sh

# Or manually
source venv/bin/activate
python run.py --mode live --verbose
```

### Access Dashboard
- **URL**: `http://your-server-ip:8000`
- **Health Check**: `http://your-server-ip:8000/health`

### Check Status
```bash
# Check if containers are running
docker ps

# Check bot logs
tail -f logs/trading_bot.log

# Check database connection
docker exec postgres psql -U trading_bot -d trading_bot -c "SELECT 1;"
```

## 🔧 Configuration

### Key Configuration Files
- **Main Config**: `config_local.yaml`
- **Database Schema**: `ops/init.sql`
- **Docker Compose**: `docker-compose.yml`

### Important Settings
- **Trading Mode**: `paper` (safe) or `live` (real money)
- **Symbols**: Trading pairs (e.g., BTCUSDT, ETHUSDT)
- **Risk Limits**: Position sizes and stop losses
- **API Credentials**: Binance API key and secret

## 🚨 Security Considerations

### Before Live Trading
1. **Test in Paper Mode**: Always test strategies first
2. **Set Risk Limits**: Configure appropriate position sizes
3. **API Permissions**: Use trading-only API keys (no withdrawal)
4. **Monitor Closely**: Watch the bot's performance
5. **Backup Configuration**: Save your working configuration

### API Key Security
- Never commit API keys to version control
- Use environment variables for production
- Enable only necessary API permissions
- Regularly rotate API keys

## 🐛 Troubleshooting

### Common Issues

#### 1. Docker Service Won't Start
```bash
sudo systemctl unmask docker
sudo systemctl start docker
sudo systemctl enable docker
```

#### 2. TA-Lib Installation Fails
```bash
sudo apt install -y libta-lib-dev
# Or install from source (see manual steps above)
```

#### 3. Python Dependencies Missing
```bash
source venv/bin/activate
pip install -r requirements.txt
pip install pyyaml python-dotenv
```

#### 4. Database Connection Failed
```bash
docker ps  # Check if containers are running
docker logs postgres  # Check PostgreSQL logs
docker logs redis  # Check Redis logs
```

#### 5. Configuration Validation Error
```bash
# Check if config_local.yaml has correct structure
cat config_local.yaml
# Ensure 'redis' is a top-level field, not under 'database'
```

### Log Files
- **Bot Logs**: `logs/trading_bot.log`
- **Docker Logs**: `docker logs trading_bot`
- **System Logs**: `journalctl -u trading-bot`

## 📊 Monitoring

### Dashboard Features
- Real-time bot status
- Position tracking
- P&L monitoring
- Order history
- Market data

### Prometheus Metrics
- Trading metrics
- System performance
- Risk metrics
- Strategy performance

## 🔄 Updates and Maintenance

### Update the Bot
```bash
git pull origin main
source venv/bin/activate
pip install -r requirements.txt
```

### Backup Configuration
```bash
cp config_local.yaml config_backup.yaml
```

### Restart Services
```bash
# Restart bot
sudo systemctl restart trading-bot

# Restart databases
docker restart postgres redis
```

## 📞 Support

If you encounter issues:
1. Check the logs first
2. Verify all services are running
3. Test in paper mode before live trading
4. Review the configuration file
5. Check network connectivity

## ⚠️ Disclaimer

This software is for educational purposes only. Trading cryptocurrencies involves substantial risk. Always test thoroughly in paper mode before using real funds. Past performance is not indicative of future results.

---

**Happy Trading! 🚀**
