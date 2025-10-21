# 🚀 Binance Trading Bot - Automated Installation

This repository contains automated installation scripts that handle all common issues and set up the trading bot properly on Ubuntu 22.04 LTS.

## 📋 Installation Options

### Option 1: Complete Fix and Install (Recommended)
```bash
# Run the comprehensive installation script
chmod +x fix_and_install.sh
./fix_and_install.sh
```

### Option 2: Quick Installation
```bash
# Run the quick installation script
chmod +x quick_install.sh
./quick_install.sh
```

### Option 3: Full Installation with Advanced Features
```bash
# Run the full installation script
chmod +x install.sh
sudo ./install.sh
```

## 🎯 What Gets Fixed Automatically

- ✅ **apt_pkg errors** - Fixes command-not-found package issues
- ✅ **Docker service issues** - Handles masked services and conflicts
- ✅ **TA-Lib installation** - Installs from source with proper dependencies
- ✅ **Pydantic version conflicts** - Uses compatible versions
- ✅ **Configuration structure** - Creates proper YAML with correct field structure
- ✅ **Database setup** - Starts PostgreSQL and Redis containers
- ✅ **Python dependencies** - Installs all required packages
- ✅ **Virtual environment** - Sets up isolated Python environment

## 🚀 Quick Start After Installation

### Start the Bot
```bash
# Option 1: Use the startup script
./start_bot.sh

# Option 2: Use the launcher (interactive menu)
./launcher.sh

# Option 3: Manual start
source venv/bin/activate
python run.py --mode live --verbose
```

### Access Dashboard
- **URL**: `http://your-server-ip:8000`
- **Health Check**: `http://your-server-ip:8000/health`

## 🔧 Configuration

The installation scripts will ask for:
- **Server IP** (for dashboard access)
- **Telegram Bot Token** (optional, for alerts)
- **Telegram Chat ID** (optional, for alerts)
- **Database Password** (default: secure_password)
- **Trading Symbols** (default: BTCUSDT,ETHUSDT)

## 📁 Files Created

After installation, you'll have:
- `config_local.yaml` - Main configuration file
- `start_bot.sh` - Quick start script
- `launcher.sh` - Interactive launcher
- `venv/` - Python virtual environment
- `logs/` - Log files directory

## 🐛 Troubleshooting

### If Installation Fails
1. **Check system requirements**: Ubuntu 22.04 LTS, 4GB+ RAM, 10GB+ disk space
2. **Run as root**: `sudo ./fix_and_install.sh`
3. **Check internet connection**: Required for downloading dependencies
4. **Verify Docker**: `docker --version`

### Common Issues Fixed
- **Docker service masked**: Automatically unmasked and started
- **TA-Lib compilation fails**: Installed from source with proper dependencies
- **Python dependencies missing**: All packages installed automatically
- **Configuration validation errors**: Proper YAML structure created
- **Database connection failed**: Containers started and initialized

### Manual Fixes
```bash
# Fix Docker if needed
sudo systemctl unmask docker
sudo systemctl start docker
sudo systemctl enable docker

# Fix TA-Lib if needed
sudo apt install -y libta-lib-dev
pip install --no-cache-dir TA-Lib

# Fix Python dependencies
source venv/bin/activate
pip install -r requirements.txt
pip install pyyaml python-dotenv
```

## 🔒 Security Notes

### Before Live Trading
1. **Test in Paper Mode**: Always test strategies first
2. **Configure API Keys**: Set up Binance API credentials
3. **Set Risk Limits**: Configure appropriate position sizes
4. **Monitor Closely**: Watch the bot's performance
5. **Backup Configuration**: Save your working settings

### API Key Security
- Never commit API keys to version control
- Use environment variables for production
- Enable only trading permissions (no withdrawal)
- Regularly rotate API keys

## 📊 Monitoring

### Dashboard Features
- Real-time bot status
- Position tracking
- P&L monitoring
- Order history
- Market data visualization

### Log Files
- **Bot Logs**: `logs/trading_bot.log`
- **Docker Logs**: `docker logs postgres`, `docker logs redis`
- **System Logs**: `journalctl -u trading-bot`

## 🔄 Maintenance

### Update the Bot
```bash
git pull origin main
source venv/bin/activate
pip install -r requirements.txt
```

### Restart Services
```bash
# Restart bot
./launcher.sh  # Select option 7

# Restart databases
docker restart postgres redis
```

### Backup Configuration
```bash
cp config_local.yaml config_backup_$(date +%Y%m%d).yaml
```

## 📞 Support

If you encounter issues:
1. Check the logs: `tail -f logs/trading_bot.log`
2. Verify services: `docker ps`
3. Test configuration: `python run.py --mode paper --verbose`
4. Check network: `curl http://localhost:8000/health`

## ⚠️ Disclaimer

This software is for educational purposes only. Trading cryptocurrencies involves substantial risk. Always test thoroughly in paper mode before using real funds. Past performance is not indicative of future results.

---

**Happy Trading! 🚀**

## 📚 Additional Resources

- [Installation Guide](INSTALLATION_GUIDE.md) - Detailed manual installation
- [Configuration Reference](config.yaml) - Configuration options
- [Docker Compose](docker-compose.yml) - Container orchestration
- [Systemd Service](ops/trading-bot.service) - Service management
