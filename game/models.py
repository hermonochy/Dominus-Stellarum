from dataclasses import dataclass
from typing import Optional

import pygame


@dataclass
class Empire:
    id: int
    name: str
    color: tuple[int, int, int]
    is_player: bool = False
    alive: bool = True


@dataclass
class StarSystem:
    id: int
    name: str
    pos: pygame.Vector2
    production: float
    ships: float
    owner_id: Optional[int] = None


@dataclass
class Fleet:
    id: int
    owner_id: int
    source_id: int
    target_id: int
    ships: float
    progress: float = 0.0
    route: tuple[int, ...] = ()
    route_index: int = 1