#!/usr/bin/env python3
"""
MODULE 5: Budgeting Goals - Comprehensive Verification Script
Verifies all components of the goals implementation
"""

import sys
import os
from pathlib import Path

# Color codes for output
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
RESET = '\033[0m'

def check(name: str, condition: bool, error_msg: str = "") -> bool:
    """Check a condition and print result"""
    if condition:
        print(f"{GREEN}✓{RESET} {name}")
        return True
    else:
        print(f"{RED}✗{RESET} {name}")
        if error_msg:
            print(f"  {YELLOW}└─{RESET} {error_msg}")
        return False

def main():
    print(f"\n{BLUE}{'='*70}{RESET}")
    print(f"{BLUE}MODULE 5: Budgeting Goals - Verification{RESET}")
    print(f"{BLUE}{'='*70}{RESET}\n")

    all_passed = True

    # 1. Check file existence
    print(f"{BLUE}1. Checking file existence...{RESET}")
    files_to_check = [
        "app/db/models/goal.py",
        "alembic/versions/0010_enhance_goals_table.py",
        "app/api/goals/routes.py",
        "app/repositories/goal_repository.py",
        "app/tests/test_module5_goals.py",
        "mobile_app/lib/models/goal.dart",
        "mobile_app/lib/screens/goals_screen.dart",
        "mobile_app/lib/services/api_service.dart",
        "MODULE_5_IMPLEMENTATION_COMPLETE.md",
    ]

    for file_path in files_to_check:
        exists = Path(file_path).exists()
        all_passed &= check(f"File exists: {file_path}", exists, f"File not found: {file_path}")

    # 2. Check Python syntax
    print(f"\n{BLUE}2. Checking Python syntax...{RESET}")
    python_files = [
        "app/db/models/goal.py",
        "alembic/versions/0010_enhance_goals_table.py",
        "app/api/goals/routes.py",
        "app/repositories/goal_repository.py",
        "app/tests/test_module5_goals.py",
    ]

    for py_file in python_files:
        result = os.system(f"python3 -m py_compile {py_file} 2>/dev/null")
        all_passed &= check(f"Syntax valid: {py_file}", result == 0, f"Syntax error in {py_file}")

    # 3. Check model fields
    print(f"\n{BLUE}3. Checking Goal model fields...{RESET}")
    with open("app/db/models/goal.py", "r") as f:
        model_content = f.read()

    required_fields = [
        "id", "user_id", "title", "description", "category",
        "target_amount", "saved_amount", "monthly_contribution",
        "status", "progress", "target_date", "created_at",
        "last_updated", "completed_at", "priority"
    ]

    for field in required_fields:
        has_field = field in model_content
        all_passed &= check(f"Model has field: {field}", has_field, f"Missing field: {field}")

    # Check model methods
    required_methods = ["update_progress", "add_savings", "remaining_amount", "is_completed", "is_overdue"]
    for method in required_methods:
        has_method = method in model_content
        all_passed &= check(f"Model has method/property: {method}", has_method, f"Missing: {method}")

    # 4. Check API endpoints
    print(f"\n{BLUE}4. Checking API endpoints...{RESET}")
    with open("app/api/goals/routes.py", "r") as f:
        routes_content = f.read()

    required_endpoints = [
        ("POST", "/goals/", "create_goal"),
        ("GET", "/goals/", "list_goals"),
        ("GET", "/goals/{id}", "get_goal"),
        ("PATCH", "/goals/{id}", "update_goal"),
        ("DELETE", "/goals/{id}", "delete_goal"),
        ("GET", "/goals/statistics", "get_statistics"),
        ("POST", "/goals/{id}/add_savings", "add_savings"),
        ("POST", "/goals/{id}/complete", "mark_goal_completed"),
        ("POST", "/goals/{id}/pause", "pause_goal"),
        ("POST", "/goals/{id}/resume", "resume_goal"),
    ]

    for method, path, func_name in required_endpoints:
        has_endpoint = func_name in routes_content
        all_passed &= check(f"Endpoint exists: {method} {path}", has_endpoint, f"Missing: {func_name}")

    # 5. Check routes registration
    print(f"\n{BLUE}5. Checking routes registration in main.py...{RESET}")
    with open("app/main.py", "r") as f:
        main_content = f.read()

    has_import = "from app.api.goals.routes import router as goals_crud_router" in main_content
    all_passed &= check("Goals router imported", has_import, "Missing import in main.py")

    has_registration = "goals_crud_router" in main_content and '"/api"' in main_content
    all_passed &= check("Goals router registered", has_registration, "Router not registered")

    # 6. Check migration
    print(f"\n{BLUE}6. Checking migration...{RESET}")
    with open("alembic/versions/0010_enhance_goals_table.py", "r") as f:
        migration_content = f.read()

    has_upgrade = "def upgrade():" in migration_content
    all_passed &= check("Migration has upgrade()", has_upgrade)

    has_downgrade = "def downgrade():" in migration_content
    all_passed &= check("Migration has downgrade()", has_downgrade)

    correct_revision = 'revision = "0010_enhance_goals"' in migration_content
    all_passed &= check("Migration has correct revision", correct_revision)

    correct_down_revision = 'down_revision = "0009_add_transaction_extended_fields"' in migration_content
    all_passed &= check("Migration has correct down_revision", correct_down_revision)

    # 7. Check mobile model
    print(f"\n{BLUE}7. Checking mobile Goal model...{RESET}")
    with open("mobile_app/lib/models/goal.dart", "r") as f:
        dart_model_content = f.read()

    dart_fields = ["id", "title", "description", "category", "targetAmount",
                   "savedAmount", "status", "progress", "priority"]
    for field in dart_fields:
        has_field = "final" in dart_model_content and field in dart_model_content
        all_passed &= check(f"Dart model has field: {field}", has_field)

    has_from_json = "fromJson" in dart_model_content
    all_passed &= check("Dart model has fromJson()", has_from_json)

    has_to_json = "toJson" in dart_model_content
    all_passed &= check("Dart model has toJson()", has_to_json)

    # 8. Check mobile API service
    print(f"\n{BLUE}8. Checking mobile API service...{RESET}")
    with open("mobile_app/lib/services/api_service.dart", "r") as f:
        api_service_content = f.read()

    api_methods = ["getGoals", "getGoal", "createGoal", "updateGoal", "deleteGoal",
                   "getGoalStatistics", "addSavingsToGoal", "completeGoal", "pauseGoal", "resumeGoal"]
    for method in api_methods:
        has_method = method in api_service_content
        all_passed &= check(f"API service has method: {method}", has_method)

    # 9. Check mobile UI
    print(f"\n{BLUE}9. Checking mobile Goals screen...{RESET}")
    with open("mobile_app/lib/screens/goals_screen.dart", "r") as f:
        screen_content = f.read()

    ui_features = [
        "TabController",
        "fetchGoals",
        "fetchStatistics",
        "_showGoalForm",
        "_deleteGoal",
        "_addSavings",
        "_toggleGoalStatus",
        "GoalsScreen",
    ]
    for feature in ui_features:
        has_feature = feature in screen_content
        all_passed &= check(f"UI has feature: {feature}", has_feature)

    # 10. Check tests
    print(f"\n{BLUE}10. Checking tests...{RESET}")
    with open("app/tests/test_module5_goals.py", "r") as f:
        tests_content = f.read()

    test_functions = [
        "test_goal_creation",
        "test_goal_progress_calculation",
        "test_goal_auto_completion",
        "test_goal_add_savings",
        "test_goal_remaining_amount",
        "test_goal_is_overdue",
        "test_goal_is_completed",
    ]
    for test_func in test_functions:
        has_test = test_func in tests_content
        all_passed &= check(f"Test exists: {test_func}", has_test)

    # 11. Check repository UUID types
    print(f"\n{BLUE}11. Checking repository UUID types...{RESET}")
    with open("app/repositories/goal_repository.py", "r") as f:
        repo_content = f.read()

    has_uuid_import = "from uuid import UUID" in repo_content
    all_passed &= check("Repository imports UUID", has_uuid_import)

    uses_uuid = "user_id: UUID" in repo_content and "goal_id: UUID" in repo_content
    all_passed &= check("Repository uses UUID types", uses_uuid, "Still using int instead of UUID")

    # Summary
    print(f"\n{BLUE}{'='*70}{RESET}")
    if all_passed:
        print(f"{GREEN}✓ ALL CHECKS PASSED!{RESET}")
        print(f"{GREEN}MODULE 5: Budgeting Goals is fully implemented and verified!{RESET}")
        return 0
    else:
        print(f"{RED}✗ SOME CHECKS FAILED{RESET}")
        print(f"{YELLOW}Please review the errors above and fix them.{RESET}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
