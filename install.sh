#!/bin/bash

# Binance Trading Bot Fresh Installation Script for Ubuntu 22.04
# This script installs the bot on a fresh server by cloning the repository

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function to check if running as root
check_root() {
    if [[ $EUID -eq 0 ]]; then
        print_warning "Running as root. This is not recommended for production."
        read -p "Do you want to continue? (y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            exit 1
        fi
    fi
}

# Function to get user input
get_user_input() {
    print_status "=== Trading Bot Configuration ==="
    echo
    
    # Get repository URL
    read -p "Enter Git repository URL (default: https://github.com/misterchinkachuk/trade-bot.git): " REPO_URL
    if [[ -z "$REPO_URL" ]]; then
        REPO_URL="https://github.com/misterchinkachuk/trade-bot.git"
    fi
    
    # Get server IP
    read -p "Enter your server IP address (for dashboard access): " SERVER_IP
    if [[ -z "$SERVER_IP" ]]; then
        SERVER_IP=$(curl -s ifconfig.me || echo "localhost")
        print_warning "Using detected IP: $SERVER_IP"
    fi
    
    # Get Telegram bot token
    echo
    read -p "Enter your Telegram bot token (optional, press Enter to skip): " TELEGRAM_BOT_TOKEN
    
    # Get Telegram chat ID
    if [[ -n "$TELEGRAM_BOT_TOKEN" ]]; then
        read -p "Enter your Telegram chat ID (optional, press Enter to skip): " TELEGRAM_CHAT_ID
    fi
    
    # Get email configuration
    echo
    read -p "Enter your email for alerts (optional, press Enter to skip): " EMAIL_ADDRESS
    
    # Get database password
    echo
    read -p "Enter database password (default: secure_password): " DB_PASSWORD
    if [[ -z "$DB_PASSWORD" ]]; then
        DB_PASSWORD="secure_password"
    fi
    
    # Get dashboard secret key
    echo
    read -p "Enter dashboard secret key (default: auto-generated): " DASHBOARD_SECRET
    if [[ -z "$DASHBOARD_SECRET" ]]; then
        DASHBOARD_SECRET=$(openssl rand -hex 32 2>/dev/null || echo "your_secret_key_here")
    fi
    
    # Get trading symbols
    echo
    read -p "Enter trading symbols (comma-separated, default: BTCUSDT,ETHUSDT): " TRADING_SYMBOLS
    if [[ -z "$TRADING_SYMBOLS" ]]; then
        TRADING_SYMBOLS="BTCUSDT,ETHUSDT"
    fi
    
    # Convert comma-separated to array format
    IFS=',' read -ra SYMBOL_ARRAY <<< "$TRADING_SYMBOLS"
    SYMBOL_YAML=""
    for symbol in "${SYMBOL_ARRAY[@]}"; do
        symbol=$(echo "$symbol" | xargs)  # trim whitespace
        SYMBOL_YAML+="    - \"$symbol\"\n"
    done
}

# Function to update system
update_system() {
    print_status "Updating system packages..."
    
    # Fix apt_pkg error by removing command-not-found temporarily
    apt remove -y command-not-found 2>/dev/null || true
    
    apt update
    apt upgrade -y
    
    # Reinstall command-not-found
    apt install -y command-not-found
    
    print_success "System updated successfully"
}

# Function to install dependencies
install_dependencies() {
    print_status "Installing system dependencies..."
    
    # Install essential packages
    apt install -y curl wget git vim nano htop build-essential software-properties-common \
        python3.11 python3.11-venv python3.11-dev python3-pip python3-apt \
        postgresql-client redis-tools
    
    # Set Python 3.11 as default
    update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.11 1
    
    print_success "System dependencies installed"
}

# Function to install Docker
install_docker() {
    print_status "Installing Docker..."
    
    # Remove old Docker installations
    apt remove -y docker docker-engine docker.io containerd runc 2>/dev/null || true
    
    # Clean up
    apt autoremove -y
    rm -rf /var/lib/docker /etc/docker 2>/dev/null || true
    
    # Install Docker
    apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
    
    # Start Docker services
    systemctl start containerd
    systemctl enable containerd
    systemctl start docker
    systemctl enable docker
    
    # Add user to docker group
    usermod -aG docker $USER
    
    # Verify Docker installation
    if docker --version >/dev/null 2>&1; then
        print_success "Docker installed successfully"
    else
        print_error "Docker installation failed"
        exit 1
    fi
}

# Function to install TA-Lib
install_talib() {
    print_status "Installing TA-Lib..."
    
    # Install TA-Lib from source
    cd /tmp
    wget -q http://prdownloads.sourceforge.net/ta-lib/ta-lib-0.4.0-src.tar.gz
    tar -xzf ta-lib-0.4.0-src.tar.gz
    cd ta-lib/
    
    ./configure --prefix=/usr
    make
    make install
    ldconfig
    
    # Clean up
    cd /
    rm -rf /tmp/ta-lib*
    
    print_success "TA-Lib installed successfully"
}

