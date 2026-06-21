import re
import sqlite3
import uuid
from datetime import datetime
from typing import Optional, List, Dict, Any

from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel, Field

#Валидаторы
def validate_name(value: str, field_name: str) -> str:
    if not value or not value.strip():
        raise ValueError(f"{field_name} не может быть пустым")
    return value.strip()

def validate_phone(phone: str) -> str:
    pattern = r'^\+?\d{10,12}$'
    if not re.match(pattern, phone):
        raise ValueError("Некорректный номер телефона. Должен содержать 10-12 цифр, может начинаться с +")
    return phone

def validate_email(email: str) -> str:
    if '@' not in email or '.' not in email.split('@')[-1]:
        raise ValueError("Некорректный email.")
    return email

def validate_birthday(birthday: str) -> str:
    try:
        birth_date = datetime.strptime(birthday, "%d.%m.%Y")
    except ValueError:
        raise ValueError("Неверный формат даты рождения. Используйте ДД.ММ.ГГГГ")
    if birth_date > datetime.now():
        raise ValueError("Дата рождения не может быть в будущем")
    age = datetime.now().year - birth_date.year
    if (datetime.now().month, datetime.now().day) < (birth_date.month, birth_date.day):
        age -= 1
    if age < 14:
        raise ValueError("Клиент должен быть не младше 14 лет")
    return birthday

def validate_status(status: str) -> str:
    allowed = {"WORKING", "ON_LEAVE", "NOT_WORKING"}
    if status not in allowed:
        raise ValueError(f"Статус тренера должен быть одним из: {', '.join(allowed)}")
    return status

#Подключение к БД и создание таблиц
DB_NAME = "fitness.db"

def get_db_connection():
    """Возвращает соединение с SQLite и включает поддержку внешних ключей."""
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row  # чтобы возвращать словари
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def init_db():
    """Создаёт таблицы, если их нет (миграция)."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        # Таблица тренеров
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS trainers (
                id TEXT PRIMARY KEY,
                surname TEXT NOT NULL,
                name TEXT NOT NULL,
                patronymic TEXT DEFAULT '',
                phone TEXT UNIQUE NOT NULL,
                status TEXT NOT NULL
            )
        """)
        # Таблица клиентов
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS clients (
                id TEXT PRIMARY KEY,
                surname TEXT NOT NULL,
                name TEXT NOT NULL,
                patronymic TEXT DEFAULT '',
                birthday TEXT NOT NULL,
                phone TEXT UNIQUE NOT NULL,
                email TEXT UNIQUE NOT NULL,
                is_active INTEGER DEFAULT 1,
                trainer_id TEXT REFERENCES trainers(id) ON DELETE SET NULL
            )
        """)
        # Таблица шкафчиков
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS lockers (
                id TEXT PRIMARY KEY,
                number INTEGER UNIQUE NOT NULL,
                client_id TEXT UNIQUE REFERENCES clients(id) ON DELETE SET NULL
            )
        """)
        # Таблица услуг
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS services (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                price INTEGER NOT NULL
            )
        """)
        # Связующая таблица клиент-услуга
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS client_services (
                client_id TEXT REFERENCES clients(id) ON DELETE CASCADE,
                service_id TEXT REFERENCES services(id) ON DELETE CASCADE,
                PRIMARY KEY (client_id, service_id)
            )
        """)
        conn.commit()

