import random
import re
from datetime import datetime
from typing import Optional, List, Dict

from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel, Field, validator

# Валидаторы
def generate_unique_id(existing_ids: set) -> str:
    while True:
        new_id = ''.join(random.choices('0123456789', k=10))
        if new_id not in existing_ids:
            return new_id

def get_all_ids() -> set:
    return set(Client._clients_by_id.keys()) | set(Trainer._trainers_by_id.keys())

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

# Класс Person
class Person:
    def __init__(self, surname, name, phone, patronymic="", person_id=None):
        self.id = person_id if person_id is not None else generate_unique_id(get_all_ids())
        self.surname = surname
        self.name = name
        self.patronymic = patronymic
        self.phone = phone

    def to_dict(self):
        return {
            'id': self.id,
            'surname': self.surname,
            'name': self.name,
            'patronymic': self.patronymic,
            'phone': self.phone,
        }

# Класс Client
class Client(Person):
    _clients: List['Client'] = []
    _clients_by_id: Dict[str, 'Client'] = {}

    def __init__(self, surname, name, birthday, phone, email, is_active=True, patronymic="", client_id=None):
        super().__init__(surname, name, phone, patronymic, person_id=client_id)
        self.birthday = birthday
        self.email = email
        self.is_active = is_active
        self.trainer_id: Optional[str] = None

    def to_dict(self):
        d = super().to_dict()
        d.update({
            'birthday': self.birthday,
            'email': self.email,
            'is_active': self.is_active,
            'trainer_id': self.trainer_id,
        })
        return d

    def to_detail_dict(self):
        """Подробная информация с данными тренера."""
        d = self.to_dict()
        if self.trainer_id:
            trainer = Trainer.get(self.trainer_id)
            d['trainer'] = trainer.to_dict() if trainer else None
        else:
            d['trainer'] = None
        return d

    @classmethod
    def _save(cls, client: 'Client'):
        cls._clients.append(client)
        cls._clients_by_id[client.id] = client

    @classmethod
    def create(cls, surname: str, name: str, birthday: str, phone: str, email: str,
               is_active: bool = True, patronymic: str = "") -> 'Client':
        surname = validate_name(surname, "Фамилия")
        name = validate_name(name, "Имя")
        patronymic = patronymic.strip()
        phone = validate_phone(phone)
        email = validate_email(email)
        birthday = validate_birthday(birthday)
        new_id = generate_unique_id(get_all_ids())
        client = cls(surname, name, birthday, phone, email, is_active, patronymic, client_id=new_id)
        cls._save(client)
        return client

    @classmethod
    def get(cls, client_id: str) -> Optional['Client']:
        return cls._clients_by_id.get(client_id)

    @classmethod
    def get_all(cls, active_only: bool = False) -> List['Client']:
        if active_only:
            return [c for c in cls._clients if c.is_active]
        return cls._clients.copy()

    @classmethod
    def update(cls, client_id: str, **kwargs) -> 'Client':
        client = cls.get(client_id)
        if not client:
            raise ValueError("Клиент не найден")
        if 'surname' in kwargs:
            client.surname = validate_name(kwargs['surname'], "Фамилия")
        if 'name' in kwargs:
            client.name = validate_name(kwargs['name'], "Имя")
        if 'patronymic' in kwargs:
            client.patronymic = kwargs['patronymic'].strip()
        if 'phone' in kwargs:
            client.phone = validate_phone(kwargs['phone'])
        if 'email' in kwargs:
            client.email = validate_email(kwargs['email'])
        if 'birthday' in kwargs:
            client.birthday = validate_birthday(kwargs['birthday'])
        if 'is_active' in kwargs:
            client.is_active = kwargs['is_active']
        if 'trainer_id' in kwargs:
            client.trainer_id = kwargs['trainer_id']
        return client

    @classmethod
    def set_status(cls, client_id: str, is_active: bool) -> 'Client':
        """Изменить статус активности клиента."""
        return cls.update(client_id, is_active=is_active)

    @classmethod
    def assign_trainer(cls, client_id: str, trainer_id: str) -> 'Client':
        """Назначить тренера клиенту."""
        client = cls.get(client_id)
        if not client:
            raise ValueError("Клиент не найден")
        if trainer_id is not None:
            trainer = Trainer.get(trainer_id)
            if not trainer:
                raise ValueError("Тренер не найден")
        client.trainer_id = trainer_id
        return client

    @classmethod
    def delete(cls, client_id: str) -> bool:
        client = cls.get(client_id)
        if not client:
            return False
        cls._clients.remove(client)
        del cls._clients_by_id[client_id]
        return True

