"""Presentation-only template helpers for the dashboard."""

from django import template

register = template.Library()


@register.filter
def datetime_local(value):
    """Format a datetime for an HTML ``datetime-local`` input."""
    if not value:
        return ""
    return value.strftime("%Y-%m-%dT%H:%M:%S")
