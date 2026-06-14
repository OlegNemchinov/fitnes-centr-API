# fitnes-centr-API

## Выбор технологий

- **FastAPI** – современный высокопроизводительный фреймворк для REST API, встроенная валидация данных через Pydantic, автоматическая генерация документации (Swagger/ReDoc).
- **Python 3.10+** – язык с богатой экосистемой для быстрой разработки.
- **Pydantic** – для декларативного описания моделей запросов/ответов и валидации.
- **Uvicorn** – ASGI-сервер для запуска приложения.
- **In-memory хранилище** – все данные хранятся в классовых атрибутах `_clients`, `_trainers` и словарях для быстрого доступа по ID. Это упрощает демонстрацию без необходимости настройки БД.

## Шаги по реализации

1. **Создание базовых классов и валидаторов** – функции `validate_name`, `validate_phone`, `validate_email` и др.
2. **Реализация классов Client и Trainer** с CRUD-методами:
   - `create` – создание и сохранение нового объекта.
   - `get` / `get_all` – получение одного или всех объектов.
   - `update` – обновление любых допустимых полей.
   - `delete` – удаление объекта.
   - `set_status`, `assign_trainer` – специфические методы для изменения статуса и назначения тренера.
3. **Разработка Pydantic-схем** для валидации входящих запросов (ClientCreate, ClientUpdate, TrainerCreate и т.д.).
4. **Создание FastAPI приложения** с группировкой эндпоинтов по префиксу `/api`:
   - `/api/clients` (POST, PUT, GET, GET/{id}, GET/{id}/detail, PATCH/{id}/status, POST/{clientId}/trainer/{trainerId})
   - `/api/trainers` (POST, PUT, PATCH/{id}/status, GET/{id}/detail, GET)
5. **Обработка ошибок** – HTTP 400 при валидации, 404 при отсутствии ресурса.
6. **Тестовые данные** – создаются при старте приложения (один клиент, один тренер, назначение тренера клиенту).

## Демонстрация результата

## Запуск приложения
```bash
pip install -r requirements.txt
python main.py
<img width="1877" height="913" alt="Снимок экрана 2026-06-14 132016" src="https://github.com/user-attachments/assets/7607012b-a714-4d85-9805-2cb791e0359e" />
<img width="1885" height="916" alt="Снимок экрана 2026-06-14 132007" src="https://github.com/user-attachments/assets/aecc2b81-9528-44da-a1ed-79c01c97ec66" />
<img width="1884" height="917" alt="Снимок экрана 2026-06-14 131955" src="https://github.com/user-attachments/assets/44e0a7ed-d2fc-4539-8466-d819be995959" />
<img width="1876" height="917" alt="Снимок экрана 2026-06-14 131943" src="https://github.com/user-attachments/assets/1b8fc57a-8c90-4b2d-91c8-888842fc16d0" />
<img width="1840" height="922" alt="Снимок экрана 2026-06-14 131931" src="https://github.com/user-attachments/assets/483e6f83-4d14-47b8-8b8f-65ee4d64c244" />
<img width="1911" height="991" alt="Снимок экрана 2026-06-14 131849" src="https://github.com/user-attachments/assets/d9bc88c3-5f6f-475f-8eea-89efc07537c3" />
