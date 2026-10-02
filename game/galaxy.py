from __future__ import annotations

import math
import random
from typing import Optional

import pygame

from . import config
from .combat import resolve_engagement, resolve_fleet_arrival
from .models import CombatShot, Empire, Fleet, StarSystem

class Galaxy:
    def __init__(self, seed: Optional[int] = None):
        self.rng = random.Random(seed)
        self.systems: list[StarSystem] = []
        self.empires: list[Empire] = []
        self.fleets: list[Fleet] = []
        self.combat_shots: list[CombatShot] = []
        self.edges: set[tuple[int, int]] = set()
        self.neighbors: dict[int, set[int]] = {}
        self.next_fleet_id = 0
        self.gathering_points: set[int] = set()
        self.new_ship_accum: dict[int, float] = {}
        self.active_combat: dict[int, float] = {}
        self.generate()

    def generate(self) -> None:
        self.systems.clear()
        self.empires.clear()
        self.fleets.clear()
        self.combat_shots.clear()
        self.edges.clear()
        self.neighbors.clear()
        self.next_fleet_id = 0
        self.gathering_points.clear()
        self.new_ship_accum.clear()
        self.active_combat.clear()
        self._create_systems()
        self._create_empires()
        self._place_empires()

    def update(self, dt: float) -> None:
        self._produce_ships(dt)
        self._update_fleets(dt)
        self._update_standoff_combat(dt)
        self._update_empire_status()

    def _create_systems(self) -> None:
        center = pygame.Vector2(config.GALAXY_CENTER_X, config.GALAXY_CENTER_Y)
        num_arms = config.GALAXY_ARM_COUNT
        used_names: set[str] = set()
        positions: list[pygame.Vector2] = []
        system_data: list[tuple[str, float]] = []
        arm_tags: list[Optional[int]] = []

        prefixes = ["Al", "Ar", "Bel", "Ca", "Cor", "Del", "Er", "Fal", "Gal", "Hel", "Io", "Jan", "Kel", "Lor", "Mor", "Nor", "Or", "Pra", "Qua", "Ren", "Sol", "Tal", "Ur", "Vel", "Wex", "Xan", "Yar", "Zen"]
        suffixes = ["a", "ar", "ea", "en", "eron", "ia", "ion", "is", "on", "or", "os", "um", "us"]

        def too_close(pos: pygame.Vector2, min_dist: float) -> bool:
            return any(pos.distance_to(other) < min_dist for other in positions)

        def make_name() -> str:
            for _ in range(400):
                name = self.rng.choice(prefixes) + self.rng.choice(suffixes)
                if name not in used_names:
                    used_names.add(name)
                    return name
            name = f"Sys{len(used_names)}"
            used_names.add(name)
            return name

        core_count = max(25, int(config.STAR_COUNT * config.GALAXY_CORE_RATIO))
        placed_core = 0
        attempts = 0
        while placed_core < core_count and attempts < core_count * 30:
            attempts += 1
            r = config.GALAXY_CORE_RADIUS * math.sqrt(self.rng.random())
            theta = self.rng.random() * math.tau
            pos = center + pygame.Vector2(math.cos(theta) * r, math.sin(theta) * r)
            if too_close(pos, config.MIN_STAR_DISTANCE * 0.6):
                continue
            name = make_name()
            production = self.rng.uniform(config.PRODUCTION_MIN * 1.1, config.PRODUCTION_MAX * 1.1)
            positions.append(pos)
            system_data.append((name, production))
            arm_tags.append(None)
            placed_core += 1
        core_count = placed_core

        arm_budget = config.STAR_COUNT - len(positions) - int(config.STAR_COUNT * config.GALAXY_BRANCH_RATIO)
        arm_stars_per_arm = max(10, arm_budget // num_arms)
        arm_start_radius = config.GALAXY_CORE_RADIUS + 20.0

        for arm_idx in range(num_arms):
            arm_base_angle = (math.tau / num_arms) * arm_idx
            for i in range(arm_stars_per_arm):
                t = (i + self.rng.random()) / arm_stars_per_arm
                r = arm_start_radius * (config.ARM_MAX_RADIUS / arm_start_radius) ** t
                theta = arm_base_angle + t * math.pi * config.GALAXY_ARM_PITCH + self.rng.gauss(0.0, config.GALAXY_ARM_WIND * 0.5)
                r += self.rng.gauss(0.0, config.MIN_STAR_DISTANCE * 0.35)
                r = max(config.GALAXY_CORE_RADIUS + 5.0, r)
                pos = center + pygame.Vector2(math.cos(theta) * r, math.sin(theta) * r)
                if too_close(pos, config.MIN_STAR_DISTANCE * 0.7):
                    continue
                name = make_name()
                production_multiplier = 1.0 - (r / config.ARM_MAX_RADIUS) * 0.4
                production = self.rng.uniform(config.PRODUCTION_MIN * production_multiplier, config.PRODUCTION_MAX * production_multiplier)
                positions.append(pos)
                system_data.append((name, production))
                arm_tags.append(arm_idx)

        if len(positions) > core_count:
            branches_to_add = int(config.STAR_COUNT * config.GALAXY_BRANCH_RATIO)
            for _ in range(branches_to_add * 3):
                if len(positions) >= config.STAR_COUNT:
                    break
                branch_parent = self.rng.randrange(core_count, len(positions))
                parent_pos = positions[branch_parent]
                parent_relative = parent_pos - center
                parent_theta = math.atan2(parent_relative.y, parent_relative.x)
                branch_angle = parent_theta + self.rng.choice([-1, 1]) * self.rng.uniform(0.4, 0.8)
                branch_radius = parent_relative.length() + self.rng.uniform(30, 50)
                candidate = center + pygame.Vector2(math.cos(branch_angle) * branch_radius, math.sin(branch_angle) * branch_radius)
                if too_close(candidate, config.MIN_STAR_DISTANCE * 0.7):
                    continue
                name = make_name()
                production = self.rng.uniform(config.PRODUCTION_MIN, config.PRODUCTION_MAX)
                positions.append(candidate)
                system_data.append((name, production))
                arm_tags.append(arm_tags[branch_parent])

        self.system_arms = arm_tags
        for i, (pos, (name, prod)) in enumerate(zip(positions, system_data)):
            ships = float(self.rng.randint(config.NEUTRAL_SHIPS_MIN, config.NEUTRAL_SHIPS_MAX))
            self.systems.append(StarSystem(id=i, name=name, pos=pos, production=prod, ships=ships))
            self.neighbors[i] = set()

        self._build_lanes(positions)

    def _build_lanes(self, positions: list[pygame.Vector2]) -> None:
        n = len(positions)
        parent = list(range(n))

        def find(x: int) -> int:
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x

        def union(a: int, b: int) -> bool:
            ra, rb = find(a), find(b)
            if ra == rb:
                return False
            parent[ra] = rb
            return True

        def crosses_existing(a: int, b: int) -> bool:
            pa, pb = positions[a], positions[b]
            for e1, e2 in self.edges:
                if a in (e1, e2) or b in (e1, e2):
                    continue
                if self._segments_intersect(pa, pb, positions[e1], positions[e2]):
                    return True
            return False

        def add_lane(a: int, b: int) -> bool:
            if union(a, b):
                lane = (min(a, b), max(a, b))
                self.edges.add(lane)
                self.neighbors[a].add(b)
                self.neighbors[b].add(a)
                return True
            return False

        candidates: list[tuple[float, int, int]] = []
        for i in range(n):
            for j in range(i + 1, n):
                distance = positions[i].distance_to(positions[j])
                if config.EDGE_MIN_LENGTH <= distance <= config.EDGE_MAX_LENGTH:
                    candidates.append((distance, i, j))
        candidates.sort()

        for distance, i, j in candidates:
            if find(i) == find(j):
                continue
            if crosses_existing(i, j):
                continue
            add_lane(i, j)

        bridges = 0
        while bridges < n:
            groups: dict[int, list[int]] = {}
            for i in range(n):
                groups.setdefault(find(i), []).append(i)
            if len(groups) <= 1:
                break
            roots = list(groups)
            bridge_candidates: list[tuple[float, int, int]] = []
            for a_idx in range(len(roots)):
                for b_idx in range(a_idx + 1, len(roots)):
                    for a in groups[roots[a_idx]]:
                        for b in groups[roots[b_idx]]:
                            distance = positions[a].distance_to(positions[b])
                            if distance <= config.LANE_BRIDGE_MAX:
                                bridge_candidates.append((distance, a, b))
            if not bridge_candidates:
                best = None
                for a_idx in range(len(roots)):
                    for b_idx in range(a_idx + 1, len(roots)):
                        for a in groups[roots[a_idx]]:
                            for b in groups[roots[b_idx]]:
                                distance = positions[a].distance_to(positions[b])
                                if best is None or distance < best[0]:
                                    best = (distance, a, b)
                if best is None:
                    break
                distance, a, b = best
                add_lane(a, b)
                bridges += 1
                continue
            bridge_candidates.sort()
            added = False
            for distance, a, b in bridge_candidates:
                if find(a) == find(b):
                    continue
                if crosses_existing(a, b):
                    continue
                add_lane(a, b)
                added = True
                bridges += 1
                break
            if not added:
                distance, a, b = bridge_candidates[0]
                if add_lane(a, b):
                    bridges += 1
                else:
                    break

    @staticmethod
    def _segments_intersect(first: pygame.Vector2, second: pygame.Vector2, third: pygame.Vector2, fourth: pygame.Vector2) -> bool:
        def orientation(a: pygame.Vector2, b: pygame.Vector2, c: pygame.Vector2) -> float:
            return (b.x - a.x) * (c.y - a.y) - (b.y - a.y) * (c.x - a.x)
        first_orientation = orientation(first, second, third)
        second_orientation = orientation(first, second, fourth)
        third_orientation = orientation(third, fourth, first)
        fourth_orientation = orientation(third, fourth, second)
        return first_orientation * second_orientation < 0 and third_orientation * fourth_orientation < 0

    def _create_empires(self) -> None:
        for empire_id in range(config.EMPIRE_COUNT):
            self.empires.append(Empire(id=empire_id, name=config.EMPIRE_NAMES[empire_id % len(config.EMPIRE_NAMES)], color=config.EMPIRE_COLORS[empire_id % len(config.EMPIRE_COLORS)], is_player=(empire_id == config.PLAYER_ID)))

    def _place_empires(self) -> None:
        center = pygame.Vector2(config.GALAXY_CENTER_X, config.GALAXY_CENTER_Y)
        num_arms = config.GALAXY_ARM_COUNT
        num_empires = min(len(self.empires), config.EMPIRE_COUNT)

        arm_systems: list[list[StarSystem]] = [[] for _ in range(num_arms)]
        core_systems: list[StarSystem] = []
        for system, arm_idx in zip(self.systems, self.system_arms):
            if arm_idx is None:
                core_systems.append(system)
            else:
                arm_systems[arm_idx].append(system)

        for sector in arm_systems:
            sector.sort(key=lambda s: -s.pos.distance_to(center))

        chosen: list[int] = []

        def place(system: StarSystem, empire_id: int) -> None:
            system.owner_id = empire_id
            system.ships = config.STARTING_SHIPS
            chosen.append(system.id)

        def min_dist_to_placed(system: StarSystem) -> float:
            if not chosen:
                return math.inf
            return min(
                system.pos.distance_to(self.systems[cid].pos)
                for cid in chosen
            )

        arm_order = sorted(range(num_arms), key=lambda i: -len(arm_systems[i]))

        empire_id = 0
        for arm_idx in arm_order:
            if empire_id >= num_empires or not arm_systems[arm_idx]:
                continue
            place(arm_systems[arm_idx][0], empire_id)
            empire_id += 1

        pool = list(core_systems)
        while empire_id < num_empires and pool:
            best = max(pool, key=min_dist_to_placed)
            pool.remove(best)
            place(best, empire_id)
            empire_id += 1

        while empire_id < num_empires:
            candidates = [s for s in self.systems if s.id not in chosen]
            if not candidates:
                break
            best = max(candidates, key=min_dist_to_placed)
            place(best, empire_id)
            empire_id += 1

    def _empire_production_efficiency(self, owned_count: int, total_systems: int) -> float:
        if total_systems <= 0:
            return 1.0
        share = max(0.001, min(1.0, owned_count / total_systems))
        efficiency = config.PRODUCTION_PEAK_EFFICIENCY - config.PRODUCTION_CURVE_STEEPNESS * abs(share - config.PRODUCTION_PEAK_SHARE)
        efficiency = max(config.PRODUCTION_MIN_EFFICIENCY, efficiency)
        if share > config.PRODUCTION_ZERO_CROSS_IN:
            overrun = (share - config.PRODUCTION_ZERO_CROSS_IN) / (1.0 - config.PRODUCTION_ZERO_CROSS_IN)
            efficiency *= 1.0 - overrun
        return efficiency

    def _apply_combat_drain(self, system: StarSystem, dt: float) -> None:
        if system.id in self.active_combat and self.active_combat[system.id] > 0:
            damage_taken = self.active_combat[system.id] * dt * config.COMBAT_DRAIN_RATE
            if damage_taken > system.ships:
                system.ships = 0.0
            else:
                system.ships -= damage_taken

    def _produce_ships(self, dt: float) -> None:
        owned_counts: dict[int, int] = {}
        total_systems = len(self.systems)
        for system in self.systems:
            if system.owner_id is None:
                continue
            owned_counts[system.owner_id] = owned_counts.get(system.owner_id, 0) + 1

        for system in self.systems:
            if system.owner_id is None:
                continue
            owned_count = owned_counts.get(system.owner_id, 1)
            efficiency = self._empire_production_efficiency(owned_count, total_systems)

            active_penalty = 1.0
            if system.id in self.active_combat:
                active_penalty = max(0.3, 1.0 - self.active_combat[system.id] * 0.1)

            gain = system.production * dt / efficiency * active_penalty
            system.ships += gain

            self.new_ship_accum[system.id] = self.new_ship_accum.get(system.id, 0.0) + gain
            self.active_combat[system.id] = max(0.0, self.active_combat.get(system.id, 0.0) - dt * 2.0)

            if system.owner_id == config.PLAYER_ID and system.id not in self.gathering_points:
                if self.new_ship_accum[system.id] >= config.SHIP_DISPATCH_THRESHOLD:
                    self._dispatch_accumulated(system)

    def _dispatch_accumulated(self, system: StarSystem) -> None:
        accumulated = self.new_ship_accum[system.id]
        amount = int(accumulated)
        if amount < 1:
            return
        empire_id = system.owner_id
        best_score = None
        best_sid = None
        best_route = None
        for sid in self.gathering_points:
            if sid == system.id:
                continue
            target = self.systems[sid]
            pool = target.ships if target.owner_id == empire_id else 0.0
            route = self._safe_route(system.id, sid, empire_id)
            if route is None:
                continue
            hops = len(route) - 1
            score = config.GATHER_HOP_WEIGHT * hops + config.GATHER_SHIP_WEIGHT * pool
            if best_score is None or score < best_score:
                best_score = score
                best_sid = sid
                best_route = route
        if best_sid is None:
            return
        if self._launch_exact(system.id, best_sid, amount, best_route):
            self.new_ship_accum[system.id] = accumulated - amount

    def _launch_exact(self, source_id: int, target_id: int, amount: int, route: Optional[tuple[int, ...]] = None) -> bool:
        source = self.systems[source_id]
        if source.ships < amount:
            return False
        if route is None:
            route = self.shortest_path(source_id, target_id)
            if route is None or len(route) < 2:
                return False
        source.ships -= amount
        self.fleets.append(Fleet(id=self.next_fleet_id, owner_id=source.owner_id, source_id=source_id, target_id=target_id, ships=float(amount), route=route, route_index=1, segment_progress=0.0))
        self.next_fleet_id += 1
        return True

    def toggle_gathering_point(self, system_id: int) -> bool:
        if system_id not in self.neighbors:
            return False
        if system_id in self.gathering_points:
            self.gathering_points.discard(system_id)
            return True
        self.gathering_points.add(system_id)
        return True

    def shortest_path(self, source_id: int, target_id: int) -> Optional[tuple[int, ...]]:
        if source_id == target_id:
            return (source_id,)
        if source_id not in self.neighbors or target_id not in self.neighbors:
            return None
        queue: list[int] = [source_id]
        previous: dict[int, Optional[int]] = {source_id: None}
        while queue:
            current = queue.pop(0)
            for neighbor in self.neighbors[current]:
                if neighbor in previous:
                    continue
                previous[neighbor] = current
                if neighbor == target_id:
                    path = [target_id]
                    cursor = target_id
                    while previous[cursor] is not None:
                        cursor = previous[cursor]
                        path.append(cursor)
                    path.reverse()
                    return tuple(path)
                queue.append(neighbor)
        return None

    def _safe_route(self, source_id: int, target_id: int, empire_id: int) -> Optional[tuple[int, ...]]:
        if source_id == target_id:
            return (source_id,)
        if source_id not in self.neighbors or target_id not in self.neighbors:
            return None
        queue: list[int] = [source_id]
        previous: dict[int, Optional[int]] = {source_id: None}
        while queue:
            current = queue.pop(0)
            for neighbor in self.neighbors[current]:
                if neighbor in previous:
                    continue
                if neighbor != target_id:
                    node = self.systems[neighbor]
                    if node.owner_id not in (None, empire_id):
                        continue
                previous[neighbor] = current
                if neighbor == target_id:
                    path = [target_id]
                    cursor = target_id
                    while previous[cursor] is not None:
                        cursor = previous[cursor]
                        path.append(cursor)
                    path.reverse()
                    return tuple(path)
                queue.append(neighbor)
        return None

    def reachable_system_ids(self, source_id: int) -> set[int]:
        if source_id not in self.neighbors:
            return set()
        reachable: set[int] = set()
        queue: list[int] = [source_id]
        while queue:
            current = queue.pop(0)
            for neighbor in self.neighbors[current]:
                if neighbor in reachable:
                    continue
                reachable.add(neighbor)
                queue.append(neighbor)
        reachable.discard(source_id)
        return reachable

    def launch_fleet(self, source_id: int, target_id: int, send_percent: int) -> bool:
        if source_id < 0 or source_id >= len(self.systems):
            return False
        if target_id < 0 or target_id >= len(self.systems):
            return False
        source = self.systems[source_id]
        if source.owner_id is None:
            return False
        route = self.shortest_path(source_id, target_id)
        if route is None or len(route) < 2:
            return False
        fraction = max(0.0, min(1.0, send_percent / 100.0))
        amount = math.floor(source.ships * fraction)
        if amount < 1:
            return False
        source.ships -= amount
        self.fleets.append(Fleet(id=self.next_fleet_id, owner_id=source.owner_id, source_id=source_id, target_id=target_id, ships=float(amount), route=route, route_index=1, segment_progress=0.0))
        self.next_fleet_id += 1
        return True

    def fleet_position(self, fleet: Fleet) -> pygame.Vector2:
        source = self.systems[fleet.source_id]
        target = self.systems[fleet.target_id]
        return source.pos.lerp(target.pos, min(1.0, fleet.progress))

    def _update_fleets(self, dt: float) -> None:
        arrived: list[Fleet] = []
        for shot in self.combat_shots:
            shot.lifetime -= dt
        self.combat_shots = [shot for shot in self.combat_shots if shot.lifetime > 0.0]

        for fleet in list(self.fleets):
            if fleet.siege_target_id is not None:
                system = self.systems[fleet.siege_target_id]
                if system.owner_id != fleet.owner_id and system.ships > config.COMBAT_MIN_SHIPS:
                    fleet.position = system.pos
                    new_shots = resolve_engagement(fleet, system, fleet.position, system.pos, dt, config.ATTACKER_DAMAGE_PER_SHIP, config.DEFENDER_DAMAGE_PER_SHIP * config.DEFENDER_BONUS, self.empires[fleet.owner_id].color, self.empires[system.owner_id].color if system.owner_id is not None else config.NEUTRAL_COLOR, self.rng)
                    self.combat_shots.extend(new_shots)
                    self.active_combat[system.id] = self.active_combat.get(system.id, 0.0) + config.DEFENDER_DAMAGE_PER_SHIP * config.DEFENDER_BONUS
                    if fleet.ships <= config.COMBAT_MIN_SHIPS:
                        if fleet in self.fleets:
                            self.fleets.remove(fleet)
                    continue
                if system.owner_id != fleet.owner_id:
                    system.owner_id = fleet.owner_id
                    system.ships = 0.0
                fleet.siege_target_id = None
                fleet.segment_progress = 0.0

            current_id = fleet.route[fleet.route_index - 1]
            next_id = fleet.route[fleet.route_index] if fleet.route_index < len(fleet.route) else fleet.route[-1]
            current_system = self.systems[current_id]
            next_system = self.systems[next_id]
            segment_distance = current_system.pos.distance_to(next_system.pos)
            fleet.segment_progress += (config.FLEET_SPEED * dt) / max(1.0, segment_distance)

            if fleet.segment_progress <= 1.0:
                fleet.position = current_system.pos.lerp(next_system.pos, min(1.0, fleet.segment_progress))
            else:
                fleet.position = next_system.pos
                if fleet.route_index >= len(fleet.route) - 1:
                    fleet.progress = 1.0
                    arrived.append(fleet)
                else:
                    fleet.route_index += 1
                    fleet.segment_progress = 0.0
                    if next_system.owner_id != fleet.owner_id:
                        if next_system.ships > config.COMBAT_MIN_SHIPS:
                            fleet.siege_target_id = next_id
                        else:
                            next_system.owner_id = fleet.owner_id
                            next_system.ships = 0.0

            if fleet.ships <= config.COMBAT_MIN_SHIPS:
                if fleet in self.fleets:
                    self.fleets.remove(fleet)
                continue

            if len(self.combat_shots) > config.MAX_VISIBLE_SHOTS:
                self.combat_shots = self.combat_shots[-config.MAX_VISIBLE_SHOTS:]

        for fleet in arrived:
            target = self.systems[fleet.target_id]
            resolve_fleet_arrival(fleet, target)
            if fleet in self.fleets:
                self.fleets.remove(fleet)

    def _update_standoff_combat(self, dt: float) -> None:
        systems = self.systems
        for i in range(len(systems)):
            first = systems[i]
            if first.owner_id is None or first.ships <= config.COMBAT_MIN_SHIPS:
                continue
            for j in range(i + 1, len(systems)):
                second = systems[j]
                if second.owner_id is None or second.owner_id == first.owner_id or second.ships <= config.COMBAT_MIN_SHIPS:
                    continue
                if first.pos.distance_to(second.pos) > config.SYSTEM_ENGAGEMENT_RANGE:
                    continue
                shots = resolve_engagement(first, second, first.pos, second.pos, dt, config.SYSTEM_VS_SYSTEM_PER_SHIP, config.SYSTEM_VS_SYSTEM_PER_SHIP, self.empires[first.owner_id].color, self.empires[second.owner_id].color, self.rng)
                self.combat_shots.extend(shots)
                self.active_combat[first.id] = self.active_combat.get(first.id, 0.0) + config.SYSTEM_VS_SYSTEM_PER_SHIP
                self.active_combat[second.id] = self.active_combat.get(second.id, 0.0) + config.SYSTEM_VS_SYSTEM_PER_SHIP

        for fleet in list(self.fleets):
            if fleet.ships <= config.COMBAT_MIN_SHIPS:
                continue
            for system in systems:
                if system.owner_id is None or system.owner_id == fleet.owner_id or system.ships <= config.COMBAT_MIN_SHIPS:
                    continue
                if fleet.siege_target_id == system.id:
                    continue
                if fleet.position.distance_to(system.pos) > config.COMBAT_RANGE:
                    continue
                shots = resolve_engagement(fleet, system, fleet.position, system.pos, dt, config.ATTACKER_DAMAGE_PER_SHIP, config.DEFENDER_DAMAGE_PER_SHIP * config.DEFENDER_BONUS, self.empires[fleet.owner_id].color, self.empires[system.owner_id].color, self.rng)
                self.combat_shots.extend(shots)
                self.active_combat[system.id] = self.active_combat.get(system.id, 0.0) + config.DEFENDER_DAMAGE_PER_SHIP * config.DEFENDER_BONUS
            for other in list(self.fleets):
                if other.id <= fleet.id or other.owner_id == fleet.owner_id or other.ships <= config.COMBAT_MIN_SHIPS:
                    continue
                if fleet.position.distance_to(other.position) > config.COMBAT_RANGE:
                    continue
                shots = resolve_engagement(fleet, other, fleet.position, other.position, dt, config.FLEET_VS_FLEET_PER_SHIP, config.FLEET_VS_FLEET_PER_SHIP, self.empires[fleet.owner_id].color, self.empires[other.owner_id].color, self.rng)
                self.combat_shots.extend(shots)

        self.fleets = [f for f in self.fleets if f.ships > config.COMBAT_MIN_SHIPS]
        if len(self.combat_shots) > config.MAX_VISIBLE_SHOTS:
            self.combat_shots = self.combat_shots[-config.MAX_VISIBLE_SHOTS:]

    def _update_empire_status(self) -> None:
        for empire in self.empires:
            owns_system = any(system.owner_id == empire.id for system in self.systems)
            owns_fleet = any(fleet.owner_id == empire.id for fleet in self.fleets)
            empire.alive = owns_system or owns_fleet

    def system_at(self, position: tuple[int, int], radius: float = 18) -> Optional[StarSystem]:
        point = pygame.Vector2(position)
        candidates = [system for system in self.systems if system.pos.distance_to(point) <= radius]
        if not candidates:
            return None
        return min(candidates, key=lambda system: system.pos.distance_to(point))

    def get_system(self, system_id: int) -> StarSystem:
        return self.systems[system_id]

    def get_empire(self, empire_id: int) -> Empire:
        return self.empires[empire_id]

    def get_neighbors(self, system_id: int) -> list[StarSystem]:
        return [self.systems[neighbor_id] for neighbor_id in self.neighbors[system_id]]

    def is_neighbor(self, first_id: int, second_id: int) -> bool:
        return second_id in self.neighbors[first_id]

    def owned_systems(self, empire_id: int) -> list[StarSystem]:
        return [system for system in self.systems if system.owner_id == empire_id]

    def empire_system_count(self, empire_id: int) -> int:
        return sum(1 for system in self.systems if system.owner_id == empire_id)

    def empire_ship_count(self, empire_id: int) -> float:
        stationed = sum(system.ships for system in self.systems if system.owner_id == empire_id)
        travelling = sum(fleet.ships for fleet in self.fleets if fleet.owner_id == empire_id)
        return stationed + travelling

    def living_empires(self) -> list[Empire]:
        return [empire for empire in self.empires if empire.alive]

    def winner(self) -> Optional[Empire]:
        living = self.living_empires()
        if len(living) == 1:
            return living[0]
        return None

    def player_defeated(self) -> bool:
        return not self.empires[config.PLAYER_ID].alive

    def player_won(self) -> bool:
        winner = self.winner()
        return winner is not None and winner.id == config.PLAYER_ID