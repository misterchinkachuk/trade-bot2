-- Database initialization script for trading bot
-- This script creates all necessary tables and indexes

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Create trades table
CREATE TABLE IF NOT EXISTS trades (
    id SERIAL PRIMARY KEY,
    symbol VARCHAR(20) NOT NULL,
    order_id BIGINT NOT NULL,
    trade_id BIGINT NOT NULL,
    side VARCHAR(10) NOT NULL,
    quantity DECIMAL(20, 8) NOT NULL,
    price DECIMAL(20, 8) NOT NULL,
    commission DECIMAL(20, 8) NOT NULL,
    commission_asset VARCHAR(10) NOT NULL,
    timestamp TIMESTAMP NOT NULL,
    is_maker BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(trade_id)
);

-- Create positions table
CREATE TABLE IF NOT EXISTS positions (
    id SERIAL PRIMARY KEY,
    symbol VARCHAR(20) NOT NULL UNIQUE,
    side VARCHAR(10) NOT NULL,
    size DECIMAL(20, 8) NOT NULL,
    entry_price DECIMAL(20, 8) NOT NULL,
    mark_price DECIMAL(20, 8) NOT NULL,
    unrealized_pnl DECIMAL(20, 8) NOT NULL DEFAULT 0,
    realized_pnl DECIMAL(20, 8) NOT NULL DEFAULT 0,
    margin DECIMAL(20, 8) NOT NULL DEFAULT 0,
    leverage DECIMAL(10, 4) NOT NULL DEFAULT 1.0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create daily_pnl table
CREATE TABLE IF NOT EXISTS daily_pnl (
    id SERIAL PRIMARY KEY,
    date DATE NOT NULL,
    symbol VARCHAR(20) NOT NULL,
    realized_pnl DECIMAL(20, 8) NOT NULL DEFAULT 0,
    unrealized_pnl DECIMAL(20, 8) NOT NULL DEFAULT 0,
    total_pnl DECIMAL(20, 8) NOT NULL DEFAULT 0,
    fees DECIMAL(20, 8) NOT NULL DEFAULT 0,
    volume DECIMAL(20, 8) NOT NULL DEFAULT 0,
    trades_count INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(date, symbol)
);

-- Create klines table
CREATE TABLE IF NOT EXISTS klines (
    id SERIAL PRIMARY KEY,
    symbol VARCHAR(20) NOT NULL,
    interval VARCHAR(10) NOT NULL,
    open_time TIMESTAMP NOT NULL,
    close_time TIMESTAMP NOT NULL,
    open_price DECIMAL(20, 8) NOT NULL,
    high_price DECIMAL(20, 8) NOT NULL,
    low_price DECIMAL(20, 8) NOT NULL,
    close_price DECIMAL(20, 8) NOT NULL,
    volume DECIMAL(20, 8) NOT NULL,
    quote_volume DECIMAL(20, 8) NOT NULL,
    trades_count INTEGER NOT NULL,
    taker_buy_volume DECIMAL(20, 8) NOT NULL,
    taker_buy_quote_volume DECIMAL(20, 8) NOT NULL,
    is_closed BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(symbol, interval, open_time)
);

-- Create orders table
CREATE TABLE IF NOT EXISTS orders (
    id SERIAL PRIMARY KEY,
    symbol VARCHAR(20) NOT NULL,
    order_id BIGINT,
    client_order_id VARCHAR(50),
    side VARCHAR(10) NOT NULL,
    type VARCHAR(20) NOT NULL,
    quantity DECIMAL(20, 8) NOT NULL,
    price DECIMAL(20, 8),
    stop_price DECIMAL(20, 8),
    time_in_force VARCHAR(10) NOT NULL,
    status VARCHAR(20) NOT NULL,
    executed_qty DECIMAL(20, 8) NOT NULL DEFAULT 0,
    cummulative_quote_qty DECIMAL(20, 8) NOT NULL DEFAULT 0,
    avg_price DECIMAL(20, 8),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create risk_events table
CREATE TABLE IF NOT EXISTS risk_events (
    id SERIAL PRIMARY KEY,
    event_type VARCHAR(50) NOT NULL,
    symbol VARCHAR(20),
    message TEXT NOT NULL,
    severity VARCHAR(20) NOT NULL DEFAULT 'WARNING',
    metadata JSONB,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create performance_metrics table
CREATE TABLE IF NOT EXISTS performance_metrics (
    id SERIAL PRIMARY KEY,
    strategy_name VARCHAR(50) NOT NULL,
    metric_name VARCHAR(50) NOT NULL,
    metric_value DECIMAL(20, 8) NOT NULL,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for better performance
CREATE INDEX IF NOT EXISTS idx_trades_symbol ON trades(symbol);
CREATE INDEX IF NOT EXISTS idx_trades_timestamp ON trades(timestamp);
CREATE INDEX IF NOT EXISTS idx_trades_order_id ON trades(order_id);

CREATE INDEX IF NOT EXISTS idx_positions_symbol ON positions(symbol);

CREATE INDEX IF NOT EXISTS idx_daily_pnl_date ON daily_pnl(date);
CREATE INDEX IF NOT EXISTS idx_daily_pnl_symbol ON daily_pnl(symbol);

CREATE INDEX IF NOT EXISTS idx_klines_symbol ON klines(symbol);
CREATE INDEX IF NOT EXISTS idx_klines_interval ON klines(interval);
CREATE INDEX IF NOT EXISTS idx_klines_open_time ON klines(open_time);
CREATE INDEX IF NOT EXISTS idx_klines_symbol_interval_time ON klines(symbol, interval, open_time);

CREATE INDEX IF NOT EXISTS idx_orders_symbol ON orders(symbol);
CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status);
CREATE INDEX IF NOT EXISTS idx_orders_created_at ON orders(created_at);

CREATE INDEX IF NOT EXISTS idx_risk_events_timestamp ON risk_events(timestamp);
CREATE INDEX IF NOT EXISTS idx_risk_events_severity ON risk_events(severity);

CREATE INDEX IF NOT EXISTS idx_performance_metrics_strategy ON performance_metrics(strategy_name);
CREATE INDEX IF NOT EXISTS idx_performance_metrics_timestamp ON performance_metrics(timestamp);

-- Create views for common queries
CREATE OR REPLACE VIEW daily_summary AS
SELECT 
    date,
    SUM(total_pnl) as total_pnl,
    SUM(fees) as total_fees,
    SUM(volume) as total_volume,
    SUM(trades_count) as total_trades
FROM daily_pnl
GROUP BY date
ORDER BY date DESC;

CREATE OR REPLACE VIEW strategy_performance AS
SELECT 
    strategy_name,
    COUNT(*) as metric_count,
    AVG(metric_value) as avg_value,
    MIN(metric_value) as min_value,
    MAX(metric_value) as max_value,
    MAX(timestamp) as last_updated
FROM performance_metrics
GROUP BY strategy_name;

-- Insert initial data
INSERT INTO daily_pnl (date, symbol, total_pnl, fees, volume, trades_count)
VALUES (CURRENT_DATE, 'INIT', 0, 0, 0, 0)
ON CONFLICT (date, symbol) DO NOTHING;