# Класс Trainer
class Trainer(Person):
    _trainers: List['Trainer'] = []
    _trainers_by_id: Dict[str, 'Trainer'] = {}

    def __init__(self, surname, name, phone, status, patronymic="", trainer_id=None):
        super().__init__(surname, name, phone, patronymic, person_id=trainer_id)
        self.status = status

    def to_dict(self):
        d = super().to_dict()
        d['status'] = self.status
        return d

    def to_detail_dict(self):
        """Подробная информация со списком клиентов."""
        d = self.to_dict()
        clients = Client.get_all(active_only=False)
        d['clients'] = [c.to_dict() for c in clients if c.trainer_id == self.id]
        return d

    @classmethod
    def _save(cls, trainer: 'Trainer'):
        cls._trainers.append(trainer)
        cls._trainers_by_id[trainer.id] = trainer

    @classmethod
    def create(cls, surname: str, name: str, phone: str, status: str, patronymic: str = "") -> 'Trainer':
        surname = validate_name(surname, "Фамилия")
        name = validate_name(name, "Имя")
        patronymic = patronymic.strip()
        phone = validate_phone(phone)
        status = validate_status(status)
        new_id = generate_unique_id(get_all_ids())
        trainer = cls(surname, name, phone, status, patronymic, trainer_id=new_id)
        cls._save(trainer)
        return trainer

    @classmethod
    def get(cls, trainer_id: str) -> Optional['Trainer']:
        return cls._trainers_by_id.get(trainer_id)

    @classmethod
    def get_all(cls, status: Optional[str] = None) -> List['Trainer']:
        if status:
            return [t for t in cls._trainers if t.status == status]
        return cls._trainers.copy()

    @classmethod
    def update(cls, trainer_id: str, **kwargs) -> 'Trainer':
        trainer = cls.get(trainer_id)
        if not trainer:
            raise ValueError("Тренер не найден")
        if 'surname' in kwargs:
            trainer.surname = validate_name(kwargs['surname'], "Фамилия")
        if 'name' in kwargs:
            trainer.name = validate_name(kwargs['name'], "Имя")
        if 'patronymic' in kwargs:
            trainer.patronymic = kwargs['patronymic'].strip()
        if 'phone' in kwargs:
            trainer.phone = validate_phone(kwargs['phone'])
        if 'status' in kwargs:
            trainer.status = validate_status(kwargs['status'])
        return trainer

    @classmethod
    def set_status(cls, trainer_id: str, status: str) -> 'Trainer':
        """Изменить статус тренера."""
        return cls.update(trainer_id, status=status)

    @classmethod
    def delete(cls, trainer_id: str) -> bool:
        trainer = cls.get(trainer_id)
        if not trainer:
            return False
        # Обнуляем trainer_id у всех клиентов этого тренера
        for client in Client.get_all():
            if client.trainer_id == trainer_id:
                client.trainer_id = None
        cls._trainers.remove(trainer)
        del cls._trainers_by_id[trainer_id]
        return True

# Создание тестовых данных
try:
    c1 = Client.create(
        surname='Ivanov',
        name='Ivan',
        birthday='01.01.2001',
        phone='88005353535',
        email='my_email@gmail.com',
        patronymic='Ivanovich'
    )
    t1 = Trainer.create(
        surname='Semenov',
        name='Semen',
        phone='81234567890',
        status='WORKING'
    )

    Client.assign_trainer(c1.id, t1.id)
except ValueError as e:
    print(f"Ошибка при создании тестовых данных: {e}")

# Pydantic модели для запросов
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

