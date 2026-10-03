from __future__ import annotations

import random

import pygame

from . import config
from .models import CombatShot, Fleet, StarSystem

def _hit_probability(ship_count: float) -> float:
    if ship_count <= 0:
        return 0.0

    hit_prob = ship_count / (ship_count + config.HIT_K)

    return min(1.0, hit_prob)

def _spawn_shots(
    attacker_pos: pygame.Vector2,
    defender_pos: pygame.Vector2,
    attacker_color: tuple[int, int, int],
    defender_color: tuple[int, int, int],
    attacker_ships: float,
    defender_ships: float,
    dt: float,
    rng: random.Random,
) -> list[CombatShot]:
    shots: list[CombatShot] = []

    attacker_shot_count = max(
        1,
        int(config.ATTACKER_SHOTS_PER_SECOND * dt * min(3, attacker_ships / 5)),
    )

    defender_shot_count = max(
        1,
        int(config.DEFENDER_SHOTS_PER_SECOND * dt * min(3, defender_ships / 5)),
    )

    for _ in range(attacker_shot_count):
        start = attacker_pos.copy() + pygame.Vector2(
            rng.uniform(-8, 8),
            rng.uniform(-8, 8),
        )
        end = defender_pos.copy() + pygame.Vector2(
            rng.uniform(-15, 15),
            rng.uniform(-15, 15),
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
        start = defender_pos.copy() + pygame.Vector2(
            rng.uniform(-20, 20),
            rng.uniform(-20, 20),
        )
        end = attacker_pos.copy() + pygame.Vector2(
            rng.uniform(-8, 8),
            rng.uniform(-8, 8),
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

def resolve_engagement(
    attacker,
    defender,
    attacker_pos: pygame.Vector2,
    defender_pos: pygame.Vector2,
    dt: float,
    attacker_dps_per_ship: float,
    defender_dps_per_ship: float,
    attacker_color: tuple[int, int, int],
    defender_color: tuple[int, int, int],
    rng: random.Random,
    attacker_is_system: bool = False,
    defender_is_system: bool = False,
) -> list[CombatShot]:
    # Bodies below the combat threshold cannot fight or be fought
    if attacker.owner_id == defender.owner_id:
        return []

    if attacker.ships <= config.COMBAT_MIN_SHIPS:
        return []

    if defender.ships <= config.COMBAT_MIN_SHIPS:
        return []

    distance = attacker_pos.distance_to(defender_pos)
    
    if distance > config.COMBAT_RANGE:
        return []

    attacker_jitter = rng.uniform(
        config.COMBAT_JITTER_MIN,
        config.COMBAT_JITTER_MAX,
    )
    defender_jitter = rng.uniform(
        config.COMBAT_JITTER_MIN,
        config.COMBAT_JITTER_MAX,
    )

    if attacker_is_system:
        actual_attacker_dps = attacker_dps_per_ship * config.DEFENDER_BONUS
    else:
        actual_attacker_dps = attacker_dps_per_ship

    if defender_is_system:
        actual_defender_dps = defender_dps_per_ship * config.DEFENDER_BONUS
    else:
        actual_defender_dps = defender_dps_per_ship

    attacker_hit_prob = _hit_probability(defender.ships)
    defender_hit_prob = _hit_probability(attacker.ships)

    raw_attacker_damage = (
        attacker.ships
        * actual_attacker_dps
        * dt
        * attacker_jitter
    )
    raw_defender_damage = (
        defender.ships
        * actual_defender_dps
        * dt
        * defender_jitter
    )

    actual_attacker_damage = raw_attacker_damage * attacker_hit_prob
    actual_defender_damage = raw_defender_damage * defender_hit_prob

    attacker.ships = max(0.0, attacker.ships - actual_defender_damage)
    defender.ships = max(0.0, defender.ships - actual_attacker_damage)

    if attacker.ships < config.COMBAT_MIN_SHIPS:
        attacker.ships = 0.0

    if defender.ships < config.COMBAT_MIN_SHIPS:
        defender.ships = 0.0

    return _spawn_shots(
        attacker_pos,
        defender_pos,
        attacker_color,
        defender_color,
        attacker.ships,
        defender.ships,
        dt,
        rng,
    )

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