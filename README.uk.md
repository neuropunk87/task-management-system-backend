# Task Management System - Backend

[English](README.md) | Українська

REST API для командного керування проєктами та завданнями на Django і
Django REST Framework. Backend поєднує розподіл роботи, контроль термінів,
обговорення, сповіщення та аналітику проєктів.

Репозиторій містить серверну частину застосунку й Telegram-бота. Окремий
вебклієнт можна підключити через API.

## Можливості

- **Проєкти:** створення, керування учасниками, розмежування доступу, активний
  та архівний стани.
- **Завдання:** призначення виконавців, пріоритети, терміни, контроль виконання
  та історія змін.
- **Обговорення:** коментарі до завдань і відповіді на них.
- **Облікові записи:** реєстрація, JWT-автентифікація, профілі, зміна пароля,
  перевірене завантаження аватарів та адміністративні ролі.
- **Сповіщення:** email і Telegram про призначення, зміну статусу, пріоритету,
  терміну та наближення дати виконання.
- **Telegram:** підтвердження приватного чату одноразовим посиланням і команди
  бота для керування налаштуваннями сповіщень.
- **Аналітика:** кількість завдань, розподіл за статусами та середній час
  виконання через API й адміністративну панель.
- **API:** фільтрація, пошук, сортування, пагінація та специфікація OpenAPI.

## Технологічний стек

| Компонент | Технології |
| --- | --- |
| Мова та вебфреймворк | Python 3.14.10, Django 5.2 LTS |
| REST API | Django REST Framework, django-filter |
| Автентифікація | SimpleJWT, Django authentication, django-axes |
| База даних | PostgreSQL, Psycopg |
| Фонові завдання | Celery, gevent, django-celery-beat |
| Брокер, результати завдань і кеш | Redis |
| Telegram та HTTP-інтеграції | Aiogram, HTTPX |
| Статичні файли та вебсервер | WhiteNoise, Gunicorn |
| Документація API | drf-spectacular, OpenAPI, Swagger UI, ReDoc |

Версії прямих і транзитивних залежностей зафіксовано з SHA-256-хешами у
`requirements.txt` та `requirements-dev.txt`.

## Структура проєкту

```text
task_management_system/  Конфігурація Django та Celery, middleware, захист запитів
users/                   Облікові записи, JWT, профілі та підтвердження Telegram
projects/                Проєкти, учасники та права доступу
tasks/                   Завдання, виконавці, історія та коментарі
notifications/           Сповіщення, transactional outbox і Telegram-бот
analytics/               Статистика проєктів та адміністративні діаграми
.github/workflows/       Автоматичні тести й перевірки безпеки
```

PostgreSQL зберігає дані застосунку та чергу доставлення сповіщень. Celery
виконує фонові операції; Redis працює як брокер, сховище результатів і кеш.
Database beat планує періодичні завдання, а Telegram-бот використовує
long polling.

Сповіщення зберігається у transactional outbox разом із відповідною зміною
даних, а потім передається на доставлення. Недоступність брокера не видаляє
запис: періодичне завдання повторює спробу. Доставлення має семантику
at-least-once, тому зовнішній збій усе ще може спричинити дублікат.

## Контроль доступу

Доступ до проєкту залежить від володіння та участі. Доступ до завдання також
враховує призначення виконавцем. Виконавець може змінити статус завдання, але
не його вміст чи склад учасників. Власник проєкту та системний адміністратор
можуть редагувати й видаляти завдання.

Коментарі доступні лише в межах дозволеного завдання. Користувач бачить
тільки власні сповіщення та приватні поля свого профілю. Адміністрування й
аналітика потребують активної ролі системного адміністратора; самого
`is_staff` недостатньо для доступу.

## Локальне встановлення

### Вимоги

- Python 3.14.10.
- PostgreSQL і Redis для звичайної роботи застосунку.
- SMTP-сервіс і токен Telegram-бота для відповідних каналів сповіщень.
- Linux/Heroku для production-запуску через Gunicorn та наявний `Procfile`.

### Середовище Windows

Для нового клону виконайте в PowerShell:

```powershell
git clone https://github.com/neuropunk87/task-management-system-backend.git
cd task-management-system-backend

py -3.14 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --require-hashes -r requirements-dev.txt

if (!(Test-Path -LiteralPath .env)) {
    Copy-Item -LiteralPath .env.example -Destination .env
}
```

