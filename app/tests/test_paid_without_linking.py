"""What the mobile forecast holds for bills it cannot link (PR #288 review G0-01).

``obligation_lines.paid_without_linking``, then the forecast holds
``need − paid`` per bill line (``_still_reserved``). The rule:
ordinary spending never releases a saved bill.

* **Rent, mortgage, utilities in a month the app laid out.** The category is
  the bill (R3): what is recorded on it pays it. A rent paid in the app is
  spent once, never also held.
* **Any other saved payment** (a loan, a subscription, insurance) is paid only
  by a link. Spending on its line uses only the line's everyday money.
* **A line laid out in ChatGPT** holds exactly ChatGPT's linked figure.

The independent review of the first version (crediting all spending on the
line) found an unpaid 270.00 car loan released by 150.00 of fuel. Its exact
cases are pinned here and through the real route in
``test_budget_forecast_local_day.py``. No database.
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


# --- rent, mortgage, utilities: only a link pays a saved bill there too -----------


def test_a_saved_rent_is_paid_only_by_a_link():
    """Pinned open owner decision (G0-01): a saved rent paid in the app without
    a link stays held — the app shows less to spend, never more. A link pays
    it; a part link pays a part."""
    rent_id = uuid4()
    rent = [due("rent", "800.00", 1, rent_id)]
    base = {"rent": D("800.00")}
    assert held(rent, base, {}) == D("800.00")
    assert held(rent, base, {"rent": D("800.00")}) == D("800.00")  # owner decision
    full = {(rent_id, date(2026, 11, 1)): D("800.00")}
    part = {(rent_id, date(2026, 11, 1)): D("400.00")}
    assert held(rent, base, {"rent": D("800.00")}, full) == D("0.00")
    assert held(rent, base, {"rent": D("400.00")}, part) == D("400.00")


def test_electricity_never_releases_a_saved_internet_bill():
    """Second review, N2: utilities 150.00 of other money, internet 45.00
    saved in the app and unpaid, 150.00 of electricity paid: 45.00 held."""
    internet = [due("utilities", "45.00", 5)]
    base = {"utilities": D("150.00")}
    assert held(internet, base, {"utilities": D("150.00")}) == D("45.00")


def test_last_month_s_late_rent_never_pays_this_month_s():
    """Second review, N3: November's rent paid on 2 December (linked to
    November) is on December's line; December's 800.00 stays held."""
    rent = [due("rent", "800.00", 1)]
    assert held(rent, {"rent": D("800.00")}, {"rent": D("800.00")}) == D("800.00")


# --- any other saved payment: only a link releases it ---------------------------


def test_fuel_never_releases_a_car_loan_saved_after_the_month_was_laid_out():
    """The review's case: transport 5.00 a day (150.00), a 270.00 car loan
    scheduled in the app afterwards (base < due), 150.00 of fuel. The loan
    stays held in full; the fuel came from transport's own money."""
    loan = [due("transportation", "270.00", 25)]
    base = {"transportation": D("150.00")}
    assert held(loan, base, {"transportation": D("150.00")}) == D("270.00")
    assert held(loan, base, {"transportation": D("420.00")}) == D("270.00")


def test_a_lamp_never_releases_a_laptop_loan():
    """The review's second case: a 70.00 laptop loan under 'other', with no
    other 'other' money, and a 70.00 lamp."""
    loan = [due("other", "70.00", 25)]
    assert held(loan, {}, {"other": D("70.00")}) == D("70.00")
    assert held(loan, {"other": D("100.00")}, {"other": D("70.00")}) == D("70.00")


def test_a_line_holding_a_loan_and_everyday_money():
    """Transportation laid out with 100.00 of everyday money and the 270.00
    loan (370.00). Spending uses the everyday money only — never the loan —
    and is never held twice."""
    loan_id = uuid4()
    loan = [due("transportation", "270.00", 15, loan_id)]
    base = {"transportation": D("370.00")}
    assert held(loan, base, {"transportation": D("60.00")}) == D("310.00")
    assert held(loan, base, {"transportation": D("130.00")}) == D("270.00")
    linked = {(loan_id, date(2026, 11, 15)): D("270.00")}
    # the loan linked in ChatGPT (it sits on the same line in this month)
    assert held(loan, base, {"transportation": D("270.00")}, linked) == D("100.00")
    assert held(loan, base, {"transportation": D("330.00")}, linked) == D("40.00")


def test_several_bills_in_one_category_are_held_until_each_is_linked():
    """Car loan 270.00 and scooter 50.00, both transportation, plus 100.00 of
    everyday money (420.00)."""
    car, scooter = uuid4(), uuid4()
    bills = [
        due("transportation", "270.00", 15, car),
        due("transportation", "50.00", 20, scooter),
    ]
    base = {"transportation": D("420.00")}
    assert held(bills, base, {"transportation": D("100.00")}) == D("320.00")
    linked = {(car, date(2026, 11, 15)): D("270.00")}
    assert held(bills, base, {"transportation": D("370.00")}, linked) == D("50.00")


# --- a month laid out in ChatGPT: exactly ChatGPT's figure ---------------------


def test_a_bill_line_is_settled_only_by_its_own_links():
    """Review finding 2. November's loan paid late on 3 December and linked to
    15 November lands on December's bill line; December's loan is still
    unpaid and stays held. Category spending never settles it either."""
    loan_id = uuid4()
    line = bill_key(loan_id)
    december = [
        DueOccurrence(
            obligation_id=loan_id,
            day=date(2026, 12, 15),
            category="transportation",
            amount=D("270.00"),
            merchant=None,
            recurrence="monthly",
            scheduled_from=date(2026, 12, 15),
        )
    ]
    base = {line: D("270.00"), "transportation": D("100.00")}
    assert held(december, base, {line: D("270.00")}, keyed=True) == D("270.00")
    assert held(december, base, {"transportation": D("270.00")}, keyed=True) == D(
        "270.00"
    )
    paid_december = {(loan_id, date(2026, 12, 15)): D("270.00")}
    assert held(december, base, {line: D("270.00")}, paid_december, keyed=True) == D(
        "0.00"
    )


def test_the_app_never_holds_more_than_chatgpt():
    """A payment linked in ChatGPT, recorded in another month, settles its due
    date here too."""
    rent_id, loan_id = uuid4(), uuid4()
    bills = [
        due("rent", "800.00", 1, rent_id),
        due("transportation", "270.00", 15, loan_id),
    ]
    linked = {
        (rent_id, date(2026, 11, 1)): D("800.00"),
        (loan_id, date(2026, 11, 15)): D("270.00"),
    }
    base = {"rent": D("800.00"), "transportation": D("270.00")}
    assert held(bills, base, {}, linked) == D("0.00")
