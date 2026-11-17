
from datetime import datetime
class MonthDayClass:

    def __init__(
            self,
            day,
            month
        ):
        self.day = day
        self.month = month
    

    def is_less_than(self, date:datetime):
        month = date.month
        day = date.day

        if((month, day) < (self.month, self.day)):
            return True
    
        return False
    

    def is_bigger_than(self, date:datetime):
        month = date.month
        day = date.day

        if((month, day) > (self.month, self.day)):
            return True
    
        return False
    

    def is_less_or_equal_than(self, date:datetime):
        month = date.month
        day = date.day

        if((month, day) <= (self.month, self.day)):
            return True
        
        return False
    

    def is_bigger_or_equal_than(self, date:datetime):
        month = date.month
        day = date.day

        if((month, day) >= (self.month, self.day)):
            return True
        
        return False