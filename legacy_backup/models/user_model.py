class User:
    def __init__(self, id, income, country, class_segment):
        self.id = id
        self.income = income
        self.country = country
        self.class_segment = class_segment
        self.config = {"income_check": {"enabled": True}}
