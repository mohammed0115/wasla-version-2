"""
Custom date range filtering for analytics.

Provides flexible date range selection for dashboard metrics.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Literal

from django.utils import timezone


@dataclass
class DateRange:
    """Represents a date range."""
    start_date: datetime
    end_date: datetime
    label: str
    period_type: str  # 'today', '7d', '30d', '90d', 'ytd', 'custom'

    def __str__(self) -> str:
        return f"{self.label} ({self.start_date.date()} - {self.end_date.date()})"

    def days(self) -> int:
        """Number of days in range."""
        return (self.end_date - self.start_date).days

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            'start_date': self.start_date.isoformat(),
            'end_date': self.end_date.isoformat(),
            'label': self.label,
            'period_type': self.period_type,
            'days': self.days(),
        }


class DateRangeService:
    """Service for handling date range selections."""

    @staticmethod
    def get_preset_range(preset: str) -> DateRange:
        """
        Get a preset date range.

        Args:
            preset: 'today', '7d', '30d', '90d', 'ytd', 'last_quarter'

        Returns:
            DateRange object
        """
        now = timezone.now()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        today_end = now

        if preset == 'today':
            return DateRange(
                start_date=today_start,
                end_date=today_end,
                label='Today',
                period_type='today'
            )
        elif preset == '7d':
            return DateRange(
                start_date=now - timedelta(days=7),
                end_date=now,
                label='Last 7 Days',
                period_type='7d'
            )
        elif preset == '30d':
            return DateRange(
                start_date=now - timedelta(days=30),
                end_date=now,
                label='Last 30 Days',
                period_type='30d'
            )
        elif preset == '90d':
            return DateRange(
                start_date=now - timedelta(days=90),
                end_date=now,
                label='Last 90 Days',
                period_type='90d'
            )
        elif preset == 'ytd':
            year_start = now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
            return DateRange(
                start_date=year_start,
                end_date=now,
                label='Year to Date',
                period_type='ytd'
            )
        elif preset == 'last_quarter':
            current_quarter = (now.month - 1) // 3
            quarter_start_month = current_quarter * 3 + 1
            if current_quarter == 0:
                # Last quarter is Q4 of previous year
                quarter_start = now.replace(year=now.year - 1, month=10, day=1, hour=0, minute=0, second=0, microsecond=0)
            else:
                quarter_start = now.replace(month=quarter_start_month - 3, day=1, hour=0, minute=0, second=0, microsecond=0)
            return DateRange(
                start_date=quarter_start,
                end_date=now,
                label='Last Quarter',
                period_type='last_quarter'
            )
        else:
            raise ValueError(f"Unknown preset: {preset}")

    @staticmethod
    def get_custom_range(start_date: str, end_date: str) -> DateRange:
        """
        Get a custom date range.

        Args:
            start_date: ISO format date string (YYYY-MM-DD)
            end_date: ISO format date string (YYYY-MM-DD)

        Returns:
            DateRange object
        """
        try:
            start = datetime.fromisoformat(start_date).replace(tzinfo=timezone.utc)
            end = datetime.fromisoformat(end_date).replace(tzinfo=timezone.utc, hour=23, minute=59, second=59)

            if start > end:
                raise ValueError("Start date must be before end date")

            return DateRange(
                start_date=start,
                end_date=end,
                label=f"{start.date()} to {end.date()}",
                period_type='custom'
            )
        except ValueError as e:
            raise ValueError(f"Invalid date format: {str(e)}")

    @staticmethod
    def get_comparison_range(date_range: DateRange) -> DateRange:
        """
        Get previous period for comparison.

        Args:
            date_range: Current date range

        Returns:
            Previous period date range
        """
        period_length = date_range.end_date - date_range.start_date
        previous_start = date_range.start_date - period_length
        previous_end = date_range.start_date

        return DateRange(
            start_date=previous_start,
            end_date=previous_end,
            label=f"Previous {date_range.label}",
            period_type='comparison'
        )

    @staticmethod
    def get_preset_options() -> list[dict]:
        """Get list of available preset options."""
        return [
            {'value': 'today', 'label': 'Today'},
            {'value': '7d', 'label': 'Last 7 Days'},
            {'value': '30d', 'label': 'Last 30 Days'},
            {'value': '90d', 'label': 'Last 90 Days'},
            {'value': 'ytd', 'label': 'Year to Date'},
            {'value': 'last_quarter', 'label': 'Last Quarter'},
        ]
