"""
Rate limiter implementation for Binance API calls.
Implements token bucket algorithm to respect Binance rate limits.
"""

import asyncio
import time
from typing import Dict, Optional
from dataclasses import dataclass
import logging


@dataclass
class RateLimit:
    """Rate limit configuration."""
    requests_per_second: int
    requests_per_minute: int
    requests_per_day: int
    weight_per_second: int
    weight_per_minute: int
    weight_per_day: int


class TokenBucket:
    """Token bucket implementation for rate limiting."""
    
    def __init__(self, capacity: int, refill_rate: float):
        """
        Initialize token bucket.
        
        Args:
            capacity: Maximum number of tokens
            refill_rate: Tokens added per second
        """
        self.capacity = capacity
        self.refill_rate = refill_rate
        self.tokens = capacity
        self.last_refill = time.time()
        self._lock = asyncio.Lock()
    
    async def consume(self, tokens: int = 1) -> bool:
        """
        Try to consume tokens from the bucket.
        
        Args:
            tokens: Number of tokens to consume
            
        Returns:
            True if tokens were consumed, False if not enough tokens
        """
        async with self._lock:
            self._refill()
            
            if self.tokens >= tokens:
                self.tokens -= tokens
                return True
            return False
    
    def _refill(self) -> None:
        """Refill tokens based on elapsed time."""
        now = time.time()
        elapsed = now - self.last_refill
        tokens_to_add = elapsed * self.refill_rate
        
        self.tokens = min(self.capacity, self.tokens + tokens_to_add)
        self.last_refill = now
    
    async def wait_for_tokens(self, tokens: int = 1) -> None:
        """Wait until enough tokens are available."""
        while not await self.consume(tokens):
            await asyncio.sleep(0.01)  # Small delay to prevent busy waiting


class RateLimiter:
    """
    Rate limiter for Binance API calls.
    
    Implements multiple token buckets for different rate limits:
    - Requests per second/minute/day
    - Weight per second/minute/day
    """
    
    def __init__(self, rate_limits: Optional[RateLimit] = None):
        """
        Initialize rate limiter.
        
        Args:
            rate_limits: Rate limit configuration. If None, uses conservative defaults.
        """
        self.logger = logging.getLogger(__name__)
        
        # Default rate limits (conservative)
        if rate_limits is None:
            rate_limits = RateLimit(
                requests_per_second=10,
                requests_per_minute=1200,
                requests_per_day=200000,
                weight_per_second=1200,
                weight_per_minute=6000,
                weight_per_day=1000000,
            )
        
        self.rate_limits = rate_limits
        
        # Token buckets for different limits
        self.request_buckets = {
            'second': TokenBucket(rate_limits.requests_per_second, rate_limits.requests_per_second),
            'minute': TokenBucket(rate_limits.requests_per_minute, rate_limits.requests_per_minute / 60),
            'day': TokenBucket(rate_limits.requests_per_day, rate_limits.requests_per_day / 86400),
        }
        
        self.weight_buckets = {
            'second': TokenBucket(rate_limits.weight_per_second, rate_limits.weight_per_second),
            'minute': TokenBucket(rate_limits.weight_per_minute, rate_limits.weight_per_minute / 60),
            'day': TokenBucket(rate_limits.weight_per_day, rate_limits.weight_per_day / 86400),
        }
        
        # Statistics
        self.total_requests = 0
        self.total_weight = 0
        self.rate_limited_requests = 0
    
    async def wait_for_request(self, weight: int = 1) -> None:
        """
        Wait for rate limit to allow a request.
        
        Args:
            weight: Weight of the request (for weight-based limits)
        """
        # Wait for request limits
        await self.request_buckets['second'].wait_for_tokens(1)
        await self.request_buckets['minute'].wait_for_tokens(1)
        await self.request_buckets['day'].wait_for_tokens(1)
        
        # Wait for weight limits
        await self.weight_buckets['second'].wait_for_tokens(weight)
        await self.weight_buckets['minute'].wait_for_tokens(weight)
        await self.weight_buckets['day'].wait_for_tokens(weight)
        
        # Update statistics
        self.total_requests += 1
        self.total_weight += weight
    
    async def check_request(self, weight: int = 1) -> bool:
        """
        Check if a request can be made without waiting.
        
        Args:
            weight: Weight of the request
            
        Returns:
            True if request can be made immediately, False otherwise
        """
        # Check all limits
        checks = [
            await self.request_buckets['second'].consume(1),
            await self.request_buckets['minute'].consume(1),
            await self.request_buckets['day'].consume(1),
            await self.weight_buckets['second'].consume(weight),
            await self.weight_buckets['minute'].consume(weight),
            await self.weight_buckets['day'].consume(weight),
        ]
        
        if all(checks):
            self.total_requests += 1
            self.total_weight += weight
            return True
        else:
            self.rate_limited_requests += 1
            return False
    
    def get_stats(self) -> Dict:
        """Get rate limiter statistics."""
        return {
            'total_requests': self.total_requests,
            'total_weight': self.total_weight,
            'rate_limited_requests': self.rate_limited_requests,
            'request_buckets': {
                name: {
                    'tokens': bucket.tokens,
                    'capacity': bucket.capacity,
                    'refill_rate': bucket.refill_rate,
                }
                for name, bucket in self.request_buckets.items()
            },
            'weight_buckets': {
                name: {
                    'tokens': bucket.tokens,
                    'capacity': bucket.capacity,
                    'refill_rate': bucket.refill_rate,
                }
                for name, bucket in self.weight_buckets.items()
            },
        }
    
    def update_rate_limits(self, rate_limits: RateLimit) -> None:
        """
        Update rate limits dynamically.
        
        Args:
            rate_limits: New rate limit configuration
        """
        self.rate_limits = rate_limits
        
        # Update request buckets
        self.request_buckets['second'] = TokenBucket(
            rate_limits.requests_per_second, 
            rate_limits.requests_per_second
        )
        self.request_buckets['minute'] = TokenBucket(
            rate_limits.requests_per_minute, 
            rate_limits.requests_per_minute / 60
        )
        self.request_buckets['day'] = TokenBucket(
            rate_limits.requests_per_day, 
            rate_limits.requests_per_day / 86400
        )
        
        # Update weight buckets
        self.weight_buckets['second'] = TokenBucket(
            rate_limits.weight_per_second, 
            rate_limits.weight_per_second
        )
        self.weight_buckets['minute'] = TokenBucket(
            rate_limits.weight_per_minute, 
            rate_limits.weight_per_minute / 60
        )
        self.weight_buckets['day'] = TokenBucket(
            rate_limits.weight_per_day, 
            rate_limits.weight_per_day / 86400
        )
        
        self.logger.info("Updated rate limits from exchange info")
