from decimal import Decimal
from datetime import time, timedelta

# Maximum number of slots on each date
MAX_SLOT_NUMBER = 3

# Maximum number of slots on each date
MAX_SLOT_DINER_MINIMUM = 6
MIN_SLOT_DINER_MAXIMUM = 12

# Last claim time for dining slots
DINING_SLOT_CLAIM_CLOSURE_TIME = time(17, 00)

# Kitchen use time
KITCHEN_USE_START_TIME = time(16, 30)
KITCHEN_USE_END_TIME = time(19, 30)

# Balance bottom limit
MINIMUM_BALANCE = Decimal('-2.00')

# The duration that pending transactions should last
TRANSACTION_PENDING_DURATION = timedelta(days=2)
