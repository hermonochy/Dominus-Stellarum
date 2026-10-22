# ai.py
import random
from typing import List, Tuple

from . import config
from .galaxy import Galaxy
from .models import StarSystem

class AIController:
    def __init__(self, galaxy: Galaxy):
        self.galaxy = galaxy
        self.rng = random.Random()
        self.think_timer = 0.0
        self.attack_cooldowns: dict[tuple[int, int], float] = {}
        self.blitz_target: dict[int, int | None] = {}
        self.breakthrough_focus: dict[int, int | None] = {}
        self.breakthrough_timer: dict[int, float] = {}
        self.massing_focus: dict[int, int | None] = {}
        self.massing_stage_point: dict[int, int | None] = {}
        self.massing_timer: dict[int, float] = {}
        self.nuclear_lockouts: dict[int, float] = {}
        self.dominance_detected: dict[int, float] = {}
        self.spite_detectors: dict[int, float] = {}

    def update(self, dt: float) -> None:
        self.think_timer += dt
        for pair in list(self.attack_cooldowns):
            self.attack_cooldowns[pair] -= dt
            if self.attack_cooldowns[pair] <= 0.0:
                del self.attack_cooldowns[pair]

        for empire_id in list(self.breakthrough_timer.keys()):
            self.breakthrough_timer[empire_id] -= dt
            if self.breakthrough_timer[empire_id] <= 0.0:
                self.breakthrough_focus[empire_id] = None
                del self.breakthrough_timer[empire_id]

        for empire_id in list(self.massing_timer.keys()):
            self.massing_timer[empire_id] -= dt
            if self.massing_timer[empire_id] <= 0.0:
                self.massing_focus[empire_id] = None
                self.massing_stage_point[empire_id] = None
                del self.massing_timer[empire_id]

        for empire_id in list(self.nuclear_lockouts.keys()):
            self.nuclear_lockouts[empire_id] -= dt
            if self.nuclear_lockouts[empire_id] <= 0.0:
                del self.nuclear_lockouts[empire_id]

        for empire_id in list(self.dominance_detected.keys()):
            self.dominance_detected[empire_id] -= dt

        for empire_id in list(self.spite_detectors.keys()):
            self.spite_detectors[empire_id] -= dt
            if self.spite_detectors[empire_id] <= 0.0:
                del self.spite_detectors[empire_id]

        if self.think_timer < config.AI_THINK_INTERVAL:
            return
        self.think_timer -= config.AI_THINK_INTERVAL

        for empire in self.galaxy.empires:
            if not empire.alive:
                continue
            if empire.is_player and not self.galaxy.autopilot:
                continue
            self._think_for_empire(empire.id)

    def _nuclear_target_score(self, system: StarSystem) -> float:
        inbound = sum(
            fleet.ships
            for fleet in self.galaxy.fleets
            if not fleet.is_missile
            and fleet.target_id == system.id
            and fleet.owner_id == system.owner_id
        )
        return system.ships + inbound + (system.production * config.NUCLEAR_PRODUCTION_TARGET_WEIGHT)

    def _consider_nuclear_launch(self, empire_id: int) -> None:
        empire = self.galaxy.empires[empire_id]
        if empire.missiles_remaining <= 0:
            return
        if self.nuclear_lockouts.get(empire_id, 0.0) > 0.0:
            return
        if self.galaxy.nuclear_cooldown > 0.0:
            return

        powers = sorted(
            (
                (self.galaxy.empire_ship_count(other.id), other.id, other.is_player)
                for other in self.galaxy.empires
                if other.alive
            ),
            reverse=True,
        )
        if len(powers) < 2:
            return

        top_power, top_id, top_is_player = powers[0]
        second_power = powers[1][0]
        
        total_galactic = sum(power for power, eid, _ in powers)
        if total_galactic <= 0:
            return
            
        top_share = top_power / total_galactic
        pairwise_ratio = top_power / max(1.0, second_power)

        dominant = (
            pairwise_ratio >= config.NUCLEAR_DOMINANCE_RATIO or
            top_share >= config.NUCLEAR_SHARE_THRESHOLD
        )

        min_threshold = config.NUCLEAR_MIN_RUNAWAY_START_MULT * config.STARTING_SHIPS
        if top_power < min_threshold:
            dominant = False

        if dominant:
            if self.dominance_detected.get(top_id, 0.0) <= 0.0:
                self.dominance_detected[top_id] = config.NUCLEAR_DELIBERATION_TIME
            else:
                self.dominance_detected[top_id] -= config.AI_THINK_INTERVAL
        else:
            self.dominance_detected[top_id] = 0.0

        if self.dominance_detected.get(top_id, 0.0) > 0.0:
            if self.rng.random() >= config.NUCLEAR_LAUNCH_CHANCE:
                return

            targets = [
                system for system in self.galaxy.systems
                if system.owner_id == top_id
                and system.id not in self.galaxy.nuked_grace
            ]
            
            if not targets:
                targets = [
                    system for system in self.galaxy.systems
                    if system.owner_id == top_id
                ]
            
            if not targets:
                return

            best = max(targets, key=self._nuclear_target_score)
            target_system = best

            origin = min(
                (system for system in self.galaxy.systems 
                 if system.owner_id == empire_id),
                key=lambda system: system.pos.distance_to(target_system.pos),
                default=None,
            )
            if origin is None:
                return

            if self.galaxy._launch_nuclear(origin.id, target_system.id):
                self.nuclear_lockouts[empire_id] = config.NUCLEAR_LAUNCH_LOCKOUT

    def _consider_spite_launch(self, empire_id: int) -> None:
        empire = self.galaxy.empires[empire_id]
        if empire.missiles_remaining <= 0:
            return
        if self.nuclear_lockouts.get(empire_id, 0.0) > 0.0:
            return

        systems_owned = self.galaxy.empire_system_count(empire_id)
        if systems_owned > config.NUCLEAR_SPITE_SYSTEM_THRESHOLD:
            return

        powers = sorted(
            (
                (self.galaxy.empire_ship_count(other.id), other.id)
                for other in self.galaxy.empires
                if other.alive and other.id != empire_id
            ),
            reverse=True,
        )
        if not powers:
            return

        target_power, target_id = powers[0]

        if self.rng.random() < config.NUCLEAR_LAUNCH_CHANCE:
            if target_id in self.spite_detectors:
                self.spite_detectors[target_id] += config.AI_THINK_INTERVAL
            else:
                self.spite_detectors[target_id] = config.AI_THINK_INTERVAL

        if self.spite_detectors.get(target_id, 0.0) <= config.NUCLEAR_DELIBERATION_TIME * 0.5:
            return

        targets = [
            system for system in self.galaxy.systems
            if system.owner_id == target_id
            and system.id not in self.galaxy.nuked_grace
        ]
        if not targets:
            targets = [
                system for system in self.galaxy.systems
                if system.owner_id == target_id
            ]
        if not targets:
            return
        
        targets_sorted = sorted(targets, key=self._nuclear_target_score, reverse=True)
        num_missiles = empire.missiles_remaining
        
        launched = 0
        used_targets = set()
        
        for missile_idx in range(min(num_missiles, len(targets_sorted))):
            for candidate in targets_sorted:
                if candidate.id in used_targets:
                    continue
                target = candidate
                break
            else:
                break
            
            origin = min(
                (system for system in self.galaxy.systems 
                 if system.owner_id == empire_id),
                key=lambda system: system.pos.distance_to(target.pos),
                default=None,
            )
            if origin is None:
                break
            
            if self.galaxy._launch_nuclear(origin.id, target.id, ignore_cooldown=True):
                launched += 1
                used_targets.add(target.id)
            else:
                break
                
            if launched >= num_missiles:
                break
        
        empire.missiles_remaining = 0
        self.nuclear_lockouts[empire_id] = config.NUCLEAR_LAUNCH_LOCKOUT

    def _adjacent_enemy_empires(self, empire_id: int) -> dict[int, float]:
        border_ids: set[int] = set()
        for system in self.galaxy.systems:
            if system.owner_id != empire_id:
                continue
            for nid in self.galaxy.neighbors[system.id]:
                owner = self.galaxy.systems[nid].owner_id
                if owner is None or owner == empire_id:
                    continue
                border_ids.add(owner)
        return {eid: self.galaxy.empire_ship_count(eid) for eid in border_ids}

    def _identify_front_lines(self, empire_id: int) -> set[int]:
        frontier: set[int] = set()
        for system in self.galaxy.systems:
            if system.owner_id != empire_id:
                continue
            for nid in self.galaxy.neighbors[system.id]:
                if self.galaxy.systems[nid].owner_id != empire_id:
                    frontier.add(system.id)
                    break
        return frontier

    def _count_total_surplus(self, empire_id: int, front_lines: set[int]) -> float:
        surplus = 0.0
        for system in self.galaxy.systems:
            if system.owner_id != empire_id or system.id in front_lines:
                continue
            excess = system.ships - config.AI_REAR_GUARD_MAX
            if excess > 0:
                surplus += excess
        return surplus

    def _find_best_breakthrough_target(self, empire_id: int, front_lines: set[int]) -> int | None:
        enemy_strength_by_neighbor: dict[int, float] = {}
        for fid in front_lines:
            for nid in self.galaxy.neighbors[fid]:
                neighbor = self.galaxy.systems[nid]
                if neighbor.owner_id is not None and neighbor.owner_id != empire_id:
                    enemy_strength_by_neighbor[neighbor.id] = enemy_strength_by_neighbor.get(neighbor.id, 0.0) + neighbor.ships

        if not enemy_strength_by_neighbor:
            return None

        weakest_enemy = min(enemy_strength_by_neighbor.values())
        candidates = [sid for sid, strength in enemy_strength_by_neighbor.items() if strength <= weakest_enemy * 1.5]

        if not candidates:
            return None

        return min(candidates)

    def _try_initiate_massing_campaign(self, empire_id: int, front_lines: set[int]) -> bool:
        if self.rng.random() >= config.AI_MASSING_CHANCE:
            return False

        total_ships = self.galaxy.empire_ship_count(empire_id)
        front_reserves = sum(
            self.galaxy.systems[fid].ships
            for fid in front_lines
            if self.galaxy.systems[fid].owner_id == empire_id
        )

        surplus = total_ships - front_reserves - config.AI_MASSING_MIN_SURPLUS
        if surplus < config.AI_MASSING_MIN_SURPLUS:
            return False

        if self._count_adjacent_enemies(empire_id) < 1:
            return False

        stage_candidate = self._find_best_staging_point(empire_id, front_lines)
        if stage_candidate is None:
            return False

        target_empire = self._find_primary_massing_target(empire_id)
        if target_empire is None:
            return False

        self.massing_focus[empire_id] = target_empire
        self.massing_stage_point[empire_id] = stage_candidate
        self.massing_timer[empire_id] = config.AI_MASSING_FOCUS_DURATION
        return True

    def _count_adjacent_enemies(self, empire_id: int) -> int:
        seen: set[int] = set()
        for system in self.galaxy.systems:
            if system.owner_id != empire_id:
                continue
            for nid in self.galaxy.neighbors[system.id]:
                owner = self.galaxy.systems[nid].owner_id
                if owner is not None and owner != empire_id:
                    seen.add(owner)
        return len(seen)

    def _find_best_staging_point(self, empire_id: int, front_lines: set[int]) -> int | None:
        best: tuple[float, int] | None = None
        for fid in front_lines:
            system = self.galaxy.systems[fid]
            if system.owner_id != empire_id:
                continue
            friendly_neighbors = sum(
                1
                for nid in self.galaxy.neighbors[fid]
                if self.galaxy.systems[nid].owner_id == empire_id
            )
            score = system.ships + friendly_neighbors * 10.0
            if best is None or score > best[0]:
                best = (score, fid)
        return best[1] if best is not None else None

    def _find_primary_massing_target(self, empire_id: int) -> int | None:
        adjacent = self._adjacent_enemy_empires(empire_id)
        if not adjacent:
            return None
        return min(adjacent, key=lambda eid: adjacent[eid])

    def _maintain_massing_campaign(self, empire_id: int) -> None:
        if empire_id not in self.massing_focus or self.massing_focus[empire_id] is None:
            return
        stage_id = self.massing_stage_point.get(empire_id)
        if stage_id is None:
            return
        stage = self.galaxy.systems[stage_id]
        if stage.owner_id != empire_id:
            self.massing_focus[empire_id] = None
            self.massing_stage_point[empire_id] = None
            return

        for system in self.galaxy.systems:
            if system.owner_id != empire_id or system.id == stage_id:
                continue
            if system.id in self.galaxy.gathering_points:
                continue
            excess = system.ships - config.AI_MASSING_STAGE_RETENTION
            if excess < 1.0:
                continue
            front_lines = self._identify_front_lines(empire_id)
            if system.id in front_lines:
                continue
            amount = int(excess * config.AI_MASSING_LAUNCH_PERCENT / 100.0)
            if amount < 1:
                continue
            route = self.galaxy._safe_route(system.id, stage_id, empire_id)
            if route is None:
                continue
            self.galaxy._launch_exact(system.id, stage_id, amount, route)

    def _execute_massing_assault(self, empire_id: int) -> None:
        focus_id = self.massing_focus.get(empire_id)
        stage_id = self.massing_stage_point.get(empire_id)
        if focus_id is None or stage_id is None:
            return

        staging_power = self.galaxy.systems[stage_id].ships
        targets = [
            system
            for system in self.galaxy.systems
            if system.owner_id == focus_id
        ]
        if not targets:
            self.massing_focus[empire_id] = None
            self.massing_stage_point[empire_id] = None
            return

        target_empire_ships = self.galaxy.empire_ship_count(focus_id)
        if staging_power < target_empire_ships / config.AI_MASSING_TARGET_RATIO:
            return

        target = min(
            targets,
            key=lambda system: self.galaxy.systems[stage_id].pos.distance_to(system.pos),
        )
        if self.galaxy.launch_fleet(stage_id, target.id, 100):
            self.massing_focus[empire_id] = None
            self.massing_stage_point[empire_id] = None

    def _try_expansion(self, empire_id: int, budget: int) -> int:
        expansions = 0
        owned = [
            system for system in self.galaxy.systems
            if system.owner_id == empire_id
        ]
        for system in owned:
            if expansions >= budget:
                break
            if system.ships < config.AI_ATTACK_THRESHOLD:
                continue
            candidates: list[tuple[float, int]] = []
            for nid in self.galaxy.neighbors[system.id]:
                neighbor = self.galaxy.systems[nid]
                if neighbor.owner_id == empire_id:
                    continue
                is_neutral = neighbor.owner_id is None
                bonus = config.AI_NEUTRAL_PRIORITY_BONUS if is_neutral else 0.0
                score = neighbor.ships - bonus + system.pos.distance_to(neighbor.pos) * 0.1
                candidates.append((score, nid))
            if not candidates:
                continue
            candidates.sort()
            for score, nid in candidates:
                neighbor = self.galaxy.systems[nid]
                required = neighbor.ships * config.AI_MIN_ATTACK_RATIO
                if system.ships <= required:
                    continue
                pair = (empire_id, nid)
                if self.attack_cooldowns.get(pair, 0.0) > 0.0:
                    continue
                if self.galaxy.launch_fleet(system.id, nid, 90):
                    self.attack_cooldowns[pair] = config.AI_COOLDOWN
                    expansions += 1
                    break
        return expansions

    def _try_defense(self, empire_id: int) -> None:
        threats: dict[int, float] = {}
        for fleet in self.galaxy.fleets:
            if fleet.is_missile:
                continue
            if fleet.owner_id == empire_id:
                continue
            if fleet.ships <= config.COMBAT_MIN_SHIPS:
                continue
            threats[fleet.target_id] = threats.get(fleet.target_id, 0.0) + fleet.ships

        for target_id, threat in threats.items():
            target = self.galaxy.systems[target_id]
            if target.owner_id != empire_id:
                continue
            if target.ships >= threat * config.AI_MIN_ATTACK_RATIO:
                continue
            responders: list[tuple[float, int]] = []
            for system in self.galaxy.systems:
                if system.owner_id != empire_id or system.id == target_id:
                    continue
                if system.id in self._identify_front_lines(empire_id):
                    continue
                excess = system.ships - config.AI_REAR_GUARD_MAX
                if excess < 1.0:
                    continue
                route = self.galaxy.shortest_path(system.id, target_id)
                if route is None:
                    continue
                responders.append((len(route), system.id))
            if not responders:
                continue
            responders.sort()
            for hops, responder_id in responders[: config.AI_MAX_REAR_DISPATCHES]:
                responder = self.galaxy.systems[responder_id]
                amount = int(responder.ships * config.AI_REAR_SEND_PERCENT / 100.0)
                if amount < 1:
                    continue
                route = self.galaxy.shortest_path(responder_id, target_id)
                if route is None:
                    continue
                self.galaxy._launch_exact(responder_id, target_id, amount, route)

    def _try_blitz(self, empire_id: int) -> None:
        blitz_target = self.blitz_target.get(empire_id)
        if blitz_target is None:
            return
        target = self.galaxy.systems[blitz_target]
        attackers = [
            system
            for system in self.galaxy.systems
            if system.owner_id == empire_id
            and system.id in self.galaxy.neighbors.get(blitz_target, ())
        ]
        if not attackers or target.owner_id == empire_id:
            self.blitz_target[empire_id] = None
            return

        total_available = sum(system.ships for system in attackers)
        if total_available < target.ships * config.AI_BLITZ_LOCAL_RATIO:
            return

        launched = 0
        for system in sorted(attackers, key=lambda s: s.ships, reverse=True):
            if launched >= config.AI_BLITZ_WAVE_SIZE:
                break
            if system.ships < target.ships / max(1, len(attackers)):
                continue
            if self.galaxy.launch_fleet(system.id, blitz_target, 80):
                launched += 1
        if launched > 0:
            self.blitz_target[empire_id] = None

    def _maintain_breakthrough(self, empire_id: int) -> None:
        focus_id = self.breakthrough_focus.get(empire_id)
        if focus_id is None:
            return
        target = self.galaxy.systems[focus_id]
        if target.owner_id == empire_id:
            self.breakthrough_focus[empire_id] = None
            return

        border = [
            system
            for system in self.galaxy.systems
            if system.owner_id == empire_id
            and any(
                self.galaxy.systems[nid].owner_id == target.owner_id
                for nid in self.galaxy.neighbors[system.id]
            )
        ]
        for system in border:
            excess = system.ships - config.AI_FRONT_LINE_RESERVE
            if excess < config.AI_BREAKTHROUGH_MIN_SURPLUS:
                continue
            amount = int(excess * config.AI_BREAKTHROUGH_CONCENTRATION)
            if amount < 1:
                continue
            self.galaxy.launch_fleet(system.id, focus_id, min(100, int(amount / system.ships * 100)))

    def _release_rear_ships(self, empire_id: int) -> None:
        front_lines = self._identify_front_lines(empire_id)
        if not front_lines:
            return
        dispatches = 0
        for system in self.galaxy.systems:
            if dispatches >= config.AI_MAX_REAR_DISPATCHES:
                break
            if system.owner_id != empire_id or system.id in front_lines:
                continue
            excess = system.ships - config.AI_REAR_GUARD_MAX * config.AI_REAR_RELEASE_MULTIPLIER
            if excess < config.AI_ATTACK_THRESHOLD:
                continue
            nearest_front = min(
                front_lines,
                key=lambda fid: system.pos.distance_to(self.galaxy.systems[fid].pos),
            )
            amount = int(excess * config.AI_REAR_SEND_PERCENT / 100.0)
            if amount < 1:
                continue
            route = self.galaxy._safe_route(system.id, nearest_front, empire_id)
            if route is None:
                route = self.galaxy.shortest_path(system.id, nearest_front)
            if route is None:
                continue
            if self.galaxy._launch_exact(system.id, nearest_front, amount, route):
                dispatches += 1

    def _think_for_empire(self, empire_id: int) -> None:
        owned = self.galaxy.empire_system_count(empire_id)
        if owned <= 0:
            return

        self._consider_nuclear_launch(empire_id)
        self._consider_spite_launch(empire_id)

        if self.massing_focus.get(empire_id) is not None:
            self._maintain_massing_campaign(empire_id)
            self._execute_massing_assault(empire_id)
        elif self.rng.random() < config.AI_MASSING_CHANCE:
            self._try_initiate_massing_campaign(
                empire_id, self._identify_front_lines(empire_id)
            )

        if self.breakthrough_focus.get(empire_id) is None:
            self.breakthrough_focus[empire_id] = self._find_best_breakthrough_target(
                empire_id, self._identify_front_lines(empire_id)
            )
            if self.breakthrough_focus.get(empire_id) is not None:
                self.breakthrough_timer[empire_id] = config.AI_BREAKTHROUGH_FOCUS_DURATION
        else:
            self._maintain_breakthrough(empire_id)

        self._try_defense(empire_id)
        self._try_expansion(empire_id, config.AI_MAX_EXPANSIONS_PER_TICK)
        self._try_blitz(empire_id)
        self._release_rear_ships(empire_id)

        if self.blitz_target.get(empire_id) is None:
            border_targets = [
                system
                for system in self.galaxy.systems
                if system.owner_id is not None and system.owner_id != empire_id
                and any(
                    self.galaxy.systems[nid].owner_id == empire_id
                    for nid in self.galaxy.neighbors.get(system.id, ())
                )
            ]
            if border_targets:
                strongest = max(border_targets, key=lambda s: s.ships)
                local_force = sum(
                    self.galaxy.systems[nid].ships
                    for nid in self.galaxy.neighbors[strongest.id]
                    if self.galaxy.systems[nid].owner_id == empire_id
                )
                if local_force >= strongest.ships * config.AI_BLITZ_POWER_RATIO:
                    self.blitz_target[empire_id] = strongest.id