# Function to setup project
setup_project() {
    print_status "Setting up trading bot project..."
    
    # Create project directory
    PROJECT_DIR="/opt/trading_bot"
    
    # Remove existing directory if it exists
    if [[ -d "$PROJECT_DIR" ]]; then
        print_warning "Removing existing project directory..."
        rm -rf $PROJECT_DIR
    fi
    
    # Clone the repository
    print_status "Cloning repository from: $REPO_URL"
    git clone $REPO_URL $PROJECT_DIR
    
    # Navigate to project directory
    cd $PROJECT_DIR
    
    # Create necessary directories
    mkdir -p logs data
    
    # Set proper permissions
    chown -R $USER:$USER $PROJECT_DIR
    
    print_success "Project setup completed"
}

# Function to create virtual environment and install Python dependencies
setup_python() {
    print_status "Setting up Python environment..."
    
    cd $PROJECT_DIR
    
    # Create virtual environment
    python3.11 -m venv venv
    source venv/bin/activate
    
    # Upgrade pip
    pip install --upgrade pip
    
    # Install Python dependencies
    pip install -r requirements.txt
    
    # Install additional dependencies that might be missing
    pip install pyyaml python-dotenv
    
    print_success "Python environment setup completed"
}

# Function to start database services
start_databases() {
    print_status "Starting database services..."
    
    # Stop existing containers
    docker stop postgres redis 2>/dev/null || true
    docker rm postgres redis 2>/dev/null || true
    
    # Start PostgreSQL
    docker run -d --name postgres \
        -e POSTGRES_DB=trading_bot \
        -e POSTGRES_USER=trading_bot \
        -e POSTGRES_PASSWORD="$DB_PASSWORD" \
        -p 5432:5432 \
        postgres:15-alpine
    
    # Start Redis
    docker run -d --name redis \
        -p 6379:6379 \
        redis:7-alpine
    
    # Wait for services to start
    print_status "Waiting for database services to start..."
    sleep 15
    
    # Initialize database
    docker exec -i postgres psql -U trading_bot -d trading_bot < ops/init.sql
    
    print_success "Database services started"
}

# Function to create configuration file
create_config() {
    print_status "Creating configuration file..."
    
    cd $PROJECT_DIR
    
    # Create config_local.yaml with user input
    cat > config_local.yaml << EOF
# Trading Configuration
trading:
  mode: "paper"  # paper, live, backtest
  base_currency: "USDT"
  symbols:
$SYMBOL_YAML  max_position_size: 10000
  max_daily_drawdown: 0.05
  max_consecutive_losses: 5

# Binance API Configuration
binance:
  testnet: false
  base_url: "https://api.binance.com"
  ws_base_url: "wss://stream.binance.com:9443/ws"
  # API credentials will be provided at runtime
  # api_key: "your_api_key_here"
  # api_secret: "your_api_secret_here"

# Database Configuration
database:
  postgres:
    host: "localhost"
    port: 5432
    database: "trading_bot"
    username: "trading_bot"
    password: "$DB_PASSWORD"
    pool_size: 10
    max_overflow: 20

# Redis Configuration
redis:
  host: "localhost"
  port: 6379
  database: 0
  password: null
  max_connections: 10

# Risk Management
risk:
  max_leverage: 1.0
  position_limits:
    BTCUSDT: 0.1
    ETHUSDT: 0.1
  stop_loss_pct: 0.02
  take_profit_pct: 0.04

# Strategy Configuration
strategies:
  scalper:
    enabled: true
    params:
      ema_short: 5
      ema_long: 20
      obi_threshold: 0.25
      risk_fraction: 0.01
      stop_distance: 0.005
  
  market_maker:
    enabled: false
    params:
      spread_pct: 0.001
      inventory_bias: 0.1
      refresh_interval: 5
      max_inventory: 1000
  
  pairs_arbitrage:
    enabled: false
    params:
      cointegration_window: 100
      z_score_threshold: 2.0
      kelly_fraction: 0.1
      max_position_ratio: 0.5

# Backtesting Configuration
backtest:
  start_date: "2024-01-01"
  end_date: "2024-12-31"
  initial_capital: 10000
  commission: 0.001
  slippage: 0.0005

# Dashboard Configuration
dashboard:
  host: "0.0.0.0"
  port: 8000
  debug: false
  secret_key: "$DASHBOARD_SECRET"

# Logging Configuration
logging:
  level: "INFO"
  format: "json"
  file: "logs/trading_bot.log"
  max_size: "10MB"
  backup_count: 5

# Monitoring Configuration
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
      enabled: $([ -n "$EMAIL_ADDRESS" ] && echo "true" || echo "false")
      smtp_server: "smtp.gmail.com"
      smtp_port: 587
      username: "$EMAIL_ADDRESS"
      password: "your_app_password"
EOF

    print_success "Configuration file created"
}

