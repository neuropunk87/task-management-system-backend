# task-management-system-api

Система Управління Завданнями/Вебдодаток для створення, призначення, відстеження та керування завданнями в рамках проєктів<br/><br/>

<ins>Можливості користувацької частини</ins>:

● Реєстрація та автентифікація користувача: збір основної інформації про користувача, включно з електронною поштою і паролем.

● Створення та управління проєктами: можливість створювати нові проєкти, вказуючи їхню назву, опис і додавати учасників.

● Створення та призначення завдань: користувачі можуть створювати завдання в рамках проєкту, призначати їхніх виконавців, встановлювати терміни та пріоритети.

● Відстеження прогресу: надання інструментів для відстеження статусу виконання завдань, можливість оновлювати статус і додавати коментарі до завдань.

● Повідомлення: автоматичне надсилання повідомлень про нові завдання, зміни в завданнях і наближення термінів виконання - на email та в Telegram.<br/><br/>

<ins>Можливості адміністративної частини</ins>:

● Керування користувачами: можливість додавати, змінювати і видаляти користувачів, а також призначати ролі і права доступу.

● Моніторинг та аналітика: збір та аналіз даних про продуктивність команд і перебіг виконання проєктів, можливість генерації звітів/діаграм за різними показниками.

● Налаштування системи: конфігурація основних параметрів системи, включно з налаштуваннями сповіщень, шаблонами завдань і проєктів.<br/><br/>

> Основні технології, використані у проєкті

● Python для розробки серверної частини.

● Django Rest Framework (DRF) для реалізації API.

● Celery (асинхронна розподілена черга завдань).

● Redis (брокер повідомлень і тимчасове зберігання результатів задач).

● Gevent (мережева бібліотека Python на основі сопрограм, яка використовує Greenlet для надання високорівневого синхронного API поверх циклу подій libev або libuv).

● Httpx (бібліотека/HTTP-клієнт для Python 3 для виконання як синхронних, так і асинхронних HTTP-запитів).

● PostgreSQL для зберігання даних.<br/><br/>
