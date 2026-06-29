import os
from datetime import datetime, timedelta
from caldav import DAVClient
from caldav.elements import dav, cdav
import pytz

class YandexCalendar:
    def __init__(self, username: str, password: str, url: str = "https://caldav.yandex.ru/"):
        self.client = DAVClient(url=url, username=username, password=password)
        self.principal = self.client.principal()
        self.calendars = self.principal.calendars()

    def get_default_calendar(self):
        if not self.calendars:
            return self.principal.make_calendar(name="Основной")
        return self.calendars[0]

    def get_events_for_date_range(self, start_date: datetime, end_date: datetime):
        calendar = self.get_default_calendar()
        start_utc = start_date.astimezone(pytz.UTC)
        end_utc = end_date.astimezone(pytz.UTC)
        events = calendar.date_search(
            start=start_utc,
            end=end_utc,
            expand=True,
        )
        return events

    def add_event(self, summary: str, start: datetime, end: datetime, description: str = ""):
        calendar = self.get_default_calendar()
        event_data = f"""BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//AI Secretary//EN
BEGIN:VEVENT
UID:{datetime.now().strftime('%Y%m%d%H%M%S')}@ai-secretary
DTSTAMP:{datetime.now().strftime('%Y%m%dT%H%M%SZ')}
DTSTART:{start.strftime('%Y%m%dT%H%M%SZ')}
DTEND:{end.strftime('%Y%m%dT%H%M%SZ')}
SUMMARY:{summary}
DESCRIPTION:{description}
END:VEVENT
END:VCALENDAR"""
        return calendar.save_event(event_data)

    def get_events_for_today(self):
        today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        today_end = today_start + timedelta(days=1)
        return self.get_events_for_date_range(today_start, today_end)

    def get_events_for_tomorrow(self):
        tomorrow_start = (datetime.now() + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        tomorrow_end = tomorrow_start + timedelta(days=1)
        return self.get_events_for_date_range(tomorrow_start, tomorrow_end)