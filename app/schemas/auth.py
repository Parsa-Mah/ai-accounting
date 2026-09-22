"""Pydantic schemas for authentication."""

from pydantic import BaseModel, Field


class Credentials(BaseModel):
    username: str = Field(min_length=1, max_length=50)
    password: str = Field(min_length=6, max_length=200)


class AuthStatus(BaseModel):
    configured: bool


class AuthUser(BaseModel):
    username: str
