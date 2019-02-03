from decimal import Decimal
from datetime import time

# Maximum number of slots on each date
MAX_SLOT_NUMBER = 3

# Maximum number of slots on each date
MAX_SLOT_DINER_MINIMUM = 6
MIN_SLOT_DINER_MAXIMUM = 12

# Last claim time for dining slots
DINING_SLOT_CLAIM_CLOSURE_TIME = time(17, 00)

# Balance bottom limit
MINIMUM_BALANCE = Decimal('-2.00')