"""
COMPATIBILITY SHIM - Temporary file for backward compatibility

This file maintains imports for legacy code that still references the old
in-memory calendar store. New code should use:
- app/services/calendar_service_real.py for database-backed calendar storage

TODO: Refactor the following files to use calendar_service_real instead:
- app/engine/behavior/spending_pattern_extractor.py
- app/logic/spending_pattern_extractor.py
- app/engine/progress_api.py
- app/engine/progress_logic.py
- app/engine/calendar_state_service.py
- app/engine/challenge_tracker.py
- app/engine/day_view_api.py
- app/api/calendar/services.py
"""
# Re-export from the deprecated module for compatibility
from app.engine.calendar_store_DEPRECATED_DO_NOT_USE import (
    CALENDAR_DB,
    save_calendar,
    get_calendar,
    update_calendar,
    reset_calendar_store,
    get_calendar_for_user,
    save_calendar_for_user,
)

__all__ = [
    'CALENDAR_DB',
    'save_calendar',
    'get_calendar',
    'update_calendar',
    'reset_calendar_store',
    'get_calendar_for_user',
    'save_calendar_for_user',
]
