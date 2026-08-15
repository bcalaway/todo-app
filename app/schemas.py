from datetime import datetime

from pydantic import BaseModel, ConfigDict


class CategoryCreate(BaseModel):
    name: str


class CategoryUpdate(BaseModel):
    name: str | None = None


class CategoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str


class TodoCreate(BaseModel):
    title: str
    category_id: int | None = None


class TodoUpdate(BaseModel):
    title: str | None = None
    completed: bool | None = None
    category_id: int | None = None


class TodoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    completed: bool
    created_at: datetime
    category_id: int | None = None
    category: CategoryOut | None = None