# Seed-данные
def seed_database():
    """Заполняет начальными данными, если таблицы пусты."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        # Шкафчики 1..20
        count = cursor.execute("SELECT COUNT(*) FROM lockers").fetchone()[0]
        if count == 0:
            for i in range(1, 21):
                locker_id = str(uuid.uuid4())
                cursor.execute(
                    "INSERT INTO lockers (id, number, client_id) VALUES (?, ?, NULL)",
                    (locker_id, i)
                )
            conn.commit()

        # Услуги
        count = cursor.execute("SELECT COUNT(*) FROM services").fetchone()[0]
        if count == 0:
            services = [
                ("SOLARIUM", "Солярий", 400),
                ("POOL", "Бассейн", 200),
                ("SAUNA", "Сауна", 0),
                ("CRYOSAUNA", "Криосауна", 1000),
                ("CROSSFIT", "Кроссфит", 500),
            ]
            cursor.executemany(
                "INSERT INTO services (id, name, price) VALUES (?, ?, ?)",
                services
            )
            conn.commit()

# Инициализация при старте
init_db()
seed_database()

# Вспомогательные функции для работы с БД
def row_to_dict(row: sqlite3.Row) -> Dict[str, Any]:
    """Преобразует sqlite3.Row в обычный словарь."""
    return dict(row)

def get_client_by_id(conn, client_id: str) -> Optional[Dict]:
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM clients WHERE id = ?", (client_id,))
    row = cursor.fetchone()
    return row_to_dict(row) if row else None

def get_trainer_by_id(conn, trainer_id: str) -> Optional[Dict]:
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM trainers WHERE id = ?", (trainer_id,))
    row = cursor.fetchone()
    return row_to_dict(row) if row else None

def get_locker_by_id(conn, locker_id: str) -> Optional[Dict]:
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM lockers WHERE id = ?", (locker_id,))
    row = cursor.fetchone()
    return row_to_dict(row) if row else None

def get_service_by_id(conn, service_id: str) -> Optional[Dict]:
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM services WHERE id = ?", (service_id,))
    row = cursor.fetchone()
    return row_to_dict(row) if row else None

def get_client_services(conn, client_id: str) -> List[Dict]:
    cursor = conn.cursor()
    cursor.execute("""
        SELECT s.id, s.name, s.price
        FROM client_services cs
        JOIN services s ON cs.service_id = s.id
        WHERE cs.client_id = ?
    """, (client_id,))
    return [row_to_dict(row) for row in cursor.fetchall()]

def get_client_trainer(conn, client_id: str) -> Optional[Dict]:
    cursor = conn.cursor()
    cursor.execute("""
        SELECT t.* FROM trainers t
        JOIN clients c ON c.trainer_id = t.id
        WHERE c.id = ?
    """, (client_id,))
    row = cursor.fetchone()
    return row_to_dict(row) if row else None

def get_client_locker(conn, client_id: str) -> Optional[Dict]:
    cursor = conn.cursor()
    cursor.execute("""
        SELECT l.* FROM lockers l
        WHERE l.client_id = ?
    """, (client_id,))
    row = cursor.fetchone()
    return row_to_dict(row) if row else None

def get_clients_by_service(conn, service_id: str) -> List[Dict]:
    cursor = conn.cursor()
    cursor.execute("""
        SELECT c.* FROM clients c
        JOIN client_services cs ON cs.client_id = c.id
        WHERE cs.service_id = ?
    """, (service_id,))
    return [row_to_dict(row) for row in cursor.fetchall()]

# Pydantic модели
class ClientCreate(BaseModel):
    surname: str = Field(..., min_length=1)
    name: str = Field(..., min_length=1)
    patronymic: str = ""
    birthday: str
    phone: str
    email: str
    is_active: bool = True

class ClientUpdate(BaseModel):
    surname: Optional[str] = None
    name: Optional[str] = None
    patronymic: Optional[str] = None
    birthday: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None

class ClientStatusUpdate(BaseModel):
    is_active: bool

class TrainerCreate(BaseModel):
    surname: str = Field(..., min_length=1)
    name: str = Field(..., min_length=1)
    patronymic: str = ""
    phone: str
    status: str

class TrainerUpdate(BaseModel):
    surname: Optional[str] = None
    name: Optional[str] = None
    patronymic: Optional[str] = None
    phone: Optional[str] = None

class TrainerStatusUpdate(BaseModel):
    status: str

# FastAPI приложение
app = FastAPI(title="Фитнес-клуб API")

# Эндпоинты клиентов
@app.post("/api/clients", response_model=dict, status_code=status.HTTP_201_CREATED)
async def create_client(client_data: ClientCreate):
    try:
        surname = validate_name(client_data.surname, "Фамилия")
        name = validate_name(client_data.name, "Имя")
        patronymic = client_data.patronymic.strip()
        phone = validate_phone(client_data.phone)
        email = validate_email(client_data.email)
        birthday = validate_birthday(client_data.birthday)
        client_id = str(uuid.uuid4())
        is_active = 1 if client_data.is_active else 0

        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """INSERT INTO clients
                   (id, surname, name, patronymic, birthday, phone, email, is_active)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (client_id, surname, name, patronymic, birthday, phone, email, is_active)
            )
            conn.commit()
            # Возвращаем созданный объект
            return get_client_by_id(conn, client_id)
    except sqlite3.IntegrityError as e:
        if "UNIQUE constraint failed: clients.phone" in str(e):
            raise HTTPException(status_code=400, detail="Телефон уже используется")
        if "UNIQUE constraint failed: clients.email" in str(e):
            raise HTTPException(status_code=400, detail="Email уже используется")
        raise HTTPException(status_code=400, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.put("/api/clients/{client_id}", response_model=dict)
async def update_client(client_id: str, update_data: ClientUpdate):
    update_dict = {k: v for k, v in update_data.dict().items() if v is not None}
    if not update_dict:
        raise HTTPException(status_code=400, detail="Нет данных для обновления")

    # Валидация полей (если есть)
    try:
        if "surname" in update_dict:
            update_dict["surname"] = validate_name(update_dict["surname"], "Фамилия")
        if "name" in update_dict:
            update_dict["name"] = validate_name(update_dict["name"], "Имя")
        if "patronymic" in update_dict:
            update_dict["patronymic"] = update_dict["patronymic"].strip()
        if "phone" in update_dict:
            update_dict["phone"] = validate_phone(update_dict["phone"])
        if "email" in update_dict:
            update_dict["email"] = validate_email(update_dict["email"])
        if "birthday" in update_dict:
            update_dict["birthday"] = validate_birthday(update_dict["birthday"])
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Формируем SQL запрос динамически
    set_clauses = []
    values = []
    for key, val in update_dict.items():
        set_clauses.append(f"{key} = ?")
        values.append(val)
    values.append(client_id)

    with get_db_connection() as conn:
        cursor = conn.cursor()
        # Проверяем, существует ли клиент
        existing = get_client_by_id(conn, client_id)
        if not existing:
            raise HTTPException(status_code=404, detail="Клиент не найден")
        try:
            cursor.execute(
                f"UPDATE clients SET {', '.join(set_clauses)} WHERE id = ?",
                values
            )
            conn.commit()
            updated = get_client_by_id(conn, client_id)
            return updated
        except sqlite3.IntegrityError as e:
            if "UNIQUE constraint failed: clients.phone" in str(e):
                raise HTTPException(status_code=400, detail="Телефон уже используется")
            if "UNIQUE constraint failed: clients.email" in str(e):
                raise HTTPException(status_code=400, detail="Email уже используется")
            raise HTTPException(status_code=400, detail=str(e))

@app.get("/api/clients", response_model=List[dict])
async def get_clients(active_only: bool = False):
    with get_db_connection() as conn:
        cursor = conn.cursor()
        if active_only:
            cursor.execute("SELECT * FROM clients WHERE is_active = 1")
        else:
            cursor.execute("SELECT * FROM clients")
        rows = cursor.fetchall()
        return [row_to_dict(row) for row in rows]

@app.get("/api/clients/{client_id}", response_model=dict)
async def get_client_short(client_id: str):
    with get_db_connection() as conn:
        client = get_client_by_id(conn, client_id)
        if not client:
            raise HTTPException(status_code=404, detail="Клиент не найден")
        return client

@app.get("/api/clients/{client_id}/detail", response_model=dict)
async def get_client_detail(client_id: str):
    with get_db_connection() as conn:
        client = get_client_by_id(conn, client_id)
        if not client:
            raise HTTPException(status_code=404, detail="Клиент не найден")
        # Дополнительные данные
        trainer = get_client_trainer(conn, client_id)
        locker = get_client_locker(conn, client_id)
        services = get_client_services(conn, client_id)

        result = dict(client)
        result["trainer"] = trainer if trainer else None
        result["locker"] = {"id": locker["id"], "number": locker["number"]} if locker else None
        result["services"] = services
        return result

@app.patch("/api/clients/{client_id}/status", response_model=dict)
async def update_client_status(client_id: str, status_data: ClientStatusUpdate):
    with get_db_connection() as conn:
        client = get_client_by_id(conn, client_id)
        if not client:
            raise HTTPException(status_code=404, detail="Клиент не найден")
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE clients SET is_active = ? WHERE id = ?",
            (1 if status_data.is_active else 0, client_id)
        )
        conn.commit()
        return get_client_by_id(conn, client_id)

