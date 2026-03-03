from __future__ import annotations

from dataclasses import dataclass

from fastapi import APIRouter


@dataclass(frozen=True)
class RouterSpec:
    router: APIRouter
    prefix: str = ""
    tags: tuple[str, ...] = ()

