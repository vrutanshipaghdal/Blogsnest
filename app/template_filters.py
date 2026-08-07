from datetime import timedelta

IST_OFFSET = timedelta(hours=5, minutes=30)


def to_ist(dt):
    """Database stores UTC (best practice). This converts to India Standard
    Time only when displaying to the user, so timestamps shown in templates
    match what's on your PC/phone instead of being 5:30 hours behind."""
    if dt is None:
        return None
    return dt + IST_OFFSET