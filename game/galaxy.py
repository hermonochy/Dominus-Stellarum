from __future__ import annotations

import math
import random
from typing import Optional

import pygame

from . import config
from .combat import fire_at_target, gun_range, resolve_fleet_arrival
from .models import CombatShot, Empire, Explosion, Fleet, StarSystem

class Galaxy:
    def __init__(self, seed: Optional[int] = None):
        self.rng = random.Random(seed)
        self.systems: list[StarSystem] = []
        self.empires: list[Empire] = []
        self.fleets: list[Fleet] = []
        self.combat_shots: list[CombatShot] = []
        self.explosions: list[Explosion] = []
        self.edges: set[tuple[int, int]] = set()
        self.neighbors: dict[int, set[int]] = {}
        self.next_fleet_id = 0
        self.gathering_points: set[int] = set()
        self.new_ship_accum: dict[int, float] = {}
        self._accum_owner: dict[int, Optional[int]] = {}
        self.active_combat: dict[int, float] = {}
        self.autopilot = False
        self.nuclear_cooldown = 0.0
        self.nuked_grace: dict[int, float] = {}
        self.pending_messages: list[str] = []
        self.rebellion_timer = 0.0
        self.next_empire_id = 0
        self._casualty_accum: dict[int, float] = {}
        self._prev_owners: dict[int, Optional[int]] = {}

        self.grid_cell_size = config.COMBAT_RANGE * 2.0
        self.spatial_grid: dict[tuple[int, int], list[int]] = {}
        self.path_cache: dict[tuple[int, int], Optional[tuple[int, ...]]] = {}
        self._ship_count_cache: Optional[dict[int, float]] = None
        self._combat_tick_accum = 0.0
        self._gather_dispatch_timers: dict[int, float] = {}

        self.generate()

    def generate(self) -> None:
        self.systems.clear()
        self.empires.clear()
        self.fleets.clear()
        self.combat_shots.clear()
        self.explosions.clear()
        self.edges.clear()
        self.neighbors.clear()
        self.next_fleet_id = 0
        self.gathering_points.clear()
        self.new_ship_accum.clear()
        self._accum_owner.clear()
        self.active_combat.clear()
        self.autopilot = False
        self.nuclear_cooldown = 0.0
        self.nuked_grace.clear()
        self.pending_messages.clear()
        self.rebellion_timer = 0.0
        self.next_empire_id = 0
        self._casualty_accum.clear()
        self.spatial_grid.clear()
        self.path_cache.clear()
        self._ship_count_cache = None
        self._combat_tick_accum = 0.0
        self._gather_dispatch_timers.clear()
        self._create_systems()
        self._create_empires()
        self._place_empires()
        self._build_spatial_grid()
        self._prev_owners = {system.id: system.owner_id for system in self.systems}

    def update(self, dt: float) -> None:
        self._ship_count_cache = None
        if self.nuclear_cooldown > 0.0:
            self.nuclear_cooldown = max(0.0, self.nuclear_cooldown - dt)
        for sid in list(self.nuked_grace):
            self.nuked_grace[sid] -= dt
            if self.nuked_grace[sid] <= 0.0:
                del self.nuked_grace[sid]
        for explosion in self.explosions:
            explosion.age += dt
        self.explosions = [e for e in self.explosions if e.age < e.max_age]
        for shot in self.combat_shots:
            shot.lifetime -= dt
        self.combat_shots = [shot for shot in self.combat_shots if shot.lifetime > 0.0]
        self._produce_ships(dt)
        forces_before = self._snapshot_forces()
        self._update_fleets(dt)
        self._combat_tick_accum += dt
        combat_interval = 1.0 / config.COMBAT_TICKS_PER_SECOND
        if self._combat_tick_accum >= combat_interval:
            combat_dt = self._combat_tick_accum
            self._combat_tick_accum = 0.0
            self._update_standoff_combat(combat_dt)
        self._resolve_casualties(forces_before)
        self._resolve_captures()
        self._update_happiness(dt)
        self._update_rebellions(dt)
        self._update_empire_status()

    def _create_systems(self) -> None:
        center = pygame.Vector2(config.GALAXY_CENTER_X, config.GALAXY_CENTER_Y)
        num_arms = config.GALAXY_ARM_COUNT
        target_count = config.STAR_COUNT

        used_names: set[str] = set()
        positions: list[pygame.Vector2] = []
        system_data: list[tuple[str, float]] = []
        arm_tags: list[Optional[int]] = []

        prefixes = ["Al", "An", "Ar", "Aus", "Bel", "Bor", "Ca", "Cal", "Cor", "Cry", "Del", "Dor", "Dra", "Er", "Ere", "Fal", "Fer", "Gal", "Gar", "Hal", "Hel", "Hor", "Io", "Ir", "Jan", "Kel", "Kor", "Lan", "Lor", "Lu", "Mar", "Mor", "Nab", "Nor", "Ny", "Ob", "Or", "Pal", "Pra", "Qua", "Ral", "Ren", "Rho", "Sol", "Tal", "Tar", "Tha", "Tor", "Ur", "Val", "Vel", "Vor", "Wex", "Xan", "Yar", "Zen", "Zeph"]
        suffixes = ["a", "ac", "ae", "al", "an", "ar", "ath", "ea", "ek", "en", "er", "era", "es", "ia", "ion", "ir", "is", "ix", "o", "on", "or", "os", "ox", "um", "ur", "us", "yn", "yr", "zar"]
        modifiers = ["", " Prime", " Minor", " Secundus", " Tertius", " II", " III", " IV", " IX"]

        cell_size = config.MIN_STAR_DISTANCE
        spawn_grid: dict[tuple[int, int], list[pygame.Vector2]] = {}

        def record_position(pos: pygame.Vector2) -> None:
            key = (int(pos.x // cell_size), int(pos.y // cell_size))
            bucket = spawn_grid.get(key)
            if bucket is None:
                spawn_grid[key] = [pos]
            else:
                bucket.append(pos)

        def too_close(pos: pygame.Vector2, min_dist: float) -> bool:
            col = int(pos.x // cell_size)
            row = int(pos.y // cell_size)
            for dc in (-1, 0, 1):
                for dr in (-1, 0, 1):
                    for other in spawn_grid.get((col + dc, row + dr), ()):
                        if pos.distance_to(other) < min_dist:
                            return True
            return False

        def make_name() -> str:
            base_capacity = len(prefixes) * len(suffixes)
            for _ in range(base_capacity):
                name = self.rng.choice(prefixes) + self.rng.choice(suffixes)
                if name not in used_names:
                    used_names.add(name)
                    return name
            for _ in range(base_capacity * len(modifiers) * 2):
                name = self.rng.choice(prefixes) + self.rng.choice(suffixes) + self.rng.choice(modifiers[1:])
                if name not in used_names:
                    used_names.add(name)
                    return name
            name = f"Sys{len(used_names)}"
            used_names.add(name)
            return name

        def add_star(pos: pygame.Vector2, production: float, arm_idx: Optional[int]) -> None:
            positions.append(pos)
            system_data.append((make_name(), production))
            arm_tags.append(arm_idx)
            record_position(pos)

        def arm_spawn(base_angle: float) -> tuple[pygame.Vector2, float]:
            arm_start_radius = config.GALAXY_CORE_RADIUS + 25.0
            t = self.rng.random()
            r = arm_start_radius * (config.ARM_MAX_RADIUS / arm_start_radius) ** t
            theta = (
                base_angle
                + t * math.pi * config.GALAXY_ARM_PITCH
                + self.rng.gauss(0.0, config.GALAXY_ARM_WIND * 0.35)
            )
            r += self.rng.gauss(0.0, config.MIN_STAR_DISTANCE * 0.25)
            r = max(config.GALAXY_CORE_RADIUS + 10.0, r)
            pos = center + pygame.Vector2(math.cos(theta) * r, math.sin(theta) * r)
            production_multiplier = 1.0 - (r / config.ARM_MAX_RADIUS) * 0.35
            production = self.rng.uniform(
                config.PRODUCTION_MIN * production_multiplier,
                config.PRODUCTION_MAX * production_multiplier,
            )
            return pos, production

        def branch_spawn() -> tuple[pygame.Vector2, float, int]:
            parent_index = self.rng.randrange(core_star_end, len(positions))
            parent_rel = positions[parent_index] - center
            parent_theta = math.atan2(parent_rel.y, parent_rel.x)
            branch_angle = parent_theta + self.rng.choice([-1, 1]) * self.rng.uniform(0.5, 1.0)
            branch_radius = parent_rel.length() + self.rng.uniform(35, 55)
            pos = center + pygame.Vector2(
                math.cos(branch_angle) * branch_radius,
                math.sin(branch_angle) * branch_radius,
            )
            production = self.rng.uniform(config.PRODUCTION_MIN, config.PRODUCTION_MAX)
            arm_idx = arm_tags[parent_index]
            return pos, production, arm_idx if arm_idx is not None else 0

        core_target = max(2, int(target_count * config.GALAXY_CORE_RATIO))
        attempts = core_target * 40
        while len(positions) < core_target and attempts > 0:
            attempts -= 1
            r = config.GALAXY_CORE_RADIUS * math.sqrt(self.rng.random())
            theta = self.rng.random() * math.tau
            pos = center + pygame.Vector2(math.cos(theta) * r, math.sin(theta) * r)
            if too_close(pos, config.MIN_STAR_DISTANCE * 0.55):
                continue
            production = self.rng.uniform(config.PRODUCTION_MIN * 1.1, config.PRODUCTION_MAX * 1.1)
            add_star(pos, production, None)

        core_star_end = len(positions)

        base_angles = [
            (math.tau / num_arms) * arm_idx + self.rng.uniform(-0.1, 0.1)
            for arm_idx in range(num_arms)
        ]

        arm_budget = max(0, target_count - len(positions))
        base_quota = arm_budget // num_arms
        remainder = arm_budget - base_quota * num_arms

        for arm_idx in range(num_arms):
            quota = base_quota + (1 if arm_idx < remainder else 0)
            attempts = quota * 5 + 50
            while quota > 0 and attempts > 0:
                attempts -= 1
                pos, production = arm_spawn(base_angles[arm_idx])
                if too_close(pos, config.MIN_STAR_DISTANCE * 0.75):
                    continue
                add_star(pos, production, arm_idx)
                quota -= 1

        deficit = target_count - len(positions)
        attempts = deficit * 30
        relax = 0.75
        miss_streak = 0

        while len(positions) < target_count and attempts > 0:
            attempts -= 1
            if (
                len(positions) > core_star_end
                and self.rng.random() < config.GALAXY_BRANCH_RATIO
            ):
                pos, production, spawn_arm_idx = branch_spawn()
            else:
                spawn_arm_idx = self.rng.randrange(num_arms)
                pos, production = arm_spawn(base_angles[spawn_arm_idx])

            if too_close(pos, config.MIN_STAR_DISTANCE * relax):
                miss_streak += 1
                if miss_streak % 200 == 0:
                    relax = max(0.15, relax - 0.05)
                continue

            miss_streak = 0
            add_star(pos, production, spawn_arm_idx)

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

    @staticmethod
    def _unpack_empire(entry: list) -> tuple[str, tuple[int, int, int], int, float]:
        missiles = entry[2] if len(entry) > 2 else config.NUCLEAR_MISSILES_PER_EMPIRE
        happiness = entry[3] if len(entry) > 3 else config.DEFAULT_HAPPINESS
        return entry[0], entry[1], missiles, float(happiness)

    def _create_empires(self) -> None:
        chosen = config.PLAYER_EMPIRE_INDEX % len(config.EMPIRES)
        player_slot = min(chosen, config.EMPIRE_COUNT - 1)
        for empire_id in range(config.EMPIRE_COUNT):
            if empire_id == player_slot:
                name, color, missiles, happiness = self._unpack_empire(config.EMPIRES[chosen])
            else:
                name, color, missiles, happiness = self._unpack_empire(config.EMPIRES[empire_id])
            self.empires.append(
                Empire(
                    id=empire_id,
                    name=name,
                    color=color,
                    is_player=(empire_id == player_slot),
                    missiles_remaining=missiles,
                    happiness=happiness,
                    unrest_tolerance=self._unrest_tolerance(happiness),
                )
            )
        self.next_empire_id = len(self.empires)
        config.PLAYER_ID = player_slot

    @staticmethod
    def _unrest_tolerance(starting_happiness: float) -> float:
        return max(
            config.UNREST_TOLERANCE_FLOOR,
            starting_happiness / config.DEFAULT_HAPPINESS,
        )

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
            if self._accum_owner.get(system.id) != system.owner_id:
                self._accum_owner[system.id] = system.owner_id
                self.new_ship_accum[system.id] = 0.0
            owned_count = owned_counts.get(system.owner_id, 1)
            efficiency = self._empire_production_efficiency(owned_count, total_systems)

            active_penalty = 1.0
            if system.id in self.active_combat:
                active_penalty = max(0.3, 1.0 - self.active_combat[system.id] * 0.1)

            gain = system.production * dt * efficiency * active_penalty
            system.ships += gain

            self.new_ship_accum[system.id] = self.new_ship_accum.get(system.id, 0.0) + gain
            self.active_combat[system.id] = max(0.0, self.active_combat.get(system.id, 0.0) - dt * 2.0)

            if system.owner_id == config.PLAYER_ID and self.gathering_points and system.id not in self.gathering_points:
                timer = self._gather_dispatch_timers.get(system.id, 0.0) - dt
                if timer <= 0.0:
                    self._gather_dispatch_timers[system.id] = config.GATHERING_DISPATCH_INTERVAL
                    if self.new_ship_accum.get(system.id, 0.0) >= config.SHIP_DISPATCH_THRESHOLD:
                        self._dispatch_accumulated(system)
                else:
                    self._gather_dispatch_timers[system.id] = timer

    def _dispatch_accumulated(self, system: StarSystem) -> None:
        accumulated = self.new_ship_accum[system.id]
        amount = min(int(accumulated), int(system.ships))
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

    def missile_inbound(self, system_id: int) -> bool:
        return any(f.is_missile and f.target_id == system_id for f in self.fleets)

    def launch_player_nuclear(self, target_id: int) -> tuple[bool, str]:
        empire = self.empires[config.PLAYER_ID]
        if empire.missiles_remaining <= 0:
            return False, "You have no missiles remaining."
        if self.nuclear_cooldown > 0.0:
            return False, f"Nuclear launch cooldown: {int(self.nuclear_cooldown)}s remaining."
        target = self.systems[target_id]
        if target.owner_id == config.PLAYER_ID:
            return False, "You cannot nuke your own system."
        if target.id in self.nuked_grace:
            return False, f"{target.name} was recently struck — launch refused."
        if self.missile_inbound(target_id):
            return False, "A missile is already inbound to that system."
        origin = min(
            (system for system in self.systems
             if system.owner_id == config.PLAYER_ID),
            key=lambda system: system.pos.distance_to(target.pos),
            default=None,
        )
        if origin is None:
            return False, "You no longer control any launch site."
        route = self.shortest_path(origin.id, target_id)
        if route is None or len(route) < 2:
            return False, "No route exists from your territory to that system."
        empire.missiles_remaining -= 1
        empire.happiness = max(0.0, empire.happiness - config.NUKE_LAUNCHER_HAPPINESS_COST)
        self.nuclear_cooldown = config.NUCLEAR_GLOBAL_COOLDOWN
        self.fleets.append(
            Fleet(
                id=self.next_fleet_id,
                owner_id=config.PLAYER_ID,
                source_id=origin.id,
                target_id=target_id,
                ships=1.0,
                route=route,
                route_index=1,
                segment_progress=0.0,
                is_missile=True,
            )
        )
        self.next_fleet_id += 1
        return True, f"Nuclear missile launched at {target.name}."

    def _launch_nuclear(self, source_id: int, target_id: int, ignore_cooldown: bool = False) -> bool:
        source = self.systems[source_id]
        if source.owner_id is None:
            return False
        empire = self.empires[source.owner_id]
        if empire.missiles_remaining <= 0:
            return False
        if not ignore_cooldown and self.nuclear_cooldown > 0.0:
            return False
        if self.missile_inbound(target_id):
            return False
        route = self.shortest_path(source_id, target_id)
        if route is None or len(route) < 2:
            return False
        target = self.systems[target_id]
        if target.owner_id == config.PLAYER_ID:
            self.pending_messages.append(f"Nuclear missile inbound to {target.name}!")
        empire.missiles_remaining -= 1
        empire.happiness = max(0.0, empire.happiness - config.NUKE_LAUNCHER_HAPPINESS_COST)
        self.nuclear_cooldown = config.NUCLEAR_GLOBAL_COOLDOWN
        self.fleets.append(
            Fleet(
                id=self.next_fleet_id,
                owner_id=source.owner_id,
                source_id=source_id,
                target_id=target_id,
                ships=1.0,
                route=route,
                route_index=1,
                segment_progress=0.0,
                is_missile=True,
            )
        )
        self.next_fleet_id += 1
        return True

    def _apply_nuclear_strike(self, node: StarSystem) -> None:
        if node.owner_id is None:
            return
        if node.ships > 0.0:
            loss = node.ships
            node.ships = 0.0
            self._record_casualties(node.owner_id, loss)
            if node.owner_id == config.PLAYER_ID and loss >= 1.0:
                self.pending_messages.append(f"All ships lost at {node.name}!")
        production_damage = config.NUCLEAR_PRODUCTION_DAMAGE
        if production_damage > 0.0:
            node.production *= (1.0 - production_damage)

    def _detonate(self, system: StarSystem) -> None:
        affected = [system]
        for other in self.systems:
            if other.id == system.id:
                continue
            distance = other.pos.distance_to(system.pos)
            if distance < config.NUCLEAR_EFFECT_RADIUS:
                affected.append(other)
        for node in affected:
            self._apply_nuclear_strike(node)
        if config.NUCLEAR_KILLS_FLEETS:
            destroyed_ids: set[int] = set()
            for fleet in self.fleets:
                if fleet.is_missile:
                    continue
                if fleet.position.distance_to(system.pos) < config.NUCLEAR_EFFECT_RADIUS:
                    self._record_casualties(fleet.owner_id, fleet.ships)
                    if fleet.owner_id == config.PLAYER_ID and fleet.ships >= 1.0:
                        self.pending_messages.append("A fleet of yours was vaporised in the blast!")
                    destroyed_ids.add(fleet.id)
            if destroyed_ids:
                self.fleets = [f for f in self.fleets if f.id not in destroyed_ids]
        self.nuked_grace[system.id] = config.NUCLEAR_NUKED_GRACE
        self.explosions.append(
            Explosion(
                pos=system.pos.copy(),
                age=0.0,
                max_age=config.EXPLOSION_DURATION,
                peak_radius=config.NUCLEAR_EFFECT_RADIUS,
            )
        )

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

    def _record_casualties(self, empire_id: int, ships: float) -> None:
        if empire_id is None or ships <= 0.0:
            return
        self._casualty_accum[empire_id] = self._casualty_accum.get(empire_id, 0.0) + ships

    def _snapshot_forces(self) -> tuple[dict[int, float], dict[int, float]]:
        system_counts: dict[int, float] = {}
        for system in self.systems:
            if system.owner_id is not None:
                system_counts[system.owner_id] = system_counts.get(system.owner_id, 0.0) + system.ships
        fleet_counts: dict[int, float] = {}
        for fleet in self.fleets:
            fleet_counts[fleet.owner_id] = fleet_counts.get(fleet.owner_id, 0.0) + fleet.ships
        return system_counts, fleet_counts

    def _resolve_casualties(self, before: tuple[dict[int, float], dict[int, float]]) -> None:
        system_before, fleet_before = before
        system_after, fleet_after = self._snapshot_forces()
        for empire in self.empires:
            prior = system_before.get(empire.id, 0.0) + fleet_before.get(empire.id, 0.0)
            after = system_after.get(empire.id, 0.0) + fleet_after.get(empire.id, 0.0)
            lost = prior - after
            if lost > 0.0:
                self._record_casualties(empire.id, lost)

    def _resolve_captures(self) -> None:
        for system in self.systems:
            previous = self._prev_owners.get(system.id, system.owner_id)
            if system.owner_id is None or system.owner_id == previous:
                continue
            empire = self.empires[system.owner_id]
            empire.happiness = min(config.HAPPINESS_MAX, empire.happiness + config.SYSTEM_CAPTURE_HAPPINESS_GAIN)
        self._prev_owners = {system.id: system.owner_id for system in self.systems}

    def _update_fleets(self, dt: float) -> None:
        arrived: list[Fleet] = []
        detonations: list[Fleet] = []
        surviving_fleets: list[Fleet] = []
        for fleet in self.fleets:
            speed = config.FLEET_SPEED
            if fleet.is_missile:
                speed *= config.NUCLEAR_MISSILE_SPEED_MULT
            current_id = fleet.route[fleet.route_index - 1]
            next_id = fleet.route[fleet.route_index] if fleet.route_index < len(fleet.route) else fleet.route[-1]
            current_system = self.systems[current_id]
            next_system = self.systems[next_id]
            segment_distance = current_system.pos.distance_to(next_system.pos)
            fleet.segment_progress += (speed * dt) / max(1.0, segment_distance)
            if fleet.segment_progress <= 1.0:
                fleet.position = current_system.pos.lerp(next_system.pos, min(1.0, fleet.segment_progress))
            else:
                fleet.position = next_system.pos
                if fleet.route_index >= len(fleet.route) - 1:
                    fleet.progress = 1.0
                    if fleet.is_missile:
                        detonations.append(fleet)
                    else:
                        arrived.append(fleet)
                    continue
                else:
                    fleet.route_index += 1
                    fleet.segment_progress = 0.0
                    if not fleet.is_missile and next_system.owner_id != fleet.owner_id:
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
        for fleet in detonations:
            self._detonate(self.systems[fleet.target_id])
        self._merge_fleets()

    def _merge_fleets(self) -> None:
        if len(self.fleets) < config.FLEET_MERGE_THRESHOLD:
            return
        segments: dict[tuple[int, int, int], Fleet] = {}
        merged: list[Fleet] = []
        for fleet in self.fleets:
            if fleet.is_missile or fleet.route_index >= len(fleet.route):
                merged.append(fleet)
                continue
            key = (fleet.owner_id, fleet.target_id, fleet.route[fleet.route_index - 1], fleet.route[fleet.route_index])
            lead = segments.get(key)
            if lead is None:
                segments[key] = fleet
                merged.append(fleet)
                continue
            total = lead.ships + fleet.ships
            if total > 0.0:
                lead.segment_progress = (
                    lead.segment_progress * lead.ships + fleet.segment_progress * fleet.ships
                ) / total
            lead.ships = total
        self.fleets = merged

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
        shot_allowance = config.MAX_VISIBLE_SHOTS - len(self.combat_shots)
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
                shots = fire_at_target(system, other, system.pos, other.pos, dt, config.SYSTEM_VS_SYSTEM_PER_SHIP, shooter_color, self.rng, True, spawn_visuals=shot_allowance > 0)
                if shots:
                    self.combat_shots.extend(shots)
                    shot_allowance -= len(shots)
                self.active_combat[other.id] = self.active_combat.get(other.id, 0.0) + config.SYSTEM_VS_SYSTEM_PER_SHIP
        fleet_grid = self._build_fleet_grid()
        seen_pairs: set[tuple[int, int]] = set()
        for fleet in self.fleets:
            if fleet.is_missile:
                continue
            if fleet.owner_id is None or fleet.ships <= config.COMBAT_MIN_SHIPS:
                continue
            shooter_range = gun_range(fleet)
            shooter_color = self.empires[fleet.owner_id].color
            for system in self._nearby_systems(fleet.position, shooter_range):
                if system.owner_id is None or system.owner_id == fleet.owner_id:
                    continue
                if system.ships <= config.COMBAT_MIN_SHIPS:
                    continue
                shots = fire_at_target(fleet, system, fleet.position, system.pos, dt, config.FLEET_VS_FLEET_PER_SHIP, shooter_color, self.rng, spawn_visuals=shot_allowance > 0)
                if shots:
                    self.combat_shots.extend(shots)
                    shot_allowance -= len(shots)
                self.active_combat[system.id] = self.active_combat.get(system.id, 0.0) + config.FLEET_VS_FLEET_PER_SHIP * config.DEFENDER_BONUS
            for other in self._nearby_fleets(fleet.position, shooter_range, fleet_grid):
                if other is fleet or other.owner_id == fleet.owner_id:
                    continue
                if other.is_missile:
                    continue
                if other.ships <= config.COMBAT_MIN_SHIPS:
                    continue
                pair = (fleet.id, other.id) if fleet.id < other.id else (other.id, fleet.id)
                if pair in seen_pairs:
                    continue
                seen_pairs.add(pair)
                shots = fire_at_target(fleet, other, fleet.position, other.position, dt, config.FLEET_VS_FLEET_PER_SHIP, shooter_color, self.rng, spawn_visuals=shot_allowance > 0)
                shots += fire_at_target(other, fleet, other.position, fleet.position, dt, config.FLEET_VS_FLEET_PER_SHIP, self.empires[other.owner_id].color, self.rng, spawn_visuals=shot_allowance > 0)
                if shots:
                    self.combat_shots.extend(shots)
                    shot_allowance -= len(shots)
        self.fleets = [f for f in self.fleets if f.is_missile or f.ships > config.COMBAT_MIN_SHIPS]
        if len(self.combat_shots) > config.MAX_VISIBLE_SHOTS:
            self.combat_shots = self.combat_shots[-config.MAX_VISIBLE_SHOTS:]

    def _update_happiness(self, dt: float) -> None:
        decay = math.exp(-dt / config.CASUALTY_WINDOW)
        for empire in self.empires:
            if not empire.alive:
                continue
            self._casualty_accum[empire.id] = self._casualty_accum.get(empire.id, 0.0) * decay
        for empire in self.empires:
            if not empire.alive:
                continue
            fleet_size = self.empire_ship_count(empire.id)
            if fleet_size < 1.0:
                continue
            metric = self._casualty_accum.get(empire.id, 0.0) / fleet_size
            if metric < 0.01:
                empire.happiness += config.HAPPINESS_PEACETIME_RECOVERY * dt
            elif metric > 0.08:
                empire.happiness -= (
                    config.CASUALTY_UNREST_FACTOR
                    * metric
                    * dt
                    / max(config.UNREST_TOLERANCE_FLOOR, empire.unrest_tolerance)
                )
            empire.happiness = max(0.0, min(config.HAPPINESS_MAX, empire.happiness))

    def _update_rebellions(self, dt: float) -> None:
        self.rebellion_timer += dt
        if self.rebellion_timer < config.REBELLION_CHECK_INTERVAL:
            return
        self.rebellion_timer -= config.REBELLION_CHECK_INTERVAL
        for empire in list(self.empires):
            if not empire.alive:
                continue
            if empire.happiness >= config.HAPPINESS_REBELLION_THRESHOLD:
                continue
            self._check_empire_unrest(empire)

    def _check_empire_unrest(self, empire: Empire) -> None:
        severity = (config.HAPPINESS_REBELLION_THRESHOLD - empire.happiness) / config.HAPPINESS_REBELLION_THRESHOLD
        severity = max(0.0, min(1.0, severity))
        owned = [system for system in self.systems if system.owner_id == empire.id]
        if len(owned) <= 1:
            return
        candidates: list[StarSystem] = []
        for system in owned:
            ship_factor = config.REBELLION_SHIP_SCALE / (config.REBELLION_SHIP_SCALE + max(0.0, system.ships))
            chance = config.REBELLION_BASE_CHANCE * severity * severity * ship_factor
            if self.rng.random() < chance:
                candidates.append(system)
        if not candidates:
            return
        spark = self.rng.choice(candidates)
        rebel_empires = [e for e in self.empires if e.is_rebel and e.alive]
        can_rebel = len(rebel_empires) < config.MAX_REBEL_EMPIRES
        neighbours = [
            self.systems[nid]
            for nid in self.neighbors[spark.id]
            if self.systems[nid].owner_id is not None
            and self.systems[nid].owner_id != empire.id
        ]
        betray_chance = config.BETRAYAL_WEIGHT if neighbours else 0.0
        if not can_rebel:
            betray_chance = 1.0
        if neighbours and self.rng.random() < betray_chance:
            self._betray_to_neighbour(empire, spark, neighbours)
        else:
            self._spark_revolt(empire, spark, candidates)

    def _betray_to_neighbour(self, empire: Empire, system: StarSystem, neighbours: list[StarSystem]) -> None:
        def neighbour_weight(node: StarSystem) -> float:
            return node.ships + self.empires[node.owner_id].happiness
        best = max(neighbours, key=neighbour_weight)
        new_owner = best.owner_id
        system.owner_id = new_owner
        self.gathering_points.discard(system.id)
        if empire.is_player:
            self.pending_messages.append(f"{system.name} has defected to the {self.empires[new_owner].name}!")
        elif new_owner == config.PLAYER_ID:
            self.pending_messages.append(f"{system.name} has joined your empire, abandoning the {empire.name}.")

    def _color_distance(self, first: tuple[int, int, int], second: tuple[int, int, int]) -> float:
        mean_red = (first[0] + second[0]) / 2.0
        dr = first[0] - second[0]
        dg = first[1] - second[1]
        db = first[2] - second[2]
        return math.sqrt(
            (2.0 + mean_red / 256.0) * dr * dr
            + 4.0 * dg * dg
            + (2.0 + (255.0 - mean_red) / 256.0) * db * db
        )

    def _pick_rebel_color(self) -> tuple[int, int, int]:
        taken = [empire.color for empire in self.empires]
        taken.append(config.NEUTRAL_COLOR)

        def min_distance(color: tuple[int, int, int]) -> float:
            return min(self._color_distance(color, other) for other in taken)

        palette = list(config.REBEL_COLORS)
        self.rng.shuffle(palette)
        best_palette: tuple[float, tuple[int, int, int]] | None = None
        for color in palette:
            distance = min_distance(color)
            if distance >= config.REBEL_COLOR_MIN_DISTANCE:
                return color
            if best_palette is None or distance > best_palette[0]:
                best_palette = (distance, color)

        best_random: tuple[float, tuple[int, int, int]] | None = None
        for _ in range(64):
            color = (
                self.rng.randint(60, 255),
                self.rng.randint(60, 255),
                self.rng.randint(60, 255),
            )
            distance = min_distance(color)
            if distance >= config.REBEL_COLOR_MIN_DISTANCE:
                return color
            if best_random is None or distance > best_random[0]:
                best_random = (distance, color)

        if best_random is not None and best_random[0] > (best_palette[0] if best_palette else 0.0):
            return best_random[1]
        if best_palette is not None:
            return best_palette[1]
        return (128, 128, 128)

    def _spark_revolt(self, empire: Empire, spark: StarSystem, candidates: list[StarSystem]) -> None:
        defectors: dict[int, StarSystem] = {spark.id: spark}
        committed: set[int] = {spark.id}
        for system in candidates:
            if system.id == spark.id:
                continue
            if system.pos.distance_to(spark.pos) <= config.REVOLT_SECTOR_RADIUS:
                defectors[system.id] = system
                committed.add(system.id)

        frontier: set[int] = set(committed)
        while frontier:
            next_frontier: set[int] = set()
            for sid in frontier:
                for nid in self.neighbors[sid]:
                    if nid in committed:
                        continue
                    system = self.systems[nid]
                    if system.owner_id != empire.id:
                        continue
                    if system.pos.distance_to(spark.pos) > config.REVOLT_SECTOR_RADIUS:
                        continue
                    if system.ships > config.REVOLT_SPREAD_SHIP_LIMIT:
                        continue
                    if self.rng.random() >= config.REVOLT_SPREAD_CHANCE:
                        continue
                    committed.add(nid)
                    defectors[nid] = system
                    next_frontier.add(nid)
            frontier = next_frontier

        owned = [s for s in self.systems if s.owner_id == empire.id]
        if len(defectors) >= len(owned):
            keeper = max(owned, key=lambda s: s.ships)
            defectors.pop(keeper.id, None)
        defector_list = list(defectors.values())
        if not defector_list:
            return

        rebel_empires = [e for e in self.empires if e.is_rebel and e.alive]
        if len(rebel_empires) >= config.MAX_REBEL_EMPIRES:
            nearest_rebel = None
            min_distance = float('inf')
            for rebel in rebel_empires:
                rebel_systems = [s for s in self.systems if s.owner_id == rebel.id]
                if not rebel_systems:
                    continue
                closest_dist = min(spark.pos.distance_to(s.pos) for s in rebel_systems)
                if closest_dist < min_distance:
                    min_distance = closest_dist
                    nearest_rebel = rebel
            if nearest_rebel is not None:
                for system in defector_list:
                    system.owner_id = nearest_rebel.id
                    self.gathering_points.discard(system.id)
                if empire.is_player:
                    self.pending_messages.append(
                        f"{len(defector_list)} systems in your {spark.name} sector have defected to the {nearest_rebel.name}!"
                    )
                return

        suffix = self.rng.choice(config.REBEL_EMPIRE_SUFFIXES)
        color = self._pick_rebel_color()
        rebel = Empire(
            id=self.next_empire_id,
            name=f"{spark.name} {suffix}",
            color=color,
            is_player=False,
            alive=True,
            missiles_remaining=0,
            happiness=config.REBEL_HAPPINESS,
            is_rebel=True,
            unrest_tolerance=self._unrest_tolerance(config.REBEL_HAPPINESS),
        )
        self.next_empire_id += 1
        self.empires.append(rebel)

        for system in defector_list:
            system.owner_id = rebel.id
            self.gathering_points.discard(system.id)

        if empire.is_player:
            self.pending_messages.append(
                f"{len(defector_list)} systems in the {spark.name} sector have risen in revolt! The {rebel.name} declares independence."
            )

    def _update_empire_status(self) -> None:
        owners: set[int] = set()
        for system in self.systems:
            if system.owner_id is not None:
                owners.add(system.owner_id)
        for fleet in self.fleets:
            owners.add(fleet.owner_id)
        for empire in self.empires:
            empire.alive = empire.id in owners

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
        return (ships+1) * planets

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
        result: list[StarSystem] = []
        systems = self.systems
        grid = self.spatial_grid
        for col in range(col_min, col_max + 1):
            for row in range(row_min, row_max + 1):
                bucket = grid.get((col, row))
                if not bucket:
                    continue
                for sid in bucket:
                    system = systems[sid]
                    if system.pos.distance_to(pos) <= radius:
                        result.append(system)
        return result