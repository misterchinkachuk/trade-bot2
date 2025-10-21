"""
Tests for Binance connectors.
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from decimal import Decimal

from bot.connectors import BinanceRESTClient, BinanceWebSocketClient, RateLimiter
from bot.types import OrderSide, OrderType, TimeInForce


class TestRateLimiter:
    """Test rate limiter functionality."""
    
    def test_initialization(self):
        """Test rate limiter initialization."""
        limiter = RateLimiter()
        assert limiter.total_requests == 0
        assert limiter.total_weight == 0
    
    @pytest.mark.asyncio
    async def test_wait_for_request(self):
        """Test waiting for request."""
        limiter = RateLimiter()
        
        # Should not block for first request
        start_time = asyncio.get_event_loop().time()
        await limiter.wait_for_request(weight=1)
        end_time = asyncio.get_event_loop().time()
        
        assert end_time - start_time < 0.1  # Should be very fast
        assert limiter.total_requests == 1
        assert limiter.total_weight == 1
    
    @pytest.mark.asyncio
    async def test_check_request(self):
        """Test checking request without waiting."""
        limiter = RateLimiter()
        
        # First request should succeed
        result = await limiter.check_request(weight=1)
        assert result is True
        assert limiter.total_requests == 1
        
        # Second request should also succeed (within limits)
        result = await limiter.check_request(weight=1)
        assert result is True
        assert limiter.total_requests == 2
    
    def test_get_stats(self):
        """Test getting statistics."""
        limiter = RateLimiter()
        stats = limiter.get_stats()
        
        assert 'total_requests' in stats
        assert 'total_weight' in stats
        assert 'rate_limited_requests' in stats


class TestBinanceRESTClient:
    """Test Binance REST client."""
    
    @pytest.fixture
    def client(self):
        """Create REST client instance."""
        return BinanceRESTClient(
            api_key="test_key",
            api_secret="test_secret",
            base_url="https://testnet.binance.vision",
            testnet=True
        )
    
    @pytest.mark.asyncio
    async def test_initialization(self, client):
        """Test client initialization."""
        with patch('aiohttp.ClientSession') as mock_session:
            mock_session.return_value = AsyncMock()
            await client.initialize()
            assert client.session is not None
    
    @pytest.mark.asyncio
    async def test_generate_signature(self, client):
        """Test signature generation."""
        params = {'symbol': 'BTCUSDT', 'timestamp': 1234567890}
        signature = client._generate_signature(params)
        
        assert isinstance(signature, str)
        assert len(signature) == 64  # SHA256 hex length
    
    @pytest.mark.asyncio
    async def test_make_request_success(self, client):
        """Test successful request."""
        with patch('aiohttp.ClientSession') as mock_session:
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.json = AsyncMock(return_value={'success': True})
            
            mock_session.return_value.request = AsyncMock(return_value=mock_response)
            await client.initialize()
            
            result = await client._make_request('GET', '/test', {'param': 'value'})
            assert result == {'success': True}
    
    @pytest.mark.asyncio
    async def test_make_request_rate_limit(self, client):
        """Test rate limit handling."""
        with patch('aiohttp.ClientSession') as mock_session:
            # First response: rate limited
            mock_response_429 = AsyncMock()
            mock_response_429.status = 429
            mock_response_429.headers = {'Retry-After': '1'}
            
            # Second response: success
            mock_response_200 = AsyncMock()
            mock_response_200.status = 200
            mock_response_200.json = AsyncMock(return_value={'success': True})
            
            mock_session.return_value.request = AsyncMock(side_effect=[mock_response_429, mock_response_200])
            await client.initialize()
            
            with patch('asyncio.sleep') as mock_sleep:
                result = await client._make_request('GET', '/test')
                assert result == {'success': True}
                mock_sleep.assert_called_once_with(1)  # Should wait for retry
    
    @pytest.mark.asyncio
    async def test_place_order(self, client):
        """Test placing an order."""
        with patch.object(client, '_make_request') as mock_request:
            mock_request.return_value = {
                'symbol': 'BTCUSDT',
                'orderId': 12345,
                'clientOrderId': 'test_order',
                'side': 'BUY',
                'type': 'LIMIT',
                'origQty': '0.1',
                'price': '50000',
                'timeInForce': 'GTC',
                'status': 'NEW',
                'executedQty': '0',
                'cummulativeQuoteQty': '0'
            }
            
            order = await client.place_order(
                symbol='BTCUSDT',
                side=OrderSide.BUY,
                order_type=OrderType.LIMIT,
                quantity=0.1,
                price=50000
            )
            
            assert order.symbol == 'BTCUSDT'
            assert order.side == OrderSide.BUY
            assert order.type == OrderType.LIMIT
            assert order.quantity == Decimal('0.1')
            assert order.price == Decimal('50000')
    
    @pytest.mark.asyncio
    async def test_get_account_info(self, client):
        """Test getting account info."""
        with patch.object(client, '_make_request') as mock_request:
            mock_request.return_value = {
                'accountType': 'SPOT',
                'canTrade': True,
                'canDeposit': True,
                'canWithdraw': False,
                'updateTime': 1234567890,
                'balances': [
                    {'asset': 'BTC', 'free': '1.0', 'locked': '0.0'},
                    {'asset': 'USDT', 'free': '10000.0', 'locked': '0.0'}
                ],
                'permissions': ['SPOT']
            }
            
            account_info = await client.get_account_info()
            
            assert account_info.account_type == 'SPOT'
            assert account_info.can_trade is True
            assert 'BTC' in account_info.balances
            assert account_info.balances['BTC'] == Decimal('1.0')


class TestBinanceWebSocketClient:
    """Test Binance WebSocket client."""
    
    @pytest.fixture
    def client(self):
        """Create WebSocket client instance."""
        return BinanceWebSocketClient(
            base_url="wss://testnet.binance.vision/ws",
            testnet=True
        )
    
    @pytest.mark.asyncio
    async def test_initialization(self, client):
        """Test client initialization."""
        assert client.base_url == "wss://testnet.binance.vision/ws"
        assert client.testnet is True
        assert not client.is_connected
    
    @pytest.mark.asyncio
    async def test_connect_disconnect(self, client):
        """Test connection and disconnection."""
        with patch('websockets.connect') as mock_connect:
            mock_websocket = AsyncMock()
            mock_connect.return_value = mock_websocket
            
            await client.connect()
            assert client.is_connected
            assert client.websocket == mock_websocket
            
            await client.disconnect()
            assert not client.is_connected
            assert client.websocket is None
    
    @pytest.mark.asyncio
    async def test_subscribe_to_streams(self, client):
        """Test subscribing to streams."""
        with patch('websockets.connect') as mock_connect:
            mock_websocket = AsyncMock()
            mock_connect.return_value = mock_websocket
            
            await client.connect()
            await client.subscribe_to_streams(['btcusdt@ticker', 'ethusdt@ticker'])
            
            assert 'btcusdt@ticker' in client.subscribed_streams
            assert 'ethusdt@ticker' in client.subscribed_streams
            mock_websocket.send.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_handle_ticker_data(self, client):
        """Test handling ticker data."""
        with patch.object(client, 'on_market_data') as mock_handler:
            client.on_market_data = mock_handler
            
            message = {
                'stream': 'btcusdt@ticker',
                'data': {
                    's': 'BTCUSDT',
                    'c': '50000.00',
                    'v': '100.0',
                    'P': '1.5'
                }
            }
            
            await client._handle_message(str(message).replace("'", '"'))
            
            # Should call the handler with market data
            mock_handler.assert_called_once()
            call_args = mock_handler.call_args[0][0]
            assert call_args.symbol == 'BTCUSDT'
            assert call_args.price == Decimal('50000.00')
    
    @pytest.mark.asyncio
    async def test_handle_depth_data(self, client):
        """Test handling depth data."""
        with patch.object(client, 'on_orderbook_update') as mock_handler:
            client.on_orderbook_update = mock_handler
            
            message = {
                'stream': 'btcusdt@depth',
                'data': {
                    's': 'BTCUSDT',
                    'b': [['49999.00', '1.0'], ['49998.00', '2.0']],
                    'a': [['50001.00', '1.5'], ['50002.00', '2.5']],
                    'u': 12345
                }
            }
            
            await client._handle_message(str(message).replace("'", '"'))
            
            # Should call the handler with orderbook data
            mock_handler.assert_called_once()
            call_args = mock_handler.call_args[0][0]
            assert call_args.symbol == 'BTCUSDT'
            assert len(call_args.bids) == 2
            assert len(call_args.asks) == 2
    
    def test_get_stats(self, client):
        """Test getting statistics."""
        stats = client.get_stats()
        
        assert 'is_connected' in stats
        assert 'is_running' in stats
        assert 'subscribed_streams' in stats
        assert 'messages_received' in stats
        assert 'messages_processed' in stats


@pytest.mark.asyncio
async def test_integration_rest_websocket():
    """Test integration between REST and WebSocket clients."""
    # This would test the integration in a real scenario
    # For now, just test that they can be created together
    rest_client = BinanceRESTClient(
        api_key="test_key",
        api_secret="test_secret",
        testnet=True
    )
    
    ws_client = BinanceWebSocketClient(testnet=True)
    
    assert rest_client.testnet is True
    assert ws_client.testnet is True


if __name__ == "__main__":
    pytest.main([__file__])
