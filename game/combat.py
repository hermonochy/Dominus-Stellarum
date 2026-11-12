from __future__ import annotations

import random
from typing import Optional

import pygame

from . import config
from .models import Fleet, StarSystem

def gun_range(entity) -> float:
    ships = max(1.0, entity.ships)
    range_value = config.GUN_RANGE_BASE * ships ** config.GUN_RANGE_EXPONENT
    if isinstance(entity, Fleet):
        range_value *= config.FLEET_GUN_RANGE_MULT
    return range_value

def escort_range(ships) -> float:
    range_value = config.GUN_RANGE_BASE * ships ** config.GUN_RANGE_EXPONENT
    return range_value

def _hit_probability(ship_count: float) -> float:
    if ship_count <= 0:
        return 0.0

    hit_prob = ship_count / (ship_count + config.HIT_K)

    return min(1.0, hit_prob)

def fire_at_target(
    shooter,
    target,
    shooter_pos: pygame.Vector2,
    target_pos: pygame.Vector2,
    dt: float,
    dps_per_ship: float,
    rng: random.Random,
    shooter_is_system: bool = False,
    max_effective_ships: Optional[float] = None,
) -> None:
    if shooter.owner_id == target.owner_id:
        return

    if shooter.owner_id is None or shooter.ships <= config.COMBAT_MIN_SHIPS:
        return

    if target.owner_id is None or target.ships <= config.COMBAT_MIN_SHIPS:
        return

    distance = shooter_pos.distance_to(target_pos)
    if distance > gun_range(shooter):
        return

    jitter = rng.uniform(
        config.COMBAT_JITTER_MIN,
        config.COMBAT_JITTER_MAX,
    )

    effective_ships = shooter.ships
    if max_effective_ships is not None:
        effective_ships = min(effective_ships, max_effective_ships)

    actual_dps = dps_per_ship * (config.DEFENDER_BONUS if shooter_is_system else 1.0)
    hit_prob = _hit_probability(target.ships)

    damage = effective_ships * actual_dps * dt * jitter * hit_prob

    target.ships = max(0.0, target.ships - damage)

    if target.ships < config.COMBAT_MIN_SHIPS:
        target.ships = 0.0

def resolve_fleet_arrival(
    fleet: Fleet,
    target: StarSystem,
) -> None:
    if fleet.ships <= config.COMBAT_MIN_SHIPS:
        return

    if target.owner_id == fleet.owner_id:
        target.ships += fleet.ships
        return

    if target.ships <= config.COMBAT_MIN_SHIPS:
        target.owner_id = fleet.owner_id
        target.ships = fleet.ships
        return

    if fleet.ships > target.ships:
        target.owner_id = fleet.owner_id
        target.ships = fleet.ships - target.ships
    else:
        target.ships -= fleet.ships
        if target.ships < config.COMBAT_MIN_SHIPS:
            target.ships = 0.0