@app.post("/api/clients/{client_id}/trainer/{trainer_id}", response_model=dict, status_code=status.HTTP_200_OK)
async def assign_trainer_to_client(client_id: str, trainer_id: str):
    with get_db_connection() as conn:
        client = get_client_by_id(conn, client_id)
        if not client:
            raise HTTPException(status_code=404, detail="Клиент не найден")
        trainer = get_trainer_by_id(conn, trainer_id)
        if not trainer:
            raise HTTPException(status_code=404, detail="Тренер не найден")
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE clients SET trainer_id = ? WHERE id = ?",
            (trainer_id, client_id)
        )
        conn.commit()
        return get_client_by_id(conn, client_id)

@app.post("/api/clients/{client_id}/locker/{locker_id}", response_model=dict, status_code=status.HTTP_200_OK)
async def assign_locker(client_id: str, locker_id: str):
    with get_db_connection() as conn:
        client = get_client_by_id(conn, client_id)
        if not client:
            raise HTTPException(status_code=404, detail="Клиент не найден")
        locker = get_locker_by_id(conn, locker_id)
        if not locker:
            raise HTTPException(status_code=404, detail="Шкафчик не найден")
        if locker["client_id"] is not None:
            raise HTTPException(status_code=409, detail="Шкафчик уже занят")
        # Проверяем, есть ли у клиента уже шкафчик
        existing_locker = get_client_locker(conn, client_id)
        if existing_locker:
            raise HTTPException(status_code=409, detail="Клиент уже имеет шкафчик")
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE lockers SET client_id = ? WHERE id = ?",
            (client_id, locker_id)
        )
        conn.commit()
        return get_client_detail(client_id)