# Клиенты (/api/clients)
@app.post("/api/clients", response_model=dict, status_code=status.HTTP_201_CREATED)
async def create_client(client_data: ClientCreate):
    try:
        client = Client.create(
            surname=client_data.surname,
            name=client_data.name,
            patronymic=client_data.patronymic,
            birthday=client_data.birthday,
            phone=client_data.phone,
            email=client_data.email,
            is_active=client_data.is_active
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return client.to_dict()

@app.put("/api/clients/{client_id}", response_model=dict)
async def update_client(client_id: str, update_data: ClientUpdate):
    update_dict = {k: v for k, v in update_data.dict().items() if v is not None}
    if not update_dict:
        raise HTTPException(status_code=400, detail="Нет данных для обновления")
    try:
        client = Client.update(client_id, **update_dict)
    except ValueError as e:
        if "не найден" in str(e):
            raise HTTPException(status_code=404, detail=str(e))
        raise HTTPException(status_code=400, detail=str(e))
    return client.to_dict()

@app.get("/api/clients", response_model=List[dict])
async def get_clients(active_only: bool = False):
    return [c.to_dict() for c in Client.get_all(active_only=active_only)]

@app.get("/api/clients/{client_id}", response_model=dict)
async def get_client_short(client_id: str):
    client = Client.get(client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Клиент не найден")
    return client.to_dict()

@app.get("/api/clients/{client_id}/detail", response_model=dict)
async def get_client_detail(client_id: str):
    client = Client.get(client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Клиент не найден")
    return client.to_detail_dict()

@app.patch("/api/clients/{client_id}/status", response_model=dict)
async def update_client_status(client_id: str, status_data: ClientStatusUpdate):
    try:
        client = Client.set_status(client_id, status_data.is_active)
    except ValueError as e:
        if "не найден" in str(e):
            raise HTTPException(status_code=404, detail=str(e))
        raise HTTPException(status_code=400, detail=str(e))
    return client.to_dict()

@app.post("/api/clients/{client_id}/trainer/{trainer_id}", response_model=dict, status_code=status.HTTP_200_OK)
async def assign_trainer_to_client(client_id: str, trainer_id: str):
    try:
        client = Client.assign_trainer(client_id, trainer_id)
    except ValueError as e:
        if "не найден" in str(e):
            raise HTTPException(status_code=404, detail=str(e))
        raise HTTPException(status_code=400, detail=str(e))
    return client.to_dict()

# Тренеры (/api/trainers)
@app.post("/api/trainers", response_model=dict, status_code=status.HTTP_201_CREATED)
async def create_trainer(trainer_data: TrainerCreate):
    try:
        trainer = Trainer.create(
            surname=trainer_data.surname,
            name=trainer_data.name,
            patronymic=trainer_data.patronymic,
            phone=trainer_data.phone,
            status=trainer_data.status
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return trainer.to_dict()

@app.put("/api/trainers/{trainer_id}", response_model=dict)
async def update_trainer(trainer_id: str, update_data: TrainerUpdate):
    update_dict = {k: v for k, v in update_data.dict().items() if v is not None}
    if not update_dict:
        raise HTTPException(status_code=400, detail="Нет данных для обновления")
    try:
        trainer = Trainer.update(trainer_id, **update_dict)
    except ValueError as e:
        if "не найден" in str(e):
            raise HTTPException(status_code=404, detail=str(e))
        raise HTTPException(status_code=400, detail=str(e))
    return trainer.to_dict()

@app.patch("/api/trainers/{trainer_id}/status", response_model=dict)
async def update_trainer_status(trainer_id: str, status_data: TrainerStatusUpdate):
    try:
        trainer = Trainer.set_status(trainer_id, status_data.status)
    except ValueError as e:
        if "не найден" in str(e):
            raise HTTPException(status_code=404, detail=str(e))
        raise HTTPException(status_code=400, detail=str(e))
    return trainer.to_dict()

@app.get("/api/trainers/{trainer_id}/detail", response_model=dict)
async def get_trainer_detail(trainer_id: str):
    trainer = Trainer.get(trainer_id)
    if not trainer:
        raise HTTPException(status_code=404, detail="Тренер не найден")
    return trainer.to_detail_dict()

@app.get("/api/trainers", response_model=List[dict])
async def get_trainers(status: Optional[str] = None):
    return [t.to_dict() for t in Trainer.get_all(status=status)]


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)