Заповніть `.env` значеннями свого середовища. Використовуйте унікальні
секрети й ніколи не додавайте робочі паролі або токени до Git. Для production
потрібні runtime-залежності з `requirements.txt`; файл залежностей для
розробки також містить інструменти тестування й аудиту.

### Основні налаштування

| Змінні | Призначення |
| --- | --- |
| `DJANGO_SECRET_KEY` | Унікальний секрет застосунку |
| `DJANGO_ENV`, `DEBUG`, `ALLOWED_HOSTS` | Середовище та дозволені домени |
| `DATABASE_URL` або `POSTGRES_*` | Підключення до PostgreSQL |
| `REDIS_URL`, `REDIS_TLS_URL` | Брокер Redis, результати завдань і кеш |
| `CORS_ALLOWED_ORIGINS`, `CSRF_TRUSTED_ORIGINS` | Дозволені origins вебклієнта |
| `EMAIL_*`, `DEFAULT_FROM_EMAIL` | Backend і параметри надсилання email |
| `TELEGRAM_BOT_TOKEN`, `TELEGRAM_BOT_USERNAME` | Налаштування Telegram-бота |

Повний шаблон конфігурації міститься у `.env.example`. Його налаштування
для розробки потрібно адаптувати перед використанням у production.

### Міграції та запуск API

Після налаштування локальних PostgreSQL і Redis:

```powershell
.\.venv\Scripts\python.exe manage.py migrate --noinput
.\.venv\Scripts\python.exe manage.py createsuperuser
.\.venv\Scripts\python.exe manage.py runserver
```

API працює за адресою `http://127.0.0.1:8000/`. Вхід до адміністративної
панелі: `/secretadmin/login/`. Для локальної роздачі аватарів можна
увімкнути `DEBUG=True`, але лише за умови `DJANGO_ENV=development`.

`runserver` призначений для розробки API й не запускає фонові компоненти.
Production використовує наявну схему Gunicorn/Celery/beat/bot у Linux/Heroku;
Gunicorn не підтримує запуск безпосередньо у Windows.

## API та документація

Основні маршрути:

| Маршрут | Призначення |
| --- | --- |
| `POST /api/users/register/` | Реєстрація |
| `POST /api/users/login/` | Отримання access- і refresh-токенів |
| `POST /api/users/token/refresh/` | Оновлення токенів |
| `POST /api/users/logout` | Відкликання власного refresh-токена |
| `/api/users/profile/` | Власний профіль |
| `POST/DELETE /api/users/profile/telegram-link/` | Підтвердження або відв'язування Telegram |
| `/api/projects/` | Проєкти та учасники |
| `/api/tasks/tasks/` | Завдання та додаткові списки |
| `/api/tasks/comments/` | Коментарі й відповіді |
| `/api/notifications/` | Власні непрочитані сповіщення |
| `/api/analytics/<project_id>/` | Аналітика проєкту для адміністраторів |
| `/api/schema/` | Схема OpenAPI |

Для автентифікованих запитів передавайте заголовок:

```http
Authorization: Bearer <access_token>
```

Документація для розробки доступна за адресами `/api/docs/swagger-ui/` і
`/api/docs/redoc/`. У production ці інтерфейси типово вимкнені, а доступ
до схеми мають лише адміністратори. Специфікація API в репозиторії:
`schema.yml`.

## Розгортання на Heroku

Наявна схема використовує **два типи процесів**. Команди `Procfile`
залишаються незмінними:

```procfile
web: gunicorn task_management_system.wsgi --log-file -
worker: celery -A task_management_system worker --loglevel=info -P gevent & celery -A task_management_system beat --scheduler django_celery_beat.schedulers.DatabaseScheduler --loglevel=info & exec python notifications/telegram_bot.py
```

Celery worker, beat і Telegram-бот працюють в одному worker dyno. Не
розділяйте їх на додаткові типи процесів і не замінюйте цю схему новим launcher.
Для beat і long polling потрібна одна worker-репліка. Масштабування та платні
ресурси автоматично не змінюються.

### Production-конфігурація

