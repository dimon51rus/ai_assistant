import os
from datetime import datetime, timedelta
from caldav import DAVClient
from caldav.elements import dav, cdav
import pytz

class YandexCalendar:
    def __init__(self, username: str, password: str, url: str = "https://caldav.yandex.ru/"):
        """Инициализация клиента для работы с Яндекс Календарем."""
        self.client = DAVClient(url=url, username=username, password=password)
        self.principal = self.client.principal()
        self.calendars = self.principal.calendars()

    def get_default_calendar(self):
        """Возвращает первый (обычно основной) календарь пользователя."""
        if not self.calendars:
            # Если календарей нет, пытаемся создать основной
            return self.principal.make_calendar(name="Основной")
        return self.calendars[0]

    def get_events_for_date_range(self, start_date: datetime, end_date: datetime):
        """
        Получает события из календаря за указанный период.
        Возвращает список объектов событий.
        """
        calendar = self.get_default_calendar()
        # Приводим даты к UTC, как требует стандарт CalDAV
        start_utc = start_date.astimezone(pytz.UTC)
        end_utc = end_date.astimezone(pytz.UTC)

        # Получаем события в формате iCalendar
        events = calendar.date_search(
            start=start_utc,
            end=end_utc,
            expand=True,  # Разворачивает повторяющиеся события
        )
        return events

    def add_event(self, summary: str, start: datetime, end: datetime, description: str = ""):
        """
        Создает новое событие в календаре.
        """
        calendar = self.get_default_calendar()
        # Формируем данные события в формате iCalendar
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
        # Сохраняем событие
        return calendar.save_event(event_data)

    def get_events_for_today(self):
        """Получает события на сегодня."""
        today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        today_end = today_start + timedelta(days=1)
        return self.get_events_for_date_range(today_start, today_end)

    def get_events_for_tomorrow(self):
        """Получает события на завтра."""
        tomorrow_start = (datetime.now() + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        tomorrow_end = tomorrow_start + timedelta(days=1)
        return self.get_events_for_date_range(tomorrow_start, tomorrow_end)
