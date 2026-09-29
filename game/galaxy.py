from __future__ import annotations

import math
import random
from typing import Optional

import pygame

from . import config
from .combat import (
    resolve_fleet_arrival,
    resolve_fleet_combat,
)
from .models import (
    CombatShot,
    Empire,
    Fleet,
    StarSystem,
)

class Galaxy:
    def __init__(
        self,
        seed: Optional[int] = None,
    ):
        self.rng = random.Random(seed)

        self.systems: list[StarSystem] = []
        self.empires: list[Empire] = []
        self.fleets: list[Fleet] = []
        self.combat_shots: list[CombatShot] = []

        self.edges: set[tuple[int, int]] = set()
        self.neighbors: dict[int, set[int]] = {}

        self.next_fleet_id = 0

        self.generate()

    def generate(self) -> None:
        self.systems.clear()
        self.empires.clear()
        self.fleets.clear()
        self.combat_shots.clear()
        self.edges.clear()
        self.neighbors.clear()

        self.next_fleet_id = 0

        self._create_systems()
        self._create_empires()
        self._place_empires()

    def update(self, dt: float) -> None:
        self._produce_ships(dt)
        self._update_fleets(dt)
        self._update_empire_status()

    def _create_systems(self) -> None:
        center = pygame.Vector2(
            config.GALAXY_CENTER_X,
            config.GALAXY_CENTER_Y,
        )

        prefixes = [
            "Al", "Ar", "Bel", "Ca", "Cor", "Del", "Er", "Fal",
            "Gal", "Hel", "Io", "Jan", "Kel", "Lor", "Mor", "Nor",
            "Or", "Pra", "Qua", "Ren", "Sol", "Tal", "Ur", "Vel",
            "Wex", "Xan", "Yar", "Zen",
        ]

        suffixes = [
            "a", "ar", "ea", "en", "eron", "ia", "ion", "is",
            "on", "or", "os", "um", "us",
        ]

        used_names: set[str] = set()

        positions: list[pygame.Vector2] = []
        system_data: list[tuple[str, float]] = []
        lane_set: set[tuple[int, int]] = set()

        def too_close(pos: pygame.Vector2) -> bool:
            return any(
                pos.distance_to(other) < config.MIN_STAR_DISTANCE
                for other in positions
            )

        def lane_clear(
            first_id: int,
            second_id: int,
        ) -> bool:
            first = positions[first_id]
            second = positions[second_id]

            distance = first.distance_to(second)
            if distance < config.EDGE_MIN_LENGTH:
                return False
            if distance > config.EDGE_MAX_LENGTH:
                return False

            for edge_first, edge_second in lane_set:
                if first_id in (edge_first, edge_second):
                    continue
                if second_id in (edge_first, edge_second):
                    continue

                if self._segments_intersect(
                    first,
                    second,
                    positions[edge_first],
                    positions[edge_second],
                ):
                    return False

            return True

        def try_place(
            pos: pygame.Vector2,
            parent_id: int,
            production_range: tuple[float, float],
        ) -> Optional[int]:
            if too_close(pos):
                return None

            new_id = len(positions)
            positions.append(pos)

            if parent_id is None or not lane_clear(parent_id, new_id):
                positions.pop()
                return None

            name = self._make_name(prefixes, suffixes, used_names)
            production = self.rng.uniform(*production_range)
            system_data.append((name, production))
            lane_set.add(tuple(sorted((parent_id, new_id))))
            return new_id

        core_count = self.rng.randint(
            config.CORE_SYSTEMS_MIN,
            config.CORE_SYSTEMS_MAX,
        )

        core_radius = max(45.0, math.sqrt(core_count) * 14.0)

        core_ids: list[int] = []

        for i in range(core_count):
            ring_radius = core_radius * math.sqrt((i + 0.5) / core_count)
            ring_angle = i * 2.39996 + self.rng.uniform(-0.08, 0.08)

            pos = center + pygame.Vector2(
                math.cos(ring_angle) * ring_radius,
                math.sin(ring_angle) * ring_radius,
            )

            pos += pygame.Vector2(
                self.rng.uniform(-3, 3),
                self.rng.uniform(-3, 3),
            )

            if too_close(pos):
                continue

            name = self._make_name(prefixes, suffixes, used_names)
            production = self.rng.uniform(
                config.PRODUCTION_MIN * 1.2,
                config.PRODUCTION_MAX * 1.2,
            )

            core_ids.append(len(positions))
            positions.append(pos)
            system_data.append((name, production))

        core_pairs = sorted(
            (
                (positions[a].distance_to(positions[b]), a, b)
                for a in core_ids
                for b in core_ids
                if a < b
            )
        )

        core_adjacency: dict[int, set[int]] = {cid: set() for cid in core_ids}

        for _, a, b in core_pairs:
            if self._core_connected(core_adjacency, a, b):
                continue

            if lane_clear(a, b):
                lane_set.add((min(a, b), max(a, b)))
                core_adjacency[a].add(b)
                core_adjacency[b].add(a)

        for _, a, b in core_pairs:
            if len(core_adjacency[a]) >= 3:
                continue
            if len(core_adjacency[b]) >= 3:
                continue
            if b in core_adjacency[a]:
                continue
            if self.rng.random() > 0.35:
                continue

            if lane_clear(a, b):
                lane_set.add((min(a, b), max(a, b)))
                core_adjacency[a].add(b)
                core_adjacency[b].add(a)

        num_arms = self.rng.randint(config.GALAXY_ARM_MIN, config.GALAXY_ARM_MAX)

        arm_base_angles = [
            (math.tau / num_arms) * i + self.rng.uniform(-0.12, 0.12)
            for i in range(num_arms)
        ]

        arms: list[dict] = []

        for base_angle in arm_base_angles:
            root_id = min(
                core_ids,
                key=lambda cid: abs(
                    (
                        math.atan2(
                            positions[cid].y - center.y,
                            positions[cid].x - center.x,
                        )
                        - base_angle
                        + math.pi
                    )
                    % math.tau
                    - math.pi
                ),
            )

            cursor = positions[root_id].copy()
            relative = cursor - center

            arms.append(
                {
                    "cursor": cursor,
                    "theta": math.atan2(relative.y, relative.x),
                    "radius": max(20.0, relative.length()),
                    "prev_id": root_id,
                    "spin_dir": self.rng.choice([1.0, -1.0]),
                    "done": False,
                }
            )

        guard = 0
        max_guard = config.STAR_COUNT * 40

        while len(positions) < config.STAR_COUNT and guard < max_guard:
            guard += 1

            active_arms = [arm for arm in arms if not arm["done"]]

            if not active_arms:
                break

            progressed_any = False

            for arm in active_arms:
                if len(positions) >= config.STAR_COUNT:
                    break

                arm["done"] = True

                for _ in range(10):
                    if len(positions) >= config.STAR_COUNT:
                        break

                    angular_step = self.rng.uniform(
                        config.ARM_SPIN_MIN,
                        config.ARM_SPIN_MAX,
                    )

                    new_theta = arm["theta"] + arm["spin_dir"] * angular_step
                    new_radius = arm["radius"] + self.rng.uniform(
                        config.ARM_OUTWARD_STEP_MIN,
                        config.ARM_OUTWARD_STEP_MAX,
                    )

                    wobble_radial = self.rng.uniform(
                        -config.ARM_WOBBLE_RADIAL,
                        config.ARM_WOBBLE_RADIAL,
                    )
                    wobble_tangential = self.rng.uniform(
                        -config.ARM_WOBBLE_TANGENTIAL,
                        config.ARM_WOBBLE_TANGENTIAL,
                    )

                    final_radius = new_radius + wobble_radial
                    final_theta = new_theta + wobble_tangential / max(1.0, new_radius)

                    candidate = center + pygame.Vector2(
                        math.cos(final_theta) * final_radius,
                        math.sin(final_theta) * final_radius,
                    )

                    if final_radius > config.ARM_MAX_RADIUS:
                        break

                    placed_id = try_place(
                        candidate,
                        arm["prev_id"],
                        (config.PRODUCTION_MIN, config.PRODUCTION_MAX),
                    )

                    if placed_id is not None:
                        arm["cursor"] = candidate
                        arm["theta"] = final_theta
                        arm["radius"] = final_radius
                        arm["prev_id"] = placed_id
                        arm["done"] = False
                        progressed_any = True

                        if self.rng.random() < config.BRANCH_CHANCE:
                            branch_spin = arm["spin_dir"] * self.rng.choice([-1.0, 1.0])
                            branch_prev = placed_id
                            
                            for bi in range(3):
                                if len(positions) >= config.STAR_COUNT:
                                    break

                                b_theta = final_theta + branch_spin * self.rng.uniform(
                                    config.BRANCH_ANGLE_MIN,
                                    config.BRANCH_ANGLE_MAX,
                                )
                                b_radius = final_radius + self.rng.uniform(
                                    config.ARM_OUTWARD_STEP_MIN * 0.8,
                                    config.ARM_OUTWARD_STEP_MAX * 1.1,
                                )

                                b_wobble = self.rng.uniform(
                                    -config.ARM_WOBBLE_RADIAL * 0.4,
                                    config.ARM_WOBBLE_RADIAL * 0.4,
                                )
                                b_radius += b_wobble

                                branch_candidate = center + pygame.Vector2(
                                    math.cos(b_theta) * b_radius,
                                    math.sin(b_theta) * b_radius,
                                )

                                if b_radius > config.ARM_MAX_RADIUS + 50:
                                    break

                                branch_id = try_place(
                                    branch_candidate,
                                    branch_prev,
                                    (
                                        config.PRODUCTION_MIN * 0.7,
                                        config.PRODUCTION_MAX * 0.9,
                                    ),
                                )

                                if branch_id is None:
                                    break

                                branch_prev = branch_id

                        break

            if not progressed_any and all(arm["done"] for arm in arms):
                break

        attempts = 0
        max_attempts = config.STAR_COUNT * 50

        while len(positions) < config.STAR_COUNT and attempts < max_attempts:
            attempts += 1

            parent_id = self.rng.randrange(len(positions))
            parent_pos = positions[parent_id]

            parent_relative = parent_pos - center
            parent_radius = parent_relative.length()
            parent_theta = math.atan2(parent_relative.y, parent_relative.x)

            angular_step = self.rng.uniform(
                config.ARM_SPIN_MIN * 0.6,
                config.ARM_SPIN_MAX * 1.3,
            )
            spin_dir = self.rng.choice([1.0, -1.0])

            new_theta = parent_theta + spin_dir * angular_step
            new_radius = parent_radius + self.rng.uniform(
                config.ARM_OUTWARD_STEP_MIN * 0.7,
                config.ARM_OUTWARD_STEP_MAX * 1.2,
            )

            candidate = center + pygame.Vector2(
                math.cos(new_theta) * new_radius,
                math.sin(new_theta) * new_radius,
            )

            try_place(
                candidate,
                parent_id,
                (
                    config.PRODUCTION_MIN * 0.7,
                    config.PRODUCTION_MAX * 0.9,
                ),
            )

        for i, (pos, (name, prod)) in enumerate(zip(positions, system_data)):
            ships = float(
                self.rng.randint(config.NEUTRAL_SHIPS_MIN, config.NEUTRAL_SHIPS_MAX)
            )

            self.systems.append(
                StarSystem(
                    id=i,
                    name=name,
                    pos=pos,
                    production=prod,
                    ships=ships,
                )
            )

            self.neighbors[i] = set()

        for first_id, second_id in lane_set:
            self.edges.add((first_id, second_id))
            self.neighbors[first_id].add(second_id)
            self.neighbors[second_id].add(first_id)

    @staticmethod
    def _core_connected(
        adjacency: dict[int, set[int]],
        source: int,
        target: int,
    ) -> bool:
        visited = {source}
        queue = [source]

        while queue:
            current = queue.pop(0)

            if current == target:
                return True

            for neighbor in adjacency.get(current, ()):
                if neighbor in visited:
                    continue

                visited.add(neighbor)
                queue.append(neighbor)

        return False

    @staticmethod
    def _segments_intersect(
        first: pygame.Vector2,
        second: pygame.Vector2,
        third: pygame.Vector2,
        fourth: pygame.Vector2,
    ) -> bool:
        def orientation(
            a: pygame.Vector2,
            b: pygame.Vector2,
            c: pygame.Vector2,
        ) -> float:
            return (
                (b.x - a.x) * (c.y - a.y)
                - (b.y - a.y) * (c.x - a.x)
            )

        first_orientation = orientation(first, second, third)
        second_orientation = orientation(first, second, fourth)
        third_orientation = orientation(third, fourth, first)
        fourth_orientation = orientation(third, fourth, second)

        return (
            first_orientation * second_orientation < 0
            and third_orientation * fourth_orientation < 0
        )

    def _make_name(
        self,
        prefixes: list[str],
        suffixes: list[str],
        used: set[str],
    ) -> str:
        for _ in range(400):
            name = self.rng.choice(prefixes) + self.rng.choice(suffixes)
            if name not in used:
                used.add(name)
                return name
        name = f"Sys{len(used)}"
        used.add(name)
        return name

    def _create_empires(self) -> None:
        for empire_id in range(config.EMPIRE_COUNT):
            self.empires.append(
                Empire(
                    id=empire_id,
                    name=config.EMPIRE_NAMES[empire_id % len(config.EMPIRE_NAMES)],
                    color=config.EMPIRE_COLORS[empire_id % len(config.EMPIRE_COLORS)],
                    is_player=(empire_id == config.PLAYER_ID),
                )
            )

    def _place_empires(self) -> None:
        center = pygame.Vector2(
            config.GALAXY_CENTER_X,
            config.GALAXY_CENTER_Y,
        )

        def distance_from_center(system: StarSystem) -> float:
            return system.pos.distance_to(center)

        arm_tip = max(
            self.systems,
            key=distance_from_center,
        )
        arm_tip.owner_id = config.PLAYER_ID
        arm_tip.ships = config.STARTING_SHIPS

        chosen: list[int] = [arm_tip.id]

        while len(chosen) < len(self.empires):
            best_id = None
            best_distance = -1.0

            for system in self.systems:
                if system.id in chosen:
                    continue

                distance = min(
                    system.pos.distance_to(self.systems[cid].pos)
                    for cid in chosen
                )

                if distance > best_distance:
                    best_distance = distance
                    best_id = system.id

            if best_id is not None:
                chosen.append(best_id)
            else:
                break

        for i, empire in enumerate(self.empires):
            if empire.id >= len(chosen):
                continue
            system = self.systems[chosen[i]]
            system.owner_id = empire.id
            system.ships = config.STARTING_SHIPS

    def _produce_ships(self, dt: float) -> None:
        owned_counts: dict[int, int] = {}

        for system in self.systems:
            if system.owner_id is None:
                continue
            owned_counts[system.owner_id] = (
                owned_counts.get(system.owner_id, 0) + 1
            )

        for system in self.systems:
            if system.owner_id is None:
                continue
            owned_count = max(1, owned_counts.get(system.owner_id, 1))
            efficiency = owned_count ** config.PRODUCTION_CONCENTRATION
            system.ships += system.production * dt / efficiency

    def shortest_path(
        self,
        source_id: int,
        target_id: int,
    ) -> Optional[tuple[int, ...]]:
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

    def reachable_system_ids(
        self,
        source_id: int,
    ) -> set[int]:
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

    def launch_fleet(
        self,
        source_id: int,
        target_id: int,
        send_percent: int,
    ) -> bool:
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

        self.fleets.append(
            Fleet(
                id=self.next_fleet_id,
                owner_id=source.owner_id,
                source_id=source_id,
                target_id=target_id,
                ships=float(amount),
                route=route,
                route_index=1,
                segment_progress=0.0,
            )
        )

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

        self.combat_shots = [
            shot for shot in self.combat_shots if shot.lifetime > 0.0
        ]

        for fleet in list(self.fleets):
            if fleet.siege_target_id is not None:
                system = self.systems[fleet.siege_target_id]

                if system.owner_id != fleet.owner_id and system.ships > 0.01:
                    fleet.position = system.pos
                    new_shots = resolve_fleet_combat(
                        fleet=fleet,
                        fleet_position=fleet.position,
                        target=system,
                        dt=dt,
                        attacker_color=self.empires[fleet.owner_id].color,
                        defender_color=(
                            self.empires[system.owner_id].color
                            if system.owner_id is not None
                            else config.NEUTRAL_COLOR
                        ),
                        rng=self.rng,
                    )
                    self.combat_shots.extend(new_shots)

                    if fleet.ships <= 0.01:
                        if fleet in self.fleets:
                            self.fleets.remove(fleet)
                    continue

                if system.owner_id != fleet.owner_id:
                    system.owner_id = fleet.owner_id
                    system.ships = 0.0
                fleet.siege_target_id = None
                fleet.segment_progress = 0.0

            current_id = fleet.route[fleet.route_index - 1]
            next_id = (
                fleet.route[fleet.route_index]
                if fleet.route_index < len(fleet.route)
                else fleet.route[-1]
            )

            current_system = self.systems[current_id]
            next_system = self.systems[next_id]

            segment_distance = current_system.pos.distance_to(next_system.pos)

            fleet.segment_progress += (
                config.FLEET_SPEED * dt
            ) / max(1.0, segment_distance)

            if fleet.segment_progress <= 1.0:
                fleet.position = current_system.pos.lerp(
                    next_system.pos,
                    min(1.0, fleet.segment_progress),
                )
            else:
                fleet.position = next_system.pos

                if fleet.route_index >= len(fleet.route) - 1:
                    fleet.progress = 1.0
                    arrived.append(fleet)
                else:
                    fleet.route_index += 1
                    fleet.segment_progress = 0.0

                    if next_system.owner_id != fleet.owner_id:
                        if next_system.ships > 0.01:
                            fleet.siege_target_id = next_id
                        else:
                            next_system.owner_id = fleet.owner_id
                            next_system.ships = 0.0

            dest_system = self.systems[fleet.target_id]
            if dest_system.owner_id is not None and dest_system.owner_id != fleet.owner_id:
                distance_from_dest = fleet.position.distance_to(dest_system.pos)
                if distance_from_dest <= config.COMBAT_RANGE:
                    new_shots = resolve_fleet_combat(
                        fleet=fleet,
                        fleet_position=fleet.position,
                        target=dest_system,
                        dt=dt,
                        attacker_color=self.empires[fleet.owner_id].color,
                        defender_color=self.empires[dest_system.owner_id].color,
                        rng=self.rng,
                    )
                    self.combat_shots.extend(new_shots)

            if fleet.ships <= 0.01:
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

    def _update_empire_status(self) -> None:
        for empire in self.empires:
            owns_system = any(
                system.owner_id == empire.id
                for system in self.systems
            )
            owns_fleet = any(
                fleet.owner_id == empire.id
                for fleet in self.fleets
            )
            empire.alive = owns_system or owns_fleet

    def system_at(
        self,
        position: tuple[int, int],
        radius: float = 18,
    ) -> Optional[StarSystem]:
        point = pygame.Vector2(position)
        candidates = [
            system
            for system in self.systems
            if system.pos.distance_to(point) <= radius
        ]
        if not candidates:
            return None
        return min(
            candidates,
            key=lambda system: system.pos.distance_to(point),
        )

    def get_system(self, system_id: int) -> StarSystem:
        return self.systems[system_id]

    def get_empire(self, empire_id: int) -> Empire:
        return self.empires[empire_id]

    def get_neighbors(self, system_id: int) -> list[StarSystem]:
        return [
            self.systems[neighbor_id]
            for neighbor_id in self.neighbors[system_id]
        ]

    def is_neighbor(self, first_id: int, second_id: int) -> bool:
        return second_id in self.neighbors[first_id]

    def owned_systems(self, empire_id: int) -> list[StarSystem]:
        return [
            system
            for system in self.systems
            if system.owner_id == empire_id
        ]

    def empire_system_count(self, empire_id: int) -> int:
        return sum(
            1
            for system in self.systems
            if system.owner_id == empire_id
        )

    def empire_ship_count(self, empire_id: int) -> float:
        stationed = sum(
            system.ships
            for system in self.systems
            if system.owner_id == empire_id
        )
        travelling = sum(
            fleet.ships
            for fleet in self.fleets
            if fleet.owner_id == empire_id
        )
        return stationed + travelling

    def living_empires(self) -> list[Empire]:
        return [
            empire
            for empire in self.empires
            if empire.alive
        ]

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