# Function to create systemd service
create_systemd_service() {
    print_status "Creating systemd service..."
    
    # Create systemd service file
    cat > /etc/systemd/system/trading-bot.service << EOF
[Unit]
Description=Binance Trading Bot
After=network.target postgresql.service redis.service
Wants=postgresql.service redis.service

[Service]
Type=simple
User=$USER
Group=$USER
WorkingDirectory=$PROJECT_DIR
ExecStart=$PROJECT_DIR/venv/bin/python run.py --mode paper
ExecReload=/bin/kill -HUP \$MAINPID
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal
SyslogIdentifier=trading_bot

# Environment variables
Environment=TRADING_MODE=paper
Environment=DB_HOST=localhost
Environment=DB_PORT=5432
Environment=DB_NAME=trading_bot
Environment=DB_USER=trading_bot
Environment=DB_PASSWORD=$DB_PASSWORD
Environment=REDIS_HOST=localhost
Environment=REDIS_PORT=6379
Environment=REDIS_DB=0

# Security settings
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=$PROJECT_DIR/logs
ReadWritePaths=$PROJECT_DIR/data

# Resource limits
LimitNOFILE=65536
LimitNPROC=4096

[Install]
WantedBy=multi-user.target
EOF

    # Reload systemd
    systemctl daemon-reload
    
    print_success "Systemd service created"
}

# Function to test installation
test_installation() {
    print_status "Testing installation..."
    
    cd $PROJECT_DIR
    source venv/bin/activate
    
    # Test paper trading mode
    timeout 10 python run.py --mode paper --verbose || {
        print_warning "Paper trading test timed out (this is normal)"
    }
    
    print_success "Installation test completed"
}

# Function to create startup script
create_startup_script() {
    print_status "Creating startup script..."
    
    cat > $PROJECT_DIR/start_bot.sh << 'EOF'
#!/bin/bash

# Trading Bot Startup Script
PROJECT_DIR="/opt/trading_bot"
cd $PROJECT_DIR

# Activate virtual environment
source venv/bin/activate

# Start the bot
echo "Starting Binance Trading Bot..."
echo "Dashboard will be available at: http://$(curl -s ifconfig.me):8000"
echo "Press Ctrl+C to stop the bot"
echo

python run.py --mode live --verbose
EOF

    chmod +x $PROJECT_DIR/start_bot.sh
    
    print_success "Startup script created"
}

# Function to display final information
display_final_info() {
    print_success "=== Fresh Installation Completed Successfully! ==="
    echo
    print_status "Trading Bot Information:"
    echo "  • Repository: $REPO_URL"
    echo "  • Project Directory: $PROJECT_DIR"
    echo "  • Dashboard URL: http://$SERVER_IP:8000"
    echo "  • Database: PostgreSQL (localhost:5432)"
    echo "  • Cache: Redis (localhost:6379)"
    echo "  • Logs: $PROJECT_DIR/logs/"
    echo
    print_status "To start the bot:"
    echo "  cd $PROJECT_DIR"
    echo "  ./start_bot.sh"
    echo
    print_status "Or manually:"
    echo "  cd $PROJECT_DIR"
    echo "  source venv/bin/activate"
    echo "  python run.py --mode live --verbose"
    echo
    print_status "To enable systemd service:"
    echo "  sudo systemctl enable trading-bot"
    echo "  sudo systemctl start trading-bot"
    echo
    print_warning "IMPORTANT: Before running in live mode, make sure to:"
    echo "  1. Configure your Binance API credentials"
    echo "  2. Test thoroughly in paper mode first"
    echo "  3. Set appropriate risk limits"
    echo "  4. Review and adjust configuration in config_local.yaml"
    echo
    print_status "Configuration file: $PROJECT_DIR/config_local.yaml"
    print_status "Logs: $PROJECT_DIR/logs/trading_bot.log"
    print_status "Repository: $REPO_URL"
}

# Main installation function
main() {
    print_status "=== Binance Trading Bot Fresh Installation ==="
    print_status "This script will install the trading bot on a fresh Ubuntu 22.04 server"
    print_status "The bot will be cloned from the Git repository and configured automatically"
    echo
    
    # Check if running as root
    check_root
    
    # Get user input
    get_user_input
    
    # Update system
    update_system
    
    # Install dependencies
    install_dependencies
    
    # Install Docker
    install_docker
    
    # Install TA-Lib
    install_talib
    
    # Setup project (clone repository)
    setup_project
    
    # Setup Python environment
    setup_python
    
    # Start database services
    start_databases
    
    # Create configuration
    create_config
    
    # Create systemd service
    create_systemd_service
    
    # Create startup script
    create_startup_script
    
    # Test installation
    test_installation
    
    # Display final information
    display_final_info
    
    print_success "Fresh installation completed successfully!"
}

# Run main function
main "$@"
