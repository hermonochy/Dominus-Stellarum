from __future__ import annotations

import random

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
    rng: random.Random,
) -> list[CombatShot]:
    if target.owner_id == fleet.owner_id:
        return []

    if fleet.ships <= 0.01:
        return []

    if target.ships <= 0.01:
        return []

    distance = fleet_position.distance_to(target.pos)

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

    fleet.ships = max(
        0.0,
        fleet.ships - defender_damage,
    )

    target.ships = max(
        0.0,
        target.ships - attacker_damage,
    )

    shots: list[CombatShot] = []

    attacker_shot_count = max(
        1,
        round(
            config.ATTACKER_SHOTS_PER_SECOND
            * dt
        ),
    )

    defender_shot_count = max(
        1,
        round(
            config.DEFENDER_SHOTS_PER_SECOND
            * dt
        ),
    )

    for _ in range(attacker_shot_count):
        start = fleet_position.copy()
        end = target.pos.copy()

        start += pygame.Vector2(
            rng.uniform(-5, 5),
            rng.uniform(-5, 5),
        )

        end += pygame.Vector2(
            rng.uniform(-12, 12),
            rng.uniform(-12, 12),
        )

        shots.append(
            CombatShot(
                start=start,
                end=end,
                color=attacker_color,
                lifetime=config.SHOT_LIFETIME,
                max_lifetime=config.SHOT_LIFETIME,
            )
        )

    for _ in range(defender_shot_count):
        start = target.pos.copy()
        end = fleet_position.copy()

        start += pygame.Vector2(
            rng.uniform(-12, 12),
            rng.uniform(-12, 12),
        )

        end += pygame.Vector2(
            rng.uniform(-5, 5),
            rng.uniform(-5, 5),
        )

        shots.append(
            CombatShot(
                start=start,
                end=end,
                color=defender_color,
                lifetime=config.SHOT_LIFETIME,
                max_lifetime=config.SHOT_LIFETIME,
            )
        )

    return shots


def resolve_fleet_arrival(
    fleet: Fleet,
    target: StarSystem,
) -> None:
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
        target.ships = (
            fleet.ships - target.ships
        )
    else:
        target.ships -= fleet.ships