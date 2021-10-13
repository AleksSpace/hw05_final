import datetime

now = datetime.datetime.now()

now_year = now.year


def year(request):
    """Добавляет переменную с текущим годом."""
    return {
        'year': now_year
    }
