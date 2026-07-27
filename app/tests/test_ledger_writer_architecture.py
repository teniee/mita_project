"""Architectural guard: only the ledger service may write Transaction rows.

A Transaction row and the DailyPlan allocations it implies must move
together, under one advisory lock and one commit. Four production paths once
built a Transaction and committed it themselves; each silently skipped
redistribution, so the transaction list and the daily plan disagreed and
nothing failed loudly.

Comments and review do not survive contact with a new endpoint. This test
walks the production AST and fails when a module that is not part of the
sanctioned ledger implementation both constructs a Transaction and hands it
to a Session.

If you are adding a legitimate writer: call
app.services.core.engine.expense_tracker.commit_transaction_to_ledger()
instead of db.add(...) + db.commit(). If you are extending the ledger
implementation itself, add the module to CANONICAL_LEDGER_MODULES below and
say why in the commit message.
"""

import ast
import pathlib

import pytest

APP_ROOT = pathlib.Path(__file__).resolve().parents[1]

# The ledger implementation itself. These modules are allowed to construct a
# Transaction and persist it because they *are* the canonical path.
CANONICAL_LEDGER_MODULES = {
    "services/core/engine/expense_tracker.py",  # commit_transaction_to_ledger
    "services/expense_tracker.py",  # legacy record_expense -> canonical
    "api/transactions/services.py",  # create/update/soft-delete
    "services/core/engine/cron_task_scheduled_expenses.py",  # scheduled writer
}

# Directories that are not production request paths.
EXCLUDED_DIR_PARTS = {
    "tests",
    "__pycache__",
    "migrations",
    "alembic",
}

# Model definitions declare the class; they never persist rows.
EXCLUDED_FILES = {
    "db/models/transaction.py",
}


def _production_modules():
    for path in sorted(APP_ROOT.rglob("*.py")):
        rel = path.relative_to(APP_ROOT)
        if set(rel.parts) & EXCLUDED_DIR_PARTS:
            continue
        if rel.as_posix() in EXCLUDED_FILES:
            continue
        if rel.as_posix() in CANONICAL_LEDGER_MODULES:
            continue
        yield rel, path


class _WriterVisitor(ast.NodeVisitor):
    """Collect `<session>.add(Transaction(...))` and `.add(<txn-ish var>)`."""

    def __init__(self):
        self.transaction_vars = set()
        self.violations = []

    def visit_Assign(self, node):
        # txn = Transaction(...)
        if (
            isinstance(node.value, ast.Call)
            and isinstance(node.value.func, ast.Name)
            and node.value.func.id == "Transaction"
        ):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    self.transaction_vars.add(target.id)
        self.generic_visit(node)

    def visit_Call(self, node):
        func = node.func
        if isinstance(func, ast.Attribute) and func.attr == "add" and node.args:
            arg = node.args[0]
            direct = (
                isinstance(arg, ast.Call)
                and isinstance(arg.func, ast.Name)
                and arg.func.id == "Transaction"
            )
            via_var = isinstance(arg, ast.Name) and arg.id in self.transaction_vars
            if direct or via_var:
                self.violations.append(node.lineno)
        self.generic_visit(node)


def _violations_in(path):
    tree = ast.parse(path.read_text(), filename=str(path))
    visitor = _WriterVisitor()
    visitor.visit(tree)
    return visitor.violations


def test_no_production_module_persists_transactions_directly():
    offenders = []
    for rel, path in _production_modules():
        for lineno in _violations_in(path):
            offenders.append(f"app/{rel.as_posix()}:{lineno}")

    assert not offenders, (
        "These production modules add a Transaction to a Session directly, "
        "bypassing the canonical ledger service. Each such writer records "
        "spend that the daily plan, redistribution and every alert never "
        "see:\n  "
        + "\n  ".join(offenders)
        + "\n\nUse commit_transaction_to_ledger() instead, or add the module "
        "to CANONICAL_LEDGER_MODULES if it is genuinely part of the ledger."
    )


def test_guard_detects_a_direct_writer(tmp_path):
    """The guard must actually catch the pattern it claims to catch."""
    offending = tmp_path / "rogue_endpoint.py"
    offending.write_text(
        "from app.db.models import Transaction\n"
        "def handler(db, user):\n"
        "    txn = Transaction(user_id=user.id, amount=1)\n"
        "    db.add(txn)\n"
        "    db.commit()\n"
    )
    assert _violations_in(offending) == [4]

    inline = tmp_path / "rogue_inline.py"
    inline.write_text(
        "def handler(db, user):\n"
        "    db.add(Transaction(user_id=user.id, amount=1))\n"
    )
    assert _violations_in(inline) == [2]


def test_canonical_modules_are_all_real_files():
    """A stale allow-list entry would silently widen the guard."""
    missing = [
        name for name in CANONICAL_LEDGER_MODULES if not (APP_ROOT / name).is_file()
    ]
    assert not missing, f"CANONICAL_LEDGER_MODULES refers to missing files: {missing}"


@pytest.mark.parametrize("module", sorted(CANONICAL_LEDGER_MODULES))
def test_canonical_modules_are_narrow(module):
    """Each allow-listed module must genuinely touch the ledger service."""
    text = (APP_ROOT / module).read_text()
    assert (
        "commit_transaction_to_ledger" in text
        or "apply_transaction_to_plan" in text
        or "rebuild_month_plan" in text
    ), (
        f"{module} is allow-listed as canonical but never references the "
        "ledger service - it should not be exempt."
    )
