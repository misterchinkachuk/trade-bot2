#!/bin/bash

# Quick Installation Script for Binance Trading Bot
# Run this script from the project directory

set -e

echo "=== Binance Trading Bot Quick Installation ==="

# Get user input
read -p "Enter your server IP (for dashboard): " SERVER_IP
read -p "Enter Telegram bot token (optional): " TELEGRAM_BOT_TOKEN
read -p "Enter Telegram chat ID (optional): " TELEGRAM_CHAT_ID
read -p "Enter database password (default: secure_password): " DB_PASSWORD
DB_PASSWORD=${DB_PASSWORD:-secure_password}

# Generate secret key
DASHBOARD_SECRET=$(openssl rand -hex 32 2>/dev/null || echo "your_secret_key_here")

echo "Installing dependencies..."

# Fix apt issues
apt remove -y command-not-found 2>/dev/null || true
apt update
apt install -y curl wget git build-essential python3.11 python3.11-venv python3.11-dev python3-pip

# Install Docker
apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
systemctl start docker
systemctl enable docker
usermod -aG docker $USER

# Install TA-Lib
cd /tmp
wget -q http://prdownloads.sourceforge.net/ta-lib/ta-lib-0.4.0-src.tar.gz
tar -xzf ta-lib-0.4.0-src.tar.gz
cd ta-lib/
./configure --prefix=/usr
make
make install
ldconfig
cd /

# Setup Python environment
python3.11 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
pip install pyyaml python-dotenv

# Start databases
docker stop postgres redis 2>/dev/null || true
docker rm postgres redis 2>/dev/null || true

docker run -d --name postgres \
  -e POSTGRES_DB=trading_bot \
  -e POSTGRES_USER=trading_bot \
  -e POSTGRES_PASSWORD="$DB_PASSWORD" \
  -p 5432:5432 \
  postgres:15-alpine

docker run -d --name redis \
  -p 6379:6379 \
  redis:7-alpine

sleep 15

# Initialize database
docker exec -i postgres psql -U trading_bot -d trading_bot < ops/init.sql

# Create configuration
cat > config_local.yaml << EOF
trading:
  mode: "paper"
  base_currency: "USDT"
  symbols: ["BTCUSDT", "ETHUSDT"]
  max_position_size: 10000
  max_daily_drawdown: 0.05
  max_consecutive_losses: 5

binance:
  testnet: false
  base_url: "https://api.binance.com"
  ws_base_url: "wss://stream.binance.com:9443/ws"

database:
  postgres:
    host: "localhost"
    port: 5432
    database: "trading_bot"
    username: "trading_bot"
    password: "$DB_PASSWORD"
    pool_size: 10
    max_overflow: 20

redis:
  host: "localhost"
  port: 6379
  database: 0
  password: null
  max_connections: 10

risk:
  max_leverage: 1.0
  position_limits:
    BTCUSDT: 0.1
    ETHUSDT: 0.1
  stop_loss_pct: 0.02
  take_profit_pct: 0.04

strategies:
  scalper:
    enabled: true
    params:
      ema_short: 5
      ema_long: 20
      obi_threshold: 0.25
      risk_fraction: 0.01
      stop_distance: 0.005

backtest:
  start_date: "2024-01-01"
  end_date: "2024-12-31"
  initial_capital: 10000
  commission: 0.001
  slippage: 0.0005

dashboard:
  host: "0.0.0.0"
  port: 8000
  debug: false
  secret_key: "$DASHBOARD_SECRET"

logging:
  level: "INFO"
  format: "json"
  file: "logs/trading_bot.log"
  max_size: "10MB"
  backup_count: 5

monitoring:
  prometheus:
    enabled: true
    port: 9090
  alerts:
    telegram:
      enabled: $([ -n "$TELEGRAM_BOT_TOKEN" ] && echo "true" || echo "false")
      bot_token: "$TELEGRAM_BOT_TOKEN"
      chat_id: "$TELEGRAM_CHAT_ID"
    email:
      enabled: false
      smtp_server: "smtp.gmail.com"
      smtp_port: 587
      username: "your_email@gmail.com"
      password: "your_app_password"
EOF

# Create startup script
cat > start_bot.sh << 'EOF'
#!/bin/bash
source venv/bin/activate
echo "Starting Binance Trading Bot..."
echo "Dashboard: http://$(curl -s ifconfig.me):8000"
python run.py --mode live --verbose
EOF

chmod +x start_bot.sh

echo "=== Installation Complete! ==="
echo "Dashboard: http://$SERVER_IP:8000"
echo "To start: ./start_bot.sh"
echo "Or: source venv/bin/activate && python run.py --mode live --verbose"
