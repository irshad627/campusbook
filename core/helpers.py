import datetime

from django.utils import timezone

from accounts.models import User

PASSWORD = "testpass12345"


def make_user(name, role):
    return User.objects.create_user(name, password=PASSWORD, role=role)


def at(days, hour, minute=0):
    """A timezone-aware datetime `days` from now (negative = past) at the given hour."""
    base = timezone.now() + datetime.timedelta(days=days)
    return base.replace(hour=hour, minute=minute, second=0, microsecond=0)


def fmt(dt):
    """Format a datetime the way the booking form's date boxes expect it."""
    return dt.strftime("%Y-%m-%d %H:%M")