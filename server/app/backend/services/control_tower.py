"""
Server Control Tower - Central monitoring and management hub for all TradeAdviser operations.

The Control Tower:
- Monitors system health (CPU, memory, disk, network, database, brokers)
- Manages trading sessions and broker connections
- Feeds real-time data to desktop AI agents
- Provides alerts and recommendations
- Maintains audit trails and compliance logs
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List

import psutil
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


class ControlTowerMetrics:
    """Real-time system metrics."""

    def __init__(self):
        self.timestamp = datetime.now()
        self.cpu_percent = 0.0
        self.memory_percent = 0.0
        self.disk_percent = 0.0
        self.active_sessions = 0
        self.active_brokers = 0
        self.pending_trades = 0
        self.database_latency_ms = 0.0
        self.api_latency_ms = 0.0
        self.ws_connections = 0
        self.alerts: List[Dict[str, Any]] = []

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp.isoformat(),
            "cpu_percent": round(self.cpu_percent, 2),
            "memory_percent": round(self.memory_percent, 2),
            "disk_percent": round(self.disk_percent, 2),
            "active_sessions": self.active_sessions,
            "active_brokers": self.active_brokers,
            "pending_trades": self.pending_trades,
            "database_latency_ms": round(self.database_latency_ms, 2),
            "api_latency_ms": round(self.api_latency_ms, 2),
            "ws_connections": self.ws_connections,
            "alerts": self.alerts,
            "health_status": self._calculate_health_status(),
        }

    def _calculate_health_status(self) -> str:
        """Calculate overall health status based on metrics."""
        if self.cpu_percent > 90 or self.memory_percent > 90 or self.disk_percent > 90:
            return "critical"
        elif self.cpu_percent > 75 or self.memory_percent > 75:
            return "warning"
        elif self.alerts:
            return "attention"
        else:
            return "healthy"


class ControlTower:
    """Central control tower for monitoring and managing all TradeAdviser systems."""

    def __init__(self, db: Session | None = None):
        self.db = db
        self.metrics = ControlTowerMetrics()
        self.session_manager: Dict[str, Dict[str, Any]] = {}
        self.broker_connections: Dict[str, Dict[str, Any]] = {}
        self.trade_queue: List[Dict[str, Any]] = []
        self.alerts_history: List[Dict[str, Any]] = []
        self.start_time = datetime.now()

    def get_system_metrics(self) -> ControlTowerMetrics:
        """Collect and return current system metrics."""
        try:
            # CPU metrics
            self.metrics.cpu_percent = psutil.cpu_percent(interval=0.1)

            # Memory metrics
            memory = psutil.virtual_memory()
            self.metrics.memory_percent = memory.percent

            # Disk metrics
            disk = psutil.disk_usage("/")
            self.metrics.disk_percent = disk.percent

            self.metrics.timestamp = datetime.now()

            # Check for alerts
            self._check_alerts()
        except Exception as exc:
            logger.warning("Error collecting system metrics: %s", exc)

        return self.metrics

    def _check_alerts(self) -> None:
        """Check system status and generate alerts."""
        self.metrics.alerts = []

        if self.metrics.cpu_percent > 85:
            self.metrics.alerts.append({
                "type": "cpu_high",
                "severity": "warning" if self.metrics.cpu_percent < 95 else "critical",
                "message": f"CPU usage at {self.metrics.cpu_percent}%",
                "timestamp": datetime.now().isoformat(),
            })

        if self.metrics.memory_percent > 85:
            self.metrics.alerts.append({
                "type": "memory_high",
                "severity": "warning" if self.metrics.memory_percent < 95 else "critical",
                "message": f"Memory usage at {self.metrics.memory_percent}%",
                "timestamp": datetime.now().isoformat(),
            })

        if self.metrics.disk_percent > 90:
            self.metrics.alerts.append({
                "type": "disk_full",
                "severity": "critical",
                "message": f"Disk usage at {self.metrics.disk_percent}%",
                "timestamp": datetime.now().isoformat(),
            })

        if self.metrics.database_latency_ms > 1000:
            self.metrics.alerts.append({
                "type": "database_slow",
                "severity": "warning",
                "message": f"Database latency: {self.metrics.database_latency_ms}ms",
                "timestamp": datetime.now().isoformat(),
            })

        if self.metrics.api_latency_ms > 5000:
            self.metrics.alerts.append({
                "type": "api_slow",
                "severity": "warning",
                "message": f"API latency: {self.metrics.api_latency_ms}ms",
                "timestamp": datetime.now().isoformat(),
            })

    def register_session(self, session_id: str, user_id: str, broker: str) -> None:
        """Register a new trading session."""
        self.session_manager[session_id] = {
            "session_id": session_id,
            "user_id": user_id,
            "broker": broker,
            "started_at": datetime.now().isoformat(),
            "status": "active",
            "trades": 0,
            "pnl": 0.0,
        }
        self.metrics.active_sessions = len(self.session_manager)
        logger.info("Session registered: %s for user %s", session_id, user_id)

    def unregister_session(self, session_id: str) -> None:
        """Unregister a trading session."""
        if session_id in self.session_manager:
            session = self.session_manager.pop(session_id)
            session["status"] = "closed"
            session["closed_at"] = datetime.utcnow().isoformat()
            self.metrics.active_sessions = len(self.session_manager)
            logger.info("Session closed: %s", session_id)

    def register_broker(self, broker_id: str, broker_type: str, status: str = "connected") -> None:
        """Register a broker connection."""
        self.broker_connections[broker_id] = {
            "broker_id": broker_id,
            "type": broker_type,
            "status": status,
            "connected_at": datetime.utcnow().isoformat(),
            "markets": 0,
            "last_heartbeat": datetime.utcnow().isoformat(),
        }
        self.metrics.active_brokers = len([b for b in self.broker_connections.values() if b["status"] == "connected"])
        logger.info("Broker registered: %s (%s)", broker_id, broker_type)

    def update_broker_status(self, broker_id: str, status: str) -> None:
        """Update broker connection status."""
        if broker_id in self.broker_connections:
            self.broker_connections[broker_id]["status"] = status
            self.broker_connections[broker_id]["last_heartbeat"] = datetime.utcnow().isoformat()
            self.metrics.active_brokers = len([b for b in self.broker_connections.values() if b["status"] == "connected"])

    def queue_trade(self, trade_data: Dict[str, Any]) -> None:
        """Queue a trade for processing."""
        trade_data["queued_at"] = datetime.utcnow().isoformat()
        trade_data["status"] = "pending"
        self.trade_queue.append(trade_data)
        self.metrics.pending_trades = len([t for t in self.trade_queue if t["status"] == "pending"])

    def process_trade(self, trade_id: str, status: str = "executed") -> None:
        """Mark trade as processed."""
        for trade in self.trade_queue:
            if trade.get("trade_id") == trade_id:
                trade["status"] = status
                trade["processed_at"] = datetime.utcnow().isoformat()
                break
        self.metrics.pending_trades = len([t for t in self.trade_queue if t["status"] == "pending"])

    def get_dashboard_snapshot(self) -> Dict[str, Any]:
        """Get comprehensive control tower dashboard snapshot."""
        metrics = self.get_system_metrics()
        uptime_seconds = (datetime.utcnow() - self.start_time).total_seconds()

        return {
            "timestamp": datetime.utcnow().isoformat(),
            "uptime_seconds": uptime_seconds,
            "uptime_formatted": self._format_uptime(uptime_seconds),
            "health_status": metrics._calculate_health_status(),
            "metrics": metrics.to_dict(),
            "sessions": {
                "active": len(self.session_manager),
                "list": list(self.session_manager.values()),
            },
            "brokers": {
                "connected": len([b for b in self.broker_connections.values() if b["status"] == "connected"]),
                "total": len(self.broker_connections),
                "list": list(self.broker_connections.values()),
            },
            "trades": {
                "pending": len([t for t in self.trade_queue if t["status"] == "pending"]),
                "total": len(self.trade_queue),
                "recent": self.trade_queue[-10:],  # Last 10 trades
            },
            "alerts": {
                "active": metrics.alerts,
                "total": len(self.alerts_history),
            },
        }

    def get_desktop_ai_feed(self) -> Dict[str, Any]:
        """Get data feed for desktop AI agents."""
        metrics = self.get_system_metrics()

        return {
            "timestamp": datetime.utcnow().isoformat(),
            "source": "server_control_tower",
            "system": {
                "health": metrics._calculate_health_status(),
                "cpu_percent": metrics.cpu_percent,
                "memory_percent": metrics.memory_percent,
                "disk_percent": metrics.disk_percent,
            },
            "trading": {
                "active_sessions": metrics.active_sessions,
                "active_brokers": metrics.active_brokers,
                "pending_trades": metrics.pending_trades,
            },
            "alerts": metrics.alerts,
            "recommendations": self._generate_recommendations(),
        }

    def _generate_recommendations(self) -> List[Dict[str, Any]]:
        """Generate AI recommendations based on current state."""
        recommendations = []

        if self.metrics.cpu_percent > 80:
            recommendations.append({
                "type": "system",
                "priority": "high",
                "action": "reduce_load",
                "message": "System CPU high. Consider pausing non-critical operations.",
            })

        if self.metrics.pending_trades > 100:
            recommendations.append({
                "type": "trading",
                "priority": "medium",
                "action": "process_queue",
                "message": f"Trade queue at {self.metrics.pending_trades}. Prioritize execution.",
            })

        if len([b for b in self.broker_connections.values() if b["status"] != "connected"]) > 0:
            recommendations.append({
                "type": "broker",
                "priority": "high",
                "action": "reconnect_brokers",
                "message": "Some brokers disconnected. Attempt reconnection.",
            })

        return recommendations

    @staticmethod
    def _format_uptime(seconds: float) -> str:
        """Format uptime as human-readable string."""
        hours, remainder = divmod(int(seconds), 3600)
        minutes, seconds = divmod(remainder, 60)
        return f"{hours}h {minutes}m {seconds}s"


# Global control tower instance
_control_tower: ControlTower | None = None


def get_control_tower(db: Session | None = None) -> ControlTower:
    """Get or create the global control tower instance."""
    global _control_tower
    if _control_tower is None:
        _control_tower = ControlTower(db=db)
    return _control_tower
