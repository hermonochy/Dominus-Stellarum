# models.py
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
    missiles_remaining: int = 0


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
    segment_progress: float = 0.0
    route: tuple[int, ...] = ()
    route_index: int = 1
    position: pygame.Vector2 = None
    siege_target_id: Optional[int] = None
    is_missile: bool = False

    def __post_init__(self):
        if self.position is None:
            self.position = pygame.Vector2(0, 0)

@dataclass
class Explosion:
    pos: pygame.Vector2
    age: float
    max_age: float
    peak_radius: float

@dataclass
class CombatShot:
    start: pygame.Vector2
    end: pygame.Vector2
    color: tuple[int, int, int]
    lifetime: float
    max_lifetime: float