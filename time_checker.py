import datetime
import pytz
from logger_config import logger

def is_within_schedule(schedule_data):
    """
    Checks if current time in given timezone is within the schedule.
    schedule_data format:
    {
        "start_time": "08:00",
        "stop_time": "18:00",
        "timezone": "Europe/London",
        "enabled": True
    }
    """
    if not schedule_data:
        logger.warning("Schedule data is empty.")
        return False
        
    enabled = schedule_data.get("enabled", False)
    if isinstance(enabled, str):
        enabled = enabled.lower() == 'true'
        
    if not enabled:
        logger.info("Schedule is marked as enabled=False.")
        return False
        
    start_time_str = schedule_data.get("start_time", "08:00")
    stop_time_str = schedule_data.get("stop_time", "18:00")
    timezone_str = schedule_data.get("timezone", "Europe/London")
    
    try:
        tz = pytz.timezone(timezone_str)
        now = datetime.datetime.now(tz)
        
        start_time = datetime.datetime.strptime(start_time_str, "%H:%M").time()
        stop_time = datetime.datetime.strptime(stop_time_str, "%H:%M").time()
        
        current_time = now.time()
        
        if start_time <= stop_time:
            is_active = start_time <= current_time <= stop_time
        else:
            # Handle overnight schedules
            is_active = current_time >= start_time or current_time <= stop_time
            
        logger.info(f"Time Check -> Current UK Time: {current_time.strftime('%H:%M')} | Schedule: {start_time_str} to {stop_time_str} | Active? {is_active}")
        return is_active
            
    except Exception as e:
        logger.error(f"Error checking time against schedule: {str(e)}")
        return False
