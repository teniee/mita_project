"""What the mobile forecast holds for bills it cannot link (PR #288 review G0-01).

``obligation_lines.paid_without_linking``: on a surface whose user cannot link
an expense to a saved payment (the mobile app), each identified line counts
what linked expenses paid or what is recorded on the line, whichever is more.
The forecast then holds ``need − paid`` per line (``_still_reserved``).

* In a month that keeps obligations under their categories (legacy, every
  month the app laid out), ``need`` is the line's whole base: the bill plus the
  category's other money. Unrelated spending in that category therefore uses
  the category's own money first and cannot release the bill until it
  exceeds it.
* In a month laid out in ChatGPT (keyed), a bill's own line holds only linked
  payments, so category spending never settles it.

Exact, hand-checkable figures; no database.
"""

from datetime import date
from decimal import Decimal
from uuid import uuid4

from app.services.core.engine.budget_forecast_engine import _still_reserved
from app.services.monthly_obligations import DueOccurrence
from app.services.obligation_lines import (
    bill_key,
    commitments_for,
    paid_without_linking,
)

D = Decimal


def due(category: str, amount: str, day: int, obligation=None) -> DueOccurrence:
    return DueOccurrence(
        obligation_id=obligation or uuid4(),
        day=date(2026, 11, day),
        category=category,
        amount=D(amount),
        merchant=None,
        recurrence="monthly",
        scheduled_from=date(2026, 11, day),
    )


def held(occurrences, base, recorded, linked=None, keyed=False) -> Decimal:
    """What the mobile forecast holds back for the month's bills."""
    commitments = commitments_for(occurrences, linked or {}, base, keyed)
    paid = paid_without_linking(commitments, recorded)
    return _still_reserved([], commitments.needs, paid)


def test_a_bill_paid_in_the_app_is_released_once():
    rent = [due("rent", "800.00", 1)]
    base = {"rent": D("800.00")}
    assert held(rent, base, {}) == D("800.00")  # not paid yet
    assert held(rent, base, {"rent": D("800.00")}) == D("0.00")  # paid in the app
    assert held(rent, base, {"rent": D("900.00")}) == D("0.00")  # more is spending


def test_a_partial_payment_releases_only_what_was_paid():
    rent = [due("rent", "800.00", 1)]
    assert held(rent, {"rent": D("800.00")}, {"rent": D("400.00")}) == D("400.00")


def test_unrelated_spending_in_the_same_category_never_releases_the_bill():
    """Transportation: 100.00 of everyday money and a 270.00 car loan on the
    15th on the same legacy line (370.00). A 60.00 car part leaves 310.00
    held — the whole loan and the 40.00 of everyday money not yet spent."""
    loan = [due("transportation", "270.00", 15)]
    base = {"transportation": D("370.00")}
    assert held(loan, base, {"transportation": D("60.00")}) == D("310.00")
    assert held(loan, base, {"transportation": D("100.00")}) == D("270.00")
    # only spending beyond the category's own money reaches the bill
    assert held(loan, base, {"transportation": D("130.00")}) == D("240.00")


def test_several_obligations_in_one_category_stay_held_until_paid():
    """Car loan 270.00 and scooter 50.00, both transportation, with 100.00 of
    everyday money (420.00). The loan paid in the app: the scooter and the
    unspent everyday money stay held (150.00); never less than the scooter."""
    bills = [due("transportation", "270.00", 15), due("transportation", "50.00", 20)]
    base = {"transportation": D("420.00")}
    assert held(bills, base, {"transportation": D("270.00")}) == D("150.00")
    assert held(bills, base, {"transportation": D("370.00")}) == D("50.00")
    assert held(bills, base, {"transportation": D("420.00")}) == D("0.00")


def test_a_month_laid_out_in_chatgpt_settles_a_bill_only_by_its_link():
    """Keyed month: the loan's own line holds only linked payments. Spending
    on the category line (60.00, even 270.00) never settles it; a linked
    270.00 does, recorded on its line or paid early in October."""
    loan_id = uuid4()
    line = bill_key(loan_id)
    loan = [due("transportation", "270.00", 15, loan_id)]
    base = {line: D("270.00"), "transportation": D("100.00")}
    assert held(loan, base, {"transportation": D("270.00")}, keyed=True) == D("270.00")
    assert held(loan, base, {line: D("270.00")}, keyed=True) == D("0.00")
    early = {(loan_id, date(2026, 11, 15)): D("270.00")}  # recorded in October
    assert held(loan, base, {}, linked=early, keyed=True) == D("0.00")


def test_never_more_held_than_chatgpt_holds():
    """The mobile figure counts linked payments too: a payment linked in
    ChatGPT but recorded in another month still settles its due date."""
    rent_id = uuid4()
    rent = [due("rent", "800.00", 1, rent_id)]
    linked = {(rent_id, date(2026, 11, 1)): D("800.00")}
    assert held(rent, {"rent": D("800.00")}, {}, linked=linked) == D("0.00")


def test_known_limit_a_bill_only_category_takes_any_purchase_in_it():
    """Pinned limit, not a goal. A category whose line holds nothing but the
    bill (utilities 45.00) cannot tell a 20.00 lamp from a part payment on a
    surface without links: 25.00 stays held. It is bounded by the unrelated
    amount, it is R3's rule from before 2.7.0, and linking in ChatGPT is
    exact (scheduled-obligations-safety.md → Limits)."""
    bill = [due("utilities", "45.00", 5)]
    assert held(bill, {"utilities": D("45.00")}, {"utilities": D("20.00")}) == D(
        "25.00"
    )
