
from app.logic.category_priority import get_priority

def test_category_priority_rank():
    categories = ['coffee', 'rent', 'entertainment']
    sorted_expected = sorted(categories, key=lambda c: get_priority(c), reverse=True)
    assert sorted_expected == ['rent', 'entertainment', 'coffee']