@app.post("/api/clients/{client_id}/additionalServices/{service_id}", response_model=dict, status_code=status.HTTP_200_OK)
async def add_service_to_client(client_id: str, service_id: str):
    with get_db_connection() as conn:
        client = get_client_by_id(conn, client_id)
        if not client:
            raise HTTPException(status_code=404, detail="Клиент не найден")
        service = get_service_by_id(conn, service_id)
        if not service:
            raise HTTPException(status_code=404, detail="Услуга не найдена")
        # Проверка на дубликат
        cursor = conn.cursor()
        cursor.execute(
            "SELECT 1 FROM client_services WHERE client_id = ? AND service_id = ?",
            (client_id, service_id)
        )
        if cursor.fetchone():
            raise HTTPException(status_code=409, detail="Услуга уже подключена")
        cursor.execute(
            "INSERT INTO client_services (client_id, service_id) VALUES (?, ?)",
            (client_id, service_id)
        )
        conn.commit()
        return {"message": "Услуга добавлена", "client": get_client_by_id(conn, client_id)}

@app.get("/api/lockers", response_model=List[dict])
async def get_lockers():
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM lockers ORDER BY number")
        rows = cursor.fetchall()
        result = []
        for row in rows:
            d = row_to_dict(row)
            d["occupied"] = d["client_id"] is not None
            result.append(d)
        return result

@app.get("/api/additionalServices", response_model=List[dict])
async def get_services():
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM services")
        rows = cursor.fetchall()
        return [row_to_dict(row) for row in rows]

