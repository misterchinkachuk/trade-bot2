"""
Monitoring and alerting module.
Handles metrics collection, health checks, and alerting.
"""

import asyncio
import logging
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Callable
from decimal import Decimal
import json

from .config import Config
from .types import MarketData, Order, Fill, RiskEvent


class MonitoringManager:
    """
    Monitoring and alerting system.
    
    Handles:
    - Metrics collection
    - Health checks
    - Alerting
    - Performance monitoring
    """
    
    def __init__(self, config: Config):
        """Initialize monitoring manager."""
        self.config = config
        self.logger = logging.getLogger(__name__)
        
        # Metrics storage
        self.metrics: Dict[str, Any] = {}
        self.health_status: Dict[str, Any] = {}
        self.alerts: List[Dict[str, Any]] = []
        
        # Performance tracking
        self.performance_metrics = {
            'latency': [],
            'throughput': [],
            'error_rate': [],
            'memory_usage': [],
            'cpu_usage': []
        }
        
        # Alert thresholds
        self.alert_thresholds = {
            'max_latency': 1000,  # ms
            'min_throughput': 10,  # messages per second
            'max_error_rate': 0.05,  # 5%
            'max_memory_usage': 0.8,  # 80%
            'max_cpu_usage': 0.8,  # 80%
        }
        
        # Statistics
        self.metrics_collected = 0
        self.alerts_sent = 0
        self.health_checks = 0
    
    async def initialize(self) -> None:
        """Initialize the monitoring manager."""
        try:
            # Initialize health status
            self.health_status = {
                'overall': 'HEALTHY',
                'components': {},
                'last_check': time.time(),
                'uptime': 0
            }
            
            self.logger.info("Monitoring manager initialized")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize monitoring manager: {e}")
            raise
    
    async def start(self) -> None:
        """Start monitoring."""
        try:
            # Start health check loop
            asyncio.create_task(self._health_check_loop())
            
            # Start metrics collection loop
            asyncio.create_task(self._metrics_collection_loop())
            
            self.logger.info("Monitoring started")
            
        except Exception as e:
            self.logger.error(f"Failed to start monitoring: {e}")
            raise
    
    async def stop(self) -> None:
        """Stop monitoring."""
        self.logger.info("Monitoring stopped")
    
    async def _health_check_loop(self) -> None:
        """Health check loop."""
        while True:
            try:
                await self._perform_health_check()
                await asyncio.sleep(30)  # Check every 30 seconds
                
            except Exception as e:
                self.logger.error(f"Error in health check loop: {e}")
                await asyncio.sleep(30)
    
    async def _metrics_collection_loop(self) -> None:
        """Metrics collection loop."""
        while True:
            try:
                await self._collect_metrics()
                await asyncio.sleep(10)  # Collect every 10 seconds
                
            except Exception as e:
                self.logger.error(f"Error in metrics collection loop: {e}")
                await asyncio.sleep(10)
    
    async def _perform_health_check(self) -> None:
        """Perform health check on all components."""
        try:
            self.health_checks += 1
            
            # Check overall health
            overall_health = 'HEALTHY'
            component_health = {}
            
            # Check data ingestion
            data_health = await self._check_data_ingestion_health()
            component_health['data_ingestion'] = data_health
            
            # Check order management
            order_health = await self._check_order_management_health()
            component_health['order_management'] = order_health
            
            # Check risk management
            risk_health = await self._check_risk_management_health()
            component_health['risk_management'] = risk_health
            
            # Check accounting
            accounting_health = await self._check_accounting_health()
            component_health['accounting'] = accounting_health
            
            # Determine overall health
            if any(health['status'] == 'UNHEALTHY' for health in component_health.values()):
                overall_health = 'UNHEALTHY'
            elif any(health['status'] == 'DEGRADED' for health in component_health.values()):
                overall_health = 'DEGRADED'
            
            # Update health status
            self.health_status.update({
                'overall': overall_health,
                'components': component_health,
                'last_check': time.time(),
                'uptime': time.time() - self.health_status.get('start_time', time.time())
            })
            
            # Send alerts if health degraded
            if overall_health != 'HEALTHY':
                await self._send_health_alert(overall_health, component_health)
            
        except Exception as e:
            self.logger.error(f"Error performing health check: {e}")
    
    async def _check_data_ingestion_health(self) -> Dict[str, Any]:
        """Check data ingestion health."""
        try:
            # This would check WebSocket connection, data flow, etc.
            # For now, we'll return a mock status
            return {
                'status': 'HEALTHY',
                'message': 'Data ingestion working normally',
                'last_data_time': time.time(),
                'data_rate': 100  # messages per second
            }
            
        except Exception as e:
            return {
                'status': 'UNHEALTHY',
                'message': f'Data ingestion error: {e}',
                'error': str(e)
            }
    
    async def _check_order_management_health(self) -> Dict[str, Any]:
        """Check order management health."""
        try:
            # This would check order placement, execution, etc.
            return {
                'status': 'HEALTHY',
                'message': 'Order management working normally',
                'active_orders': 0,
                'pending_orders': 0
            }
            
        except Exception as e:
            return {
                'status': 'UNHEALTHY',
                'message': f'Order management error: {e}',
                'error': str(e)
            }
    
    async def _check_risk_management_health(self) -> Dict[str, Any]:
        """Check risk management health."""
        try:
            # This would check risk limits, position monitoring, etc.
            return {
                'status': 'HEALTHY',
                'message': 'Risk management working normally',
                'risk_breach': False,
                'active_positions': 0
            }
            
        except Exception as e:
            return {
                'status': 'UNHEALTHY',
                'message': f'Risk management error: {e}',
                'error': str(e)
            }
    
    async def _check_accounting_health(self) -> Dict[str, Any]:
        """Check accounting health."""
        try:
            # This would check P&L calculation, trade recording, etc.
            return {
                'status': 'HEALTHY',
                'message': 'Accounting working normally',
                'total_pnl': 0,
                'total_fees': 0
            }
            
        except Exception as e:
            return {
                'status': 'UNHEALTHY',
                'message': f'Accounting error: {e}',
                'error': str(e)
            }
    
    async def _collect_metrics(self) -> None:
        """Collect system metrics."""
        try:
            self.metrics_collected += 1
            
            # Collect latency metrics
            latency = await self._measure_latency()
            self.performance_metrics['latency'].append(latency)
            
            # Collect throughput metrics
            throughput = await self._measure_throughput()
            self.performance_metrics['throughput'].append(throughput)
            
            # Collect error rate
            error_rate = await self._measure_error_rate()
            self.performance_metrics['error_rate'].append(error_rate)
            
            # Collect system metrics
            memory_usage = await self._measure_memory_usage()
            self.performance_metrics['memory_usage'].append(memory_usage)
            
            cpu_usage = await self._measure_cpu_usage()
            self.performance_metrics['cpu_usage'].append(cpu_usage)
            
            # Keep only last 1000 measurements
            for metric in self.performance_metrics.values():
                if len(metric) > 1000:
                    metric[:] = metric[-1000:]
            
            # Check for alert conditions
            await self._check_alert_conditions()
            
        except Exception as e:
            self.logger.error(f"Error collecting metrics: {e}")
    
    async def _measure_latency(self) -> float:
        """Measure system latency."""
        try:
            start_time = time.time()
            # This would measure actual latency
            await asyncio.sleep(0.001)  # Mock delay
            return (time.time() - start_time) * 1000  # Convert to ms
            
        except Exception as e:
            self.logger.error(f"Error measuring latency: {e}")
            return 0.0
    
    async def _measure_throughput(self) -> float:
        """Measure system throughput."""
        try:
            # This would measure actual throughput
            return 100.0  # Mock throughput
            
        except Exception as e:
            self.logger.error(f"Error measuring throughput: {e}")
            return 0.0
    
    async def _measure_error_rate(self) -> float:
        """Measure system error rate."""
        try:
            # This would measure actual error rate
            return 0.01  # Mock error rate
            
        except Exception as e:
            self.logger.error(f"Error measuring error rate: {e}")
            return 0.0
    
    async def _measure_memory_usage(self) -> float:
        """Measure memory usage."""
        try:
            import psutil
            return psutil.virtual_memory().percent / 100.0
            
        except ImportError:
            return 0.5  # Mock memory usage
        except Exception as e:
            self.logger.error(f"Error measuring memory usage: {e}")
            return 0.0
    
    async def _measure_cpu_usage(self) -> float:
        """Measure CPU usage."""
        try:
            import psutil
            return psutil.cpu_percent() / 100.0
            
        except ImportError:
            return 0.3  # Mock CPU usage
        except Exception as e:
            self.logger.error(f"Error measuring CPU usage: {e}")
            return 0.0
    
    async def _check_alert_conditions(self) -> None:
        """Check for alert conditions."""
        try:
            # Check latency
            if self.performance_metrics['latency']:
                avg_latency = sum(self.performance_metrics['latency'][-10:]) / len(self.performance_metrics['latency'][-10:])
                if avg_latency > self.alert_thresholds['max_latency']:
                    await self._send_alert('HIGH_LATENCY', f'Average latency {avg_latency:.2f}ms exceeds threshold')
            
            # Check throughput
            if self.performance_metrics['throughput']:
                avg_throughput = sum(self.performance_metrics['throughput'][-10:]) / len(self.performance_metrics['throughput'][-10:])
                if avg_throughput < self.alert_thresholds['min_throughput']:
                    await self._send_alert('LOW_THROUGHPUT', f'Average throughput {avg_throughput:.2f} below threshold')
            
            # Check error rate
            if self.performance_metrics['error_rate']:
                avg_error_rate = sum(self.performance_metrics['error_rate'][-10:]) / len(self.performance_metrics['error_rate'][-10:])
                if avg_error_rate > self.alert_thresholds['max_error_rate']:
                    await self._send_alert('HIGH_ERROR_RATE', f'Error rate {avg_error_rate:.2%} exceeds threshold')
            
            # Check memory usage
            if self.performance_metrics['memory_usage']:
                avg_memory = sum(self.performance_metrics['memory_usage'][-10:]) / len(self.performance_metrics['memory_usage'][-10:])
                if avg_memory > self.alert_thresholds['max_memory_usage']:
                    await self._send_alert('HIGH_MEMORY_USAGE', f'Memory usage {avg_memory:.2%} exceeds threshold')
            
            # Check CPU usage
            if self.performance_metrics['cpu_usage']:
                avg_cpu = sum(self.performance_metrics['cpu_usage'][-10:]) / len(self.performance_metrics['cpu_usage'][-10:])
                if avg_cpu > self.alert_thresholds['max_cpu_usage']:
                    await self._send_alert('HIGH_CPU_USAGE', f'CPU usage {avg_cpu:.2%} exceeds threshold')
            
        except Exception as e:
            self.logger.error(f"Error checking alert conditions: {e}")
    
    async def _send_alert(self, alert_type: str, message: str) -> None:
        """Send an alert."""
        try:
            alert = {
                'type': alert_type,
                'message': message,
                'timestamp': time.time(),
                'severity': 'WARNING'
            }
            
            self.alerts.append(alert)
            self.alerts_sent += 1
            
            # Send to configured alert channels
            if self.config.monitoring.telegram_enabled:
                await self._send_telegram_alert(alert)
            
            if self.config.monitoring.email_enabled:
                await self._send_email_alert(alert)
            
            self.logger.warning(f"Alert sent: {alert_type} - {message}")
            
        except Exception as e:
            self.logger.error(f"Error sending alert: {e}")
    
    async def _send_health_alert(self, overall_health: str, component_health: Dict[str, Any]) -> None:
        """Send health alert."""
        try:
            message = f"System health: {overall_health}\n"
            for component, health in component_health.items():
                message += f"{component}: {health['status']} - {health['message']}\n"
            
            await self._send_alert('HEALTH_DEGRADED', message)
            
        except Exception as e:
            self.logger.error(f"Error sending health alert: {e}")
    
    async def _send_telegram_alert(self, alert: Dict[str, Any]) -> None:
        """Send alert via Telegram."""
        try:
            # This would implement Telegram bot integration
            self.logger.info(f"Telegram alert: {alert['message']}")
            
        except Exception as e:
            self.logger.error(f"Error sending Telegram alert: {e}")
    
    async def _send_email_alert(self, alert: Dict[str, Any]) -> None:
        """Send alert via email."""
        try:
            # This would implement email integration
            self.logger.info(f"Email alert: {alert['message']}")
            
        except Exception as e:
            self.logger.error(f"Error sending email alert: {e}")
    
    async def record_market_data(self, market_data: MarketData) -> None:
        """Record market data metrics."""
        try:
            # Update market data metrics
            if 'market_data' not in self.metrics:
                self.metrics['market_data'] = {
                    'total_updates': 0,
                    'last_update': 0,
                    'symbols': set()
                }
            
            self.metrics['market_data']['total_updates'] += 1
            self.metrics['market_data']['last_update'] = time.time()
            self.metrics['market_data']['symbols'].add(market_data.symbol)
            
        except Exception as e:
            self.logger.error(f"Error recording market data: {e}")
    
    async def record_order_update(self, order: Order) -> None:
        """Record order update metrics."""
        try:
            # Update order metrics
            if 'orders' not in self.metrics:
                self.metrics['orders'] = {
                    'total_orders': 0,
                    'filled_orders': 0,
                    'canceled_orders': 0,
                    'pending_orders': 0
                }
            
            self.metrics['orders']['total_orders'] += 1
            
            if order.status.value in ['FILLED', 'PARTIALLY_FILLED']:
                self.metrics['orders']['filled_orders'] += 1
            elif order.status.value == 'CANCELED':
                self.metrics['orders']['canceled_orders'] += 1
            else:
                self.metrics['orders']['pending_orders'] += 1
            
        except Exception as e:
            self.logger.error(f"Error recording order update: {e}")
    
    async def record_fill(self, fill: Fill) -> None:
        """Record fill metrics."""
        try:
            # Update fill metrics
            if 'fills' not in self.metrics:
                self.metrics['fills'] = {
                    'total_fills': 0,
                    'total_volume': Decimal('0'),
                    'total_fees': Decimal('0')
                }
            
            self.metrics['fills']['total_fills'] += 1
            self.metrics['fills']['total_volume'] += fill.quantity
            self.metrics['fills']['total_fees'] += fill.commission
            
        except Exception as e:
            self.logger.error(f"Error recording fill: {e}")
    
    async def record_risk_event(self, risk_event: RiskEvent) -> None:
        """Record risk event metrics."""
        try:
            # Update risk metrics
            if 'risk_events' not in self.metrics:
                self.metrics['risk_events'] = {
                    'total_events': 0,
                    'by_severity': {},
                    'by_type': {}
                }
            
            self.metrics['risk_events']['total_events'] += 1
            
            # Count by severity
            severity = risk_event.severity
            if severity not in self.metrics['risk_events']['by_severity']:
                self.metrics['risk_events']['by_severity'][severity] = 0
            self.metrics['risk_events']['by_severity'][severity] += 1
            
            # Count by type
            event_type = risk_event.event_type
            if event_type not in self.metrics['risk_events']['by_type']:
                self.metrics['risk_events']['by_type'][event_type] = 0
            self.metrics['risk_events']['by_type'][event_type] += 1
            
        except Exception as e:
            self.logger.error(f"Error recording risk event: {e}")
    
    def get_health_status(self) -> Dict[str, Any]:
        """Get current health status."""
        return self.health_status.copy()
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get current metrics."""
        return {
            'metrics': self.metrics.copy(),
            'performance': {
                'latency': self.performance_metrics['latency'][-10:] if self.performance_metrics['latency'] else [],
                'throughput': self.performance_metrics['throughput'][-10:] if self.performance_metrics['throughput'] else [],
                'error_rate': self.performance_metrics['error_rate'][-10:] if self.performance_metrics['error_rate'] else [],
                'memory_usage': self.performance_metrics['memory_usage'][-10:] if self.performance_metrics['memory_usage'] else [],
                'cpu_usage': self.performance_metrics['cpu_usage'][-10:] if self.performance_metrics['cpu_usage'] else []
            },
            'alerts': self.alerts[-50:],  # Last 50 alerts
            'stats': {
                'metrics_collected': self.metrics_collected,
                'alerts_sent': self.alerts_sent,
                'health_checks': self.health_checks
            }
        }
    
    def get_stats(self) -> Dict[str, Any]:
        """Get monitoring statistics."""
        return {
            'metrics_collected': self.metrics_collected,
            'alerts_sent': self.alerts_sent,
            'health_checks': self.health_checks,
            'active_alerts': len(self.alerts),
            'health_status': self.health_status['overall'],
            'uptime': self.health_status.get('uptime', 0)
        }
