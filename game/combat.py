from __future__ import annotations

import pygame

from . import config
from .models import CombatShot, Fleet, StarSystem


def resolve_fleet_combat(
    fleet: Fleet,
    fleet_position: pygame.Vector2,
    target: StarSystem,
    dt: float,
    attacker_color: tuple[int, int, int],
    defender_color: tuple[int, int, int],
) -> list[CombatShot]:
    """
    Resolve one frame of combat between an incoming fleet
    and the defenders of its target system.
    """

    if target.owner_id == fleet.owner_id:
        return []

    if fleet.ships <= 0.0:
        return []

    if target.ships <= 0.0:
        return []

    distance = fleet_position.distance_to(
        target.pos
    )

    if distance > config.COMBAT_RANGE:
        return []

    attacker_damage = (
        fleet.ships
        * config.ATTACKER_DAMAGE_PER_SHIP
        * dt
    )

    defender_damage = (
        target.ships
        * config.DEFENDER_DAMAGE_PER_SHIP
        * dt
    )

    target.ships = max(
        0.0,
        target.ships - attacker_damage,
    )

    fleet.ships = max(
        0.0,
        fleet.ships - defender_damage,
    )

    return [
        CombatShot(
            start=target.pos.copy(),
            end=fleet_position.copy(),
            color=defender_color,
            lifetime=config.SHOT_LIFETIME,
            max_lifetime=config.SHOT_LIFETIME,
        ),
        CombatShot(
            start=fleet_position.copy(),
            end=target.pos.copy(),
            color=attacker_color,
            lifetime=config.SHOT_LIFETIME,
            max_lifetime=config.SHOT_LIFETIME,
        ),
    ]


def resolve_fleet_arrival(
    fleet: Fleet,
    target: StarSystem,
) -> None:
    """
    Resolve what happens when a fleet reaches its final
    destination.
    """

    if fleet.ships <= 0.01:
        return

    if target.owner_id == fleet.owner_id:
        target.ships += fleet.ships
        return

    if target.ships <= 0.01:
        target.owner_id = fleet.owner_id
        target.ships = fleet.ships
        return

    if fleet.ships > target.ships:
        target.owner_id = fleet.owner_id
        target.ships = fleet.ships - target.ships
    else:
        target.ships -= fleet.ships