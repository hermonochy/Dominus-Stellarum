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
    """Resolve combat between fleet and defending system."""
    
    # Early termination conditions
    if target.owner_id == fleet.owner_id:
        return []
    
    if fleet.ships <= 0.01:
        return []
    
    if target.ships <= 0.01:
        return []
    
    # Check engagement range
    distance = fleet_position.distance_to(target.pos)
    if distance > config.COMBAT_RANGE:
        return []
    
    # Calculate damage (balanced with defense bonus)
    attacker_damage = (
        fleet.ships
        * config.ATTACKER_DAMAGE_PER_SHIP
        * dt
    )
    
    # Defenders get position bonus
    defender_damage = (
        target.ships
        * config.DEFENDER_DAMAGE_PER_SHIP
        * dt
        * config.DEFENDER_BONUS
    )
    
    # Apply damage
    fleet.ships = max(0.0, fleet.ships - defender_damage)
    target.ships = max(0.0, target.ships - attacker_damage)
    
    # Generate visual combat shots
    shots: list[CombatShot] = []
    
    # More shots for larger engagements
    attacker_shot_count = max(
        1,
        int(config.ATTACKER_SHOTS_PER_SECOND * dt * min(3, fleet.ships / 5)),
    )
    
    defender_shot_count = max(
        1,
        int(config.DEFENDER_SHOTS_PER_SECOND * dt * min(3, target.ships / 5)),
    )
    
    # Attacker shots (fleet firing at system)
    for _ in range(attacker_shot_count):
        start = fleet_position.copy()
        end = target.pos.copy()
        
        # Add spread to shots
        start += pygame.Vector2(
            rng.uniform(-8, 8),
            rng.uniform(-8, 8),
        )
        
        end += pygame.Vector2(
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
    
    # Defender shots (system orbital batteries)
    for _ in range(defender_shot_count):
        start = target.pos.copy()
        end = fleet_position.copy()
        
        # Wider spread for defensive fire
        start += pygame.Vector2(
            rng.uniform(-20, 20),
            rng.uniform(-20, 20),
        )
        
        end += pygame.Vector2(
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


def resolve_fleet_arrival(
    fleet: Fleet,
    target: StarSystem,
) -> None:
    """Handle fleet arrival at destination system."""
    
    if fleet.ships <= 0.01:
        return
    
    # Reinforce friendly system
    if target.owner_id == fleet.owner_id:
        target.ships += fleet.ships
        return
    
    # Capture unowned system
    if target.ships <= 0.01:
        target.owner_id = fleet.owner_id
        target.ships = fleet.ships
        return
    
    # Combat resolution for enemy system
    if fleet.ships > target.ships:
        # Victory: capture system with remaining ships
        target.owner_id = fleet.owner_id
        target.ships = fleet.ships - target.ships
    else:
        # Defeat: attacker destroyed, defender weakened
        target.ships -= fleet.ships