"""
MIGRATION COMPLETE ✅

All files have been successfully migrated to calendar_service_real.py for
database-backed calendar storage.

Migrated files (2025-12-29):
- app/engine/behavior/spending_pattern_extractor.py ✅
- app/logic/spending_pattern_extractor.py ✅
- app/engine/progress_api.py ✅
- app/engine/progress_logic.py ✅
- app/engine/calendar_state_service.py ✅
- app/engine/challenge_tracker.py ✅
- app/engine/day_view_api.py ✅
- app/api/calendar/services.py ✅

This compatibility shim is no longer needed and can be removed.
The deprecated implementation has been deleted.

All calendar operations now use PostgreSQL-backed storage via:
- app/services/calendar_service_real.py
"""

# NOTE: This file is kept for reference only.
# No code imports from here anymore.
# The deprecated module has been deleted.

__all__ = [
    'CALENDAR_DB',
    'save_calendar',
    'get_calendar',
    'update_calendar',
    'reset_calendar_store',
    'get_calendar_for_user',
    'save_calendar_for_user',
]
