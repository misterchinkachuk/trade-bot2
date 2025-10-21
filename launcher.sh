#!/bin/bash

# Trading Bot Launcher Script
# This script provides easy access to common bot operations

set -e

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

print_header() {
    echo -e "${BLUE}=== Binance Trading Bot Launcher ===${NC}"
    echo
}

print_menu() {
    echo "Available commands:"
    echo "  1) Start Bot (Live Mode)"
    echo "  2) Start Bot (Paper Mode)"
    echo "  3) Start Bot (Backtest Mode)"
    echo "  4) Start Dashboard Only"
    echo "  5) Check Bot Status"
    echo "  6) View Logs"
    echo "  7) Restart Services"
    echo "  8) Stop Bot"
    echo "  9) Update Bot"
    echo "  0) Exit"
    echo
}

check_venv() {
    if [[ ! -f "venv/bin/activate" ]]; then
        echo -e "${RED}Error: Virtual environment not found!${NC}"
        echo "Please run the installation script first."
        exit 1
    fi
}

check_config() {
    if [[ ! -f "config_local.yaml" ]]; then
        echo -e "${RED}Error: Configuration file not found!${NC}"
        echo "Please create config_local.yaml first."
        exit 1
    fi
}

start_bot() {
    local mode=$1
    echo -e "${GREEN}Starting bot in $mode mode...${NC}"
    
    source venv/bin/activate
    
    if [[ "$mode" == "live" ]]; then
        echo -e "${YELLOW}WARNING: Live mode uses real money!${NC}"
        echo "Make sure you have configured your API credentials."
        read -p "Continue? (y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            echo "Cancelled."
            return
        fi
    fi
    
    echo "Dashboard: http://$(curl -s ifconfig.me 2>/dev/null || echo localhost):8000"
    echo "Press Ctrl+C to stop the bot"
    echo
    
    python run.py --mode $mode --verbose
}

start_dashboard() {
    echo -e "${GREEN}Starting dashboard only...${NC}"
    source venv/bin/activate
    python -m dashboard.api
}

check_status() {
    echo -e "${BLUE}Checking bot status...${NC}"
    echo
    
    # Check if bot is running
    if pgrep -f "run.py" > /dev/null; then
        echo -e "${GREEN}✓ Bot is running${NC}"
    else
        echo -e "${RED}✗ Bot is not running${NC}"
    fi
    
    # Check database
    if docker ps | grep -q postgres; then
        echo -e "${GREEN}✓ PostgreSQL is running${NC}"
    else
        echo -e "${RED}✗ PostgreSQL is not running${NC}"
    fi
    
    # Check Redis
    if docker ps | grep -q redis; then
        echo -e "${GREEN}✓ Redis is running${NC}"
    else
        echo -e "${RED}✗ Redis is not running${NC}"
    fi
    
    # Check dashboard
    if curl -s http://localhost:8000/health > /dev/null 2>&1; then
        echo -e "${GREEN}✓ Dashboard is accessible${NC}"
    else
        echo -e "${RED}✗ Dashboard is not accessible${NC}"
    fi
}

view_logs() {
    echo -e "${BLUE}Viewing bot logs...${NC}"
    echo "Press Ctrl+C to exit log viewer"
    echo
    
    if [[ -f "logs/trading_bot.log" ]]; then
        tail -f logs/trading_bot.log
    else
        echo "No log file found."
    fi
}

restart_services() {
    echo -e "${BLUE}Restarting services...${NC}"
    
    # Stop bot if running
    pkill -f "run.py" 2>/dev/null || true
    
    # Restart database containers
    docker restart postgres redis 2>/dev/null || true
    
    # Wait for services
    sleep 5
    
    echo -e "${GREEN}Services restarted${NC}"
}

stop_bot() {
    echo -e "${BLUE}Stopping bot...${NC}"
    pkill -f "run.py" 2>/dev/null || true
    echo -e "${GREEN}Bot stopped${NC}"
}

update_bot() {
    echo -e "${BLUE}Updating bot...${NC}"
    
    # Pull latest changes
    git pull origin main
    
    # Update dependencies
    source venv/bin/activate
    pip install -r requirements.txt
    
    echo -e "${GREEN}Bot updated${NC}"
}

main() {
    print_header
    
    # Check prerequisites
    check_venv
    check_config
    
    while true; do
        print_menu
        read -p "Select option (0-9): " choice
        
        case $choice in
            1)
                start_bot "live"
                ;;
            2)
                start_bot "paper"
                ;;
            3)
                start_bot "backtest"
                ;;
            4)
                start_dashboard
                ;;
            5)
                check_status
                ;;
            6)
                view_logs
                ;;
            7)
                restart_services
                ;;
            8)
                stop_bot
                ;;
            9)
                update_bot
                ;;
            0)
                echo "Goodbye!"
                exit 0
                ;;
            *)
                echo -e "${RED}Invalid option. Please try again.${NC}"
                ;;
        esac
        
        echo
        read -p "Press Enter to continue..."
        clear
    done
}

# Run main function
main "$@"
