"""
Recurrence Service - Schedule and Throttling Logic
Handles complex recurrence rules, time windows, and throttling
"""
import logging
import random
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta, time as dt_time
try:
    from dateutil.relativedelta import relativedelta
except ImportError:
    # Fallback if dateutil not available
    def relativedelta(*args, **kwargs):
        return timedelta(days=30)  # Simple fallback

logger = logging.getLogger(__name__)


class RecurrenceService:
    """Service for handling recurrence rules and throttling"""
    
    def __init__(self):
        logger.info("RecurrenceService initialized")
    
    def parse_time_window(
        self,
        time_start: Optional[str],
        time_end: Optional[str],
        random_time: bool = False
    ) -> Optional[dt_time]:
        """
        Parse time window and return appropriate time
        If random_time is True, returns a random time within the window
        """
        if not time_start or not time_end:
            return None
        
        try:
            start_hour, start_min = map(int, time_start.split(':'))
            end_hour, end_min = map(int, time_end.split(':'))
            
            start_time = dt_time(start_hour, start_min)
            end_time = dt_time(end_hour, end_min)
            
            if random_time:
                # Generate random time within window
                start_minutes = start_hour * 60 + start_min
                end_minutes = end_hour * 60 + end_min
                random_minutes = random.randint(start_minutes, end_minutes)
                random_hour = random_minutes // 60
                random_min = random_minutes % 60
                return dt_time(random_hour, random_min)
            else:
                # Return start time
                return start_time
        except Exception as e:
            logger.error(f"Error parsing time window: {e}")
            return None
    
    def should_trigger_now(
        self,
        recurrence: Optional[Dict[str, Any]],
        last_triggered: Optional[datetime] = None,
        current_time: Optional[datetime] = None
    ) -> bool:
        """
        Check if a question should be triggered based on recurrence rules
        """
        if not recurrence:
            # No recurrence rule means trigger immediately
            return True
        
        current = current_time or datetime.utcnow()
        frequency = recurrence.get("frequency", "daily")
        
        # Check date range
        start_date = recurrence.get("start_date")
        end_date = recurrence.get("end_date")
        
        if start_date:
            if isinstance(start_date, str):
                start_date = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
            if current < start_date:
                return False
        
        if end_date:
            if isinstance(end_date, str):
                end_date = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
            if current > end_date:
                return False
        
        # Check time window
        time_start = recurrence.get("time_window_start")
        time_end = recurrence.get("time_window_end")
        
        if time_start and time_end:
            try:
                start_hour, start_min = map(int, time_start.split(':'))
                end_hour, end_min = map(int, time_end.split(':'))
                current_time_obj = current.time()
                start_time_obj = dt_time(start_hour, start_min)
                end_time_obj = dt_time(end_hour, end_min)
                
                if not (start_time_obj <= current_time_obj <= end_time_obj):
                    return False
            except Exception as e:
                logger.error(f"Error checking time window: {e}")
        
        # Check day of week filters
        days_of_week = recurrence.get("days_of_week")
        weekends_only = recurrence.get("weekends_only", False)
        
        if weekends_only:
            # 5 = Saturday, 6 = Sunday
            if current.weekday() not in [5, 6]:
                return False
        
        if days_of_week:
            # 0 = Monday, 6 = Sunday
            if current.weekday() not in days_of_week:
                return False
        
        # Check days of month
        days_of_month = recurrence.get("days_of_month")
        if days_of_month:
            if current.day not in days_of_month:
                return False
        
        # Check frequency-based rules
        if not last_triggered:
            # First time, check if we should trigger
            return True
        
        interval = recurrence.get("interval", 1)
        
        if frequency == "daily":
            days_since = (current - last_triggered).days
            return days_since >= interval
        
        elif frequency == "weekly":
            weeks_since = (current - last_triggered).days // 7
            return weeks_since >= interval
        
        elif frequency == "monthly":
            months_since = (current.year - last_triggered.year) * 12 + \
                          (current.month - last_triggered.month)
            return months_since >= interval
        
        elif frequency == "custom":
            # Custom logic can be extended here
            return True
        
        return True
    
    def check_throttle(
        self,
        throttle: Optional[Dict[str, Any]],
        question_id: str,
        answer_history: List[Dict[str, Any]]
    ) -> bool:
        """
        Check if question should be throttled based on answer history
        Returns True if question should be asked (not throttled)
        """
        if not throttle:
            return True
        
        max_count = throttle.get("max_count", 1)
        within_hours = throttle.get("within_hours")
        within_days = throttle.get("within_days")
        
        # Filter answer history by time window
        now = datetime.utcnow()
        relevant_answers = []
        
        for answer in answer_history:
            if answer.get("question_id") != question_id:
                continue
            
            answer_time = answer.get("timestamp")
            if isinstance(answer_time, str):
                answer_time = datetime.fromisoformat(answer_time.replace('Z', '+00:00'))
            
            if within_hours:
                time_diff = (now - answer_time).total_seconds() / 3600
                if time_diff <= within_hours:
                    relevant_answers.append(answer)
            elif within_days:
                time_diff = (now - answer_time).days
                if time_diff <= within_days:
                    relevant_answers.append(answer)
            else:
                # No time window, count all answers
                relevant_answers.append(answer)
        
        # Check if we've exceeded the limit
        return len(relevant_answers) < max_count
    
    def get_next_trigger_time(
        self,
        recurrence: Optional[Dict[str, Any]],
        last_triggered: Optional[datetime] = None
    ) -> Optional[datetime]:
        """
        Calculate the next time a question should be triggered
        """
        if not recurrence:
            return None
        
        current = datetime.utcnow()
        frequency = recurrence.get("frequency", "daily")
        interval = recurrence.get("interval", 1)
        
        # Parse time window
        time_start = recurrence.get("time_window_start")
        time_end = recurrence.get("time_window_end")
        random_time = recurrence.get("random_time", False)
        
        time_obj = None
        if time_start and time_end:
            time_obj = self.parse_time_window(time_start, time_end, random_time)
        
        if frequency == "daily":
            next_date = current + timedelta(days=interval)
        elif frequency == "weekly":
            next_date = current + timedelta(weeks=interval)
        elif frequency == "monthly":
            next_date = current + relativedelta(months=interval)
        else:
            return None
        
        if time_obj:
            next_date = next_date.replace(hour=time_obj.hour, minute=time_obj.minute, second=0, microsecond=0)
        
        return next_date

