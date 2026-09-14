"""Explicit, reviewable choices for the Coconut + NASA POWER pipeline."""

from collections import OrderedDict

# The source does not establish whether 1981-82 belongs to 1981 or 1982.
# The command-line option in run_pipeline.py overrides this documented default.
DEFAULT_AGRICULTURE_YEAR_ANCHOR = "start"  # "start" maps 1981-82 -> 1981

# Calendar periods, not asserted crop seasons. Change this mapping only with a
# documented agronomic/calendar rationale; names deliberately expose the months.
CALENDAR_PERIODS = OrderedDict(
    [
        ("Jan_Feb", (1, 2)),
        ("Mar_May", (3, 4, 5)),
        ("Jun_Sep", (6, 7, 8, 9)),
        ("Oct_Dec", (10, 11, 12)),
    ]
)

# A predeclared small annual-lag horizon. It is configurable at execution time.
DEFAULT_CROSS_CORRELATION_MAX_LAG = 3
MIN_PAIRED_OBSERVATIONS = 30
ALPHA = 0.05
FDR_ALPHA = 0.10
REDUNDANCY_THRESHOLD = 0.85

# The full annual/seasonal feature screen has far more candidates than the
# available annual observations can support. Retain all screen results, but
# construct a review-sized dynamic subset with at most one lag per physical
# NASA parameter and no more than this many NASA predictors.
MAX_DYNAMIC_NASA_FEATURES = 7

# Full-year weather is not assumed to be available before a same-year annual
# target is predicted. Set only after defining an operational prediction cutoff.
INCLUDE_CONTEMPORANEOUS_FEATURES = False