- `DJANGO_ENV=production`, `DEBUG=False` та унікальний `DJANGO_SECRET_KEY`.
- Точні `ALLOWED_HOSTS` без `*` і потрібні HTTPS origins вебклієнта.
- URL наявних PostgreSQL/Redis add-on, SMTP і налаштування Telegram.
- PostgreSQL із TLS, Redis через `rediss://`.

Змінна Heroku runtime `DYNO` вмикає production- і proxy-налаштування за
замовчуванням. Явно задані Config Vars мають пріоритет. Без окремих Redis
overrides брокер, сховище результатів і кеш успадковують поточний URL add-on;
не фіксуйте застарілі адреси підключення.

Для Heroku KVS без власного CA використовується режим сумісності: TLS
залишається ввімкненим, але перевірку самопідписаного сертифіката вимкнено
лише для Redis. Цей режим застосовується автоматично, коли є `DYNO` і не
задано `REDIS_SSL_CA_CERTS`. Поза Heroku перевірка залишається суворою.
З'єднання зашифроване, але справжність сервера не підтверджується. Це
прийнятий компроміс відповідно до
[рекомендацій Heroku KVS](https://devcenter.heroku.com/articles/connecting-heroku-redis).
Не задавайте `HEROKU_REDIS_COMPATIBILITY=False` без довіреного CA.

### Оновлення наявного розгортання

Власниця репозиторію виконує розгортання та production-міграції вручну.
Створіть резервну копію бази даних і застосуйте міграції **кодом нової
версії** в заплановане вікно обслуговування, до звичайної обробки запитів
і фонових завдань:

```text
python manage.py check --deploy --fail-level WARNING
python manage.py migrate --noinput
python manage.py collectstatic --noinput
```

Команди керування можна виконувати через `heroku run ... -a APP`, коли
нова версія вже доступна. Одноразові запуски можуть витрачати квоту підписки.
Окремий тип процесу `release` до `Procfile` не додається.

Heroku має тимчасову файлову систему: локальний `MEDIA_ROOT` не гарантує
збереження аватарів чи їхньої доступності між dyno. Постійне media-сховище
налаштовується окремо; новий сервіс або платний add-on автоматично не
створюється.

## Тестування та перевірки безпеки

Тести типово використовують тимчасову SQLite і кеш у пам'яті. Справжні
повідомлення через SMTP або Telegram не надсилаються:

```powershell
.\.venv\Scripts\python.exe manage.py test --settings=task_management_system.settings_test
.\.venv\Scripts\python.exe -m pip check

.\.venv\Scripts\bandit.exe -r analytics notifications projects task_management_system tasks users -x "*/migrations/*,*/tests.py,*/tests_*.py"
.\.venv\Scripts\pip-audit.exe -r requirements.txt --require-hashes --strict
.\.venv\Scripts\pip-audit.exe -r requirements-dev.txt --require-hashes --disable-pip --strict
```

Для перевірки конкурентних транзакцій задайте `AUDIT_TEST_DATABASE_URL`
і `AUDIT_TEST_REDIS_URL` **лише для ізольованих тестових сервісів**.
Runner створює та видаляє тестову базу даних, а тести очищають кеш.
Використовувати production Redis не можна. Без PostgreSQL два тести
конкурентного доступу пропускаються.

Workflow у `.github/workflows/security.yml` визначає тести на PostgreSQL/Redis,
поріг покриття 80%, перевірки міграцій, схеми й production-налаштувань, Bandit
та аудит залежностей, зокрема щотижневий запуск. Для виконання на GitHub
потрібно опублікувати зміни.

Перевірено 2026-10-08: **106 тестів** на Windows і Linux пройшли, покриття
з урахуванням розгалужень становить **84%**, Bandit та обидва аудити
залежностей не виявили проблем. Результати сканерів не гарантують відсутності
всіх уразливостей.

## Оновлення залежностей

Редагуйте `requirements.in` і `requirements-dev.in`, а потім сформуйте
lock-файли заново:

```powershell
.\.venv\Scripts\pip-compile.exe --generate-hashes --allow-unsafe --newline=lf -o requirements.txt requirements.in
.\.venv\Scripts\pip-compile.exe --generate-hashes --allow-unsafe --newline=lf -o requirements-dev.txt requirements-dev.in
```

Після оновлення повторіть тести, `pip check` та аудит обох lock-файлів.
Не замінюйте їх довільним `pip freeze` зі спільного середовища.
