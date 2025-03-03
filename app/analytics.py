import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from collections import defaultdict
import json
import os
from app.logger import setup_logger
from app.config import settings

logger = setup_logger(__name__)

class Analytics:
    def __init__(self):
        self.command_stats: Dict[str, int] = defaultdict(int)
        self.user_activity: Dict[int, List[datetime]] = defaultdict(list)
        self.error_stats: Dict[str, int] = defaultdict(int)
        self.performance_metrics: Dict[str, List[float]] = defaultdict(list)
        self.last_save = time.time()
        self.save_interval = 300  # 5 minutes
        
        # Load existing data
        self.load_analytics()
    
    def track_command(self, command: str):
        """Track command usage"""
        self.command_stats[command] += 1
        self._auto_save()
    
    def track_user_activity(self, user_id: int):
        """Track user activity"""
        self.user_activity[user_id].append(datetime.now())
        # Keep only last 24 hours
        cutoff = datetime.now() - timedelta(days=1)
        self.user_activity[user_id] = [
            dt for dt in self.user_activity[user_id]
            if dt > cutoff
        ]
        self._auto_save()
    
    def track_error(self, error_type: str):
        """Track error occurrence"""
        self.error_stats[error_type] += 1
        self._auto_save()
    
    def track_performance(self, operation: str, duration: float):
        """Track operation duration"""
        self.performance_metrics[operation].append(duration)
        # Keep only last 1000 measurements
        if len(self.performance_metrics[operation]) > 1000:
            self.performance_metrics[operation] = self.performance_metrics[operation][-1000:]
        self._auto_save()
    
    def get_active_users_24h(self) -> int:
        """Get number of active users in last 24 hours"""
        cutoff = datetime.now() - timedelta(days=1)
        return sum(
            1 for activities in self.user_activity.values()
            if any(dt > cutoff for dt in activities)
        )
    
    def get_popular_commands(self, limit: int = 10) -> List[tuple]:
        """Get most popular commands"""
        return sorted(
            self.command_stats.items(),
            key=lambda x: x[1],
            reverse=True
        )[:limit]
    
    def get_average_performance(self) -> Dict[str, float]:
        """Get average duration for each operation"""
        return {
            op: sum(durations) / len(durations)
            for op, durations in self.performance_metrics.items()
            if durations
        }
    
    def generate_report(self) -> str:
        """Generate analytics report"""
        report = []
        report.append("=== Bot Analytics Report ===")
        
        # Active users
        active_users = self.get_active_users_24h()
        report.append(f"\nActive Users (24h): {active_users}")
        
        # Popular commands
        popular_commands = self.get_popular_commands(5)
        report.append("\nPopular Commands:")
        for cmd, count in popular_commands:
            report.append(f"  {cmd}: {count} uses")
        
        # Error statistics
        report.append("\nError Statistics:")
        for error_type, count in self.error_stats.items():
            report.append(f"  {error_type}: {count} occurrences")
        
        # Performance metrics
        avg_performance = self.get_average_performance()
        report.append("\nAverage Performance:")
        for op, avg_duration in avg_performance.items():
            report.append(f"  {op}: {avg_duration:.3f} seconds")
        
        return "\n".join(report)
    
    def _auto_save(self):
        """Auto-save analytics data periodically"""
        current_time = time.time()
        if current_time - self.last_save > self.save_interval:
            self.save_analytics()
            self.last_save = current_time
    
    def save_analytics(self):
        """Save analytics data to file"""
        try:
            analytics_dir = os.path.join(settings.DATA_DIR, 'analytics')
            os.makedirs(analytics_dir, exist_ok=True)
            
            data = {
                'command_stats': dict(self.command_stats),
                'user_activity': {
                    user_id: [dt.isoformat() for dt in times]
                    for user_id, times in self.user_activity.items()
                },
                'error_stats': dict(self.error_stats),
                'performance_metrics': dict(self.performance_metrics)
            }
            
            file_path = os.path.join(analytics_dir, 'analytics.json')
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            
            logger.debug("Analytics data saved successfully")
            
        except Exception as e:
            logger.error(f"Error saving analytics data: {e}")
    
    def load_analytics(self):
        """Load analytics data from file"""
        try:
            file_path = os.path.join(settings.DATA_DIR, 'analytics', 'analytics.json')
            if not os.path.exists(file_path):
                return
            
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            self.command_stats = defaultdict(int, data.get('command_stats', {}))
            self.user_activity = defaultdict(list, {
                int(user_id): [datetime.fromisoformat(dt) for dt in times]
                for user_id, times in data.get('user_activity', {}).items()
            })
            self.error_stats = defaultdict(int, data.get('error_stats', {}))
            self.performance_metrics = defaultdict(list, data.get('performance_metrics', {}))
            
            logger.debug("Analytics data loaded successfully")
            
        except Exception as e:
            logger.error(f"Error loading analytics data: {e}")

# Create global analytics instance
analytics = Analytics() 