@app.get("/api/additionalServices/{service_id}", response_model=dict)
async def get_service_detail(service_id: str):
    with get_db_connection() as conn:
        service = get_service_by_id(conn, service_id)
        if not service:
            raise HTTPException(status_code=404, detail="Услуга не найдена")
        clients = get_clients_by_service(conn, service_id)
        result = dict(service)
        result["clients"] = clients
        return result

# Эндпоинты тренеров
@app.post("/api/trainers", response_model=dict, status_code=status.HTTP_201_CREATED)
async def create_trainer(trainer_data: TrainerCreate):
    try:
        surname = validate_name(trainer_data.surname, "Фамилия")
        name = validate_name(trainer_data.name, "Имя")
        patronymic = trainer_data.patronymic.strip()
        phone = validate_phone(trainer_data.phone)
        status = validate_status(trainer_data.status)
        trainer_id = str(uuid.uuid4())

        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """INSERT INTO trainers
                   (id, surname, name, patronymic, phone, status)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (trainer_id, surname, name, patronymic, phone, status)
            )
            conn.commit()
            return get_trainer_by_id(conn, trainer_id)
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=400, detail="Телефон уже используется")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.put("/api/trainers/{trainer_id}", response_model=dict)
async def update_trainer(trainer_id: str, update_data: TrainerUpdate):
    update_dict = {k: v for k, v in update_data.dict().items() if v is not None}
    if not update_dict:
        raise HTTPException(status_code=400, detail="Нет данных для обновления")
    try:
        if "surname" in update_dict:
            update_dict["surname"] = validate_name(update_dict["surname"], "Фамилия")
        if "name" in update_dict:
            update_dict["name"] = validate_name(update_dict["name"], "Имя")
        if "patronymic" in update_dict:
            update_dict["patronymic"] = update_dict["patronymic"].strip()
        if "phone" in update_dict:
            update_dict["phone"] = validate_phone(update_dict["phone"])
        if "status" in update_dict:
            update_dict["status"] = validate_status(update_dict["status"])
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    set_clauses = []
    values = []
    for key, val in update_dict.items():
        set_clauses.append(f"{key} = ?")
        values.append(val)
    values.append(trainer_id)

    with get_db_connection() as conn:
        trainer = get_trainer_by_id(conn, trainer_id)
        if not trainer:
            raise HTTPException(status_code=404, detail="Тренер не найден")
        try:
            cursor = conn.cursor()
            cursor.execute(
                f"UPDATE trainers SET {', '.join(set_clauses)} WHERE id = ?",
                values
            )
            conn.commit()
            return get_trainer_by_id(conn, trainer_id)
        except sqlite3.IntegrityError:
            raise HTTPException(status_code=400, detail="Телефон уже используется")

@app.patch("/api/trainers/{trainer_id}/status", response_model=dict)
async def update_trainer_status(trainer_id: str, status_data: TrainerStatusUpdate):
    try:
        status = validate_status(status_data.status)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    with get_db_connection() as conn:
        trainer = get_trainer_by_id(conn, trainer_id)
        if not trainer:
            raise HTTPException(status_code=404, detail="Тренер не найден")
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE trainers SET status = ? WHERE id = ?",
            (status, trainer_id)
        )
        conn.commit()
        return get_trainer_by_id(conn, trainer_id)

@app.get("/api/trainers/{trainer_id}/detail", response_model=dict)
async def get_trainer_detail(trainer_id: str):
    with get_db_connection() as conn:
        trainer = get_trainer_by_id(conn, trainer_id)
        if not trainer:
            raise HTTPException(status_code=404, detail="Тренер не найден")
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM clients WHERE trainer_id = ?",
            (trainer_id,)
        )
        clients = [row_to_dict(row) for row in cursor.fetchall()]
        result = dict(trainer)
        result["clients"] = clients
        return result

@app.get("/api/trainers", response_model=List[dict])
async def get_trainers(status: Optional[str] = None):
    with get_db_connection() as conn:
        cursor = conn.cursor()
        if status:
            cursor.execute("SELECT * FROM trainers WHERE status = ?", (status,))
        else:
            cursor.execute("SELECT * FROM trainers")
        rows = cursor.fetchall()
        return [row_to_dict(row) for row in rows]

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)