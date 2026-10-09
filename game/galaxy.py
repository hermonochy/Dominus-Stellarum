from __future__ import annotations

import math
import random
from typing import Optional

import pygame

from . import config
from .combat import fire_at_target, gun_range, resolve_fleet_arrival
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

        self.grid_cell_size = config.COMBAT_RANGE * 2.0
        self.spatial_grid: dict[tuple[int, int], list[int]] = {}
        self.path_cache: dict[tuple[int, int], Optional[tuple[int, ...]]] = {}
        self._ship_count_cache: Optional[dict[int, float]] = None

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
        self.spatial_grid.clear()
        self.path_cache.clear()
        self._ship_count_cache = None
        self._create_systems()
        self._create_empires()
        self._place_empires()
        self._build_spatial_grid()

    def update(self, dt: float) -> None:
        self._ship_count_cache = None
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
            branches_to_add = min(int(config.STAR_COUNT * config.GALAXY_BRANCH_RATIO), config.STAR_COUNT - len(positions))
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
            self.empires.append(Empire(id=empire_id, name=config.EMPIRES[empire_id % len(config.EMPIRES)][0], color=config.EMPIRES[empire_id % len(config.EMPIRES)][1], is_player=(empire_id == config.PLAYER_ID)))

    def _spiral_deviation(self, system: StarSystem, arm_idx: int, center: pygame.Vector2) -> tuple[float, float]:
        rel = system.pos - center
        radius = max(rel.length(), config.GALAXY_CORE_RADIUS + 21.0)
        arm_start_radius = config.GALAXY_CORE_RADIUS + 20.0
        log_span = math.log(config.ARM_MAX_RADIUS / arm_start_radius)
        t = min(1.0, max(0.0, math.log(radius / arm_start_radius) / log_span))
        ideal_angle = (math.tau / config.GALAXY_ARM_COUNT) * arm_idx + t * math.pi * config.GALAXY_ARM_PITCH
        actual_angle = math.atan2(rel.y, rel.x)
        delta = (actual_angle - ideal_angle + math.pi) % math.tau - math.pi
        return abs(delta), radius

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

        empire_id = 0

        for arm_idx in range(num_arms):
            if empire_id >= num_empires:
                break
            candidates = [
                s for s in arm_systems[arm_idx]
                if s.pos.distance_to(center) > config.GALAXY_CORE_RADIUS
            ]
            if not candidates:
                continue
            best: tuple[tuple[int, float, float], StarSystem] | None = None
            for system in candidates:
                deviation, radius = self._spiral_deviation(system, arm_idx, center)
                key = (1 if deviation > 0.5 else 0, -radius, deviation)
                if best is None or key < best[0]:
                    best = (key, system)
            if best is not None:
                place(best[1], empire_id)
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
        # Ship production is a quadratic: AX^2 + BX + C
        efficiency = config.PRODUCTION_A*share**2 + config.PRODUCTION_B*share + config.PRODUCTION_C
        return efficiency

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

        cache_key = (source_id, target_id)
        if cache_key in self.path_cache:
            return self.path_cache[cache_key]

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
                    result = tuple(path)
                    self.path_cache[cache_key] = result
                    return result
                queue.append(neighbor)

        self.path_cache[cache_key] = None
        return None

    def _safe_route(self, source_id: int, target_id: int, empire_id: int) -> Optional[tuple[int, ...]]:
        if source_id == target_id:
            return (source_id,)
        if source_id not in self.neighbors or target_id not in self.neighbors:
            return None
        queue: list[int] = [source_id]
        previous: dict[int, Optional[int]] = {source_id: None}
        visited: set[int] = {source_id}
        while queue:
            current = queue.pop(0)
            for neighbor in self.neighbors[current]:
                if neighbor in visited:
                    continue
                if neighbor != target_id:
                    node = self.systems[neighbor]
                    if node.owner_id not in (None, empire_id):
                        continue
                visited.add(neighbor)
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
        visited: set[int] = {source_id}
        queue: list[int] = [source_id]
        while queue:
            current = queue.pop(0)
            for neighbor in self.neighbors[current]:
                if neighbor in visited:
                    continue
                visited.add(neighbor)
                reachable.add(neighbor)
                queue.append(neighbor)
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
        surviving_fleets: list[Fleet] = []

        for shot in self.combat_shots:
            shot.lifetime -= dt
        self.combat_shots = [shot for shot in self.combat_shots if shot.lifetime > 0.0]

        for fleet in self.fleets:
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
                    continue
                else:
                    fleet.route_index += 1
                    fleet.segment_progress = 0.0
                    if next_system.owner_id != fleet.owner_id:
                        if next_system.ships > config.COMBAT_MIN_SHIPS:
                            if fleet.ships > next_system.ships:
                                next_system.owner_id = fleet.owner_id
                                next_system.ships = 0.0
                            else:
                                next_system.ships = max(0.0, next_system.ships - fleet.ships)
                                fleet.ships = 0.0
                        else:
                            next_system.owner_id = fleet.owner_id
                            next_system.ships = 0.0

            if fleet.ships > config.COMBAT_MIN_SHIPS:
                surviving_fleets.append(fleet)

        self.fleets = surviving_fleets

        for fleet in arrived:
            target = self.systems[fleet.target_id]
            resolve_fleet_arrival(fleet, target)

        if len(self.combat_shots) > config.MAX_VISIBLE_SHOTS:
            self.combat_shots = self.combat_shots[-config.MAX_VISIBLE_SHOTS:]

    def _build_fleet_grid(self) -> dict[tuple[int, int], list[Fleet]]:
        cell_size = self.grid_cell_size
        fleet_grid: dict[tuple[int, int], list[Fleet]] = {}
        for fleet in self.fleets:
            key = (int(fleet.position.x // cell_size), int(fleet.position.y // cell_size))
            bucket = fleet_grid.get(key)
            if bucket is None:
                fleet_grid[key] = [fleet]
            else:
                bucket.append(fleet)
        return fleet_grid

    def _nearby_fleets(
        self,
        pos: pygame.Vector2,
        radius: float,
        fleet_grid: dict[tuple[int, int], list[Fleet]],
    ) -> list[Fleet]:
        cell_size = self.grid_cell_size
        col_min = int((pos.x - radius) // cell_size)
        col_max = int((pos.x + radius) // cell_size)
        row_min = int((pos.y - radius) // cell_size)
        row_max = int((pos.y + radius) // cell_size)

        result: list[Fleet] = []
        for col in range(col_min, col_max + 1):
            for row in range(row_min, row_max + 1):
                bucket = fleet_grid.get((col, row))
                if not bucket:
                    continue
                for fleet in bucket:
                    if fleet.position.distance_to(pos) <= radius:
                        result.append(fleet)
        return result

    def _update_standoff_combat(self, dt: float) -> None:
        for system in self.systems:
            if system.owner_id is None or system.ships <= config.COMBAT_MIN_SHIPS:
                continue
            shooter_range = gun_range(system)
            shooter_color = self.empires[system.owner_id].color
            for other in self._nearby_systems(system.pos, shooter_range):
                if other.id == system.id:
                    continue
                if other.owner_id is None or other.owner_id == system.owner_id:
                    continue
                if other.ships <= config.COMBAT_MIN_SHIPS:
                    continue
                shots = fire_at_target(system, other, system.pos, other.pos, dt, config.SYSTEM_VS_SYSTEM_PER_SHIP, shooter_color, self.rng, True)
                self.combat_shots.extend(shots)
                self.active_combat[other.id] = self.active_combat.get(other.id, 0.0) + config.SYSTEM_VS_SYSTEM_PER_SHIP

        fleet_grid = self._build_fleet_grid()
        seen_pairs: set[tuple[int, int]] = set()

        for fleet in self.fleets:
            if fleet.owner_id is None or fleet.ships <= config.COMBAT_MIN_SHIPS:
                continue
            shooter_range = gun_range(fleet)
            shooter_color = self.empires[fleet.owner_id].color
            for system in self._nearby_systems(fleet.position, shooter_range):
                if system.owner_id is None or system.owner_id == fleet.owner_id:
                    continue
                if system.ships <= config.COMBAT_MIN_SHIPS:
                    continue
                shots = fire_at_target(fleet, system, fleet.position, system.pos, dt, config.FLEET_VS_FLEET_PER_SHIP, shooter_color, self.rng)
                self.combat_shots.extend(shots)
                self.active_combat[system.id] = self.active_combat.get(system.id, 0.0) + config.FLEET_VS_FLEET_PER_SHIP * config.DEFENDER_BONUS
            for other in self._nearby_fleets(fleet.position, shooter_range, fleet_grid):
                if other is fleet or other.owner_id == fleet.owner_id:
                    continue
                if other.ships <= config.COMBAT_MIN_SHIPS:
                    continue
                pair = (fleet.id, other.id) if fleet.id < other.id else (other.id, fleet.id)
                if pair in seen_pairs:
                    continue
                seen_pairs.add(pair)
                shots = fire_at_target(fleet, other, fleet.position, other.position, dt, config.FLEET_VS_FLEET_PER_SHIP, shooter_color, self.rng)
                shots += fire_at_target(other, fleet, other.position, fleet.position, dt, config.FLEET_VS_FLEET_PER_SHIP, self.empires[other.owner_id].color, self.rng)
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
        if self._ship_count_cache is None:
            counts: dict[int, float] = {}
            for system in self.systems:
                if system.owner_id is not None:
                    counts[system.owner_id] = counts.get(system.owner_id, 0.0) + system.ships
            for fleet in self.fleets:
                counts[fleet.owner_id] = counts.get(fleet.owner_id, 0.0) + fleet.ships
            self._ship_count_cache = counts
        return self._ship_count_cache.get(empire_id, 0.0)

    def empire_strength(self, empire_id: int) -> float:
        planets = self.empire_system_count(empire_id)
        if planets <= 0:
            return 0.0
        ships = self.empire_ship_count(empire_id)
        return ships * planets

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

    def _build_spatial_grid(self) -> None:
        cell_size = self.grid_cell_size
        for system in self.systems:
            key = (int(system.pos.x // cell_size), int(system.pos.y // cell_size))
            if key not in self.spatial_grid:
                self.spatial_grid[key] = []
            self.spatial_grid[key].append(system.id)

    def _nearby_systems(self, pos: pygame.Vector2, radius: float) -> list[StarSystem]:
        cell_size = self.grid_cell_size
        col_min = int((pos.x - radius) // cell_size)
        col_max = int((pos.x + radius) // cell_size)
        row_min = int((pos.y - radius) // cell_size)
        row_max = int((pos.y + radius) // cell_size)

        nearby_ids: set[int] = set()
        for col in range(col_min, col_max + 1):
            for row in range(row_min, row_max + 1):
                bucket = self.spatial_grid.get((col, row))
                if bucket:
                    nearby_ids.update(bucket)

        result: list[StarSystem] = []
        for sid in nearby_ids:
            system = self.systems[sid]
            if system.pos.distance_to(pos) <= radius:
                result.append(system)
        return result