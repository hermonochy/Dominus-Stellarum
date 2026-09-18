from __future__ import annotations

import math
import random
from typing import Optional

import pygame

from . import config
from .combat import resolve_fleet_arrival
from .models import Empire, Fleet, StarSystem


class Galaxy:
    def __init__(
        self,
        seed: Optional[int] = None,
    ):
        self.rng = random.Random(seed)

        self.systems: list[StarSystem] = []
        self.empires: list[Empire] = []
        self.fleets: list[Fleet] = []

        self.edges: set[tuple[int, int]] = set()
        self.neighbors: dict[int, set[int]] = {}

        self.next_fleet_id = 0

        self.generate()

    def generate(self) -> None:
        self.systems.clear()
        self.empires.clear()
        self.fleets.clear()
        self.edges.clear()
        self.neighbors.clear()

        self.next_fleet_id = 0

        self._create_systems()
        self._create_hyperlanes()
        self._create_empires()
        self._place_empires()

    def update(
        self,
        dt: float,
    ) -> None:
        self._produce_ships(dt)
        self._update_fleets(dt)
        self._update_empire_status()

    def _create_systems(self) -> None:
        positions: list[pygame.Vector2] = []

        attempts = 0
        min_y = config.TOP_BAR_HEIGHT + 40
        max_y = (
            config.HEIGHT
            - config.BOTTOM_BAR_HEIGHT
            - 30
        )

        while (
            len(positions) < config.STAR_COUNT
            and attempts < 15000
        ):
            attempts += 1

            position = pygame.Vector2(
                self.rng.randint(
                    60,
                    config.WIDTH - 60,
                ),
                self.rng.randint(
                    min_y,
                    max_y,
                ),
            )

            if all(
                position.distance_to(other)
                >= config.MIN_STAR_DISTANCE
                for other in positions
            ):
                positions.append(position)

        while len(positions) < config.STAR_COUNT:
            positions.append(
                pygame.Vector2(
                    self.rng.randint(
                        60,
                        config.WIDTH - 60,
                    ),
                    self.rng.randint(
                        min_y,
                        max_y,
                    ),
                )
            )

        prefixes = [
            "Al",
            "Ar",
            "Bel",
            "Ca",
            "Cor",
            "Del",
            "Er",
            "Fal",
            "Gal",
            "Hel",
            "Io",
            "Jan",
            "Kel",
            "Lor",
            "Mor",
            "Nor",
            "Or",
            "Pra",
            "Qua",
            "Ren",
            "Sol",
            "Tal",
            "Ur",
            "Vel",
            "Wex",
            "Xan",
            "Yar",
            "Zen",
        ]

        suffixes = [
            "a",
            "ar",
            "ea",
            "en",
            "eron",
            "ia",
            "ion",
            "is",
            "on",
            "or",
            "os",
            "um",
            "us",
        ]

        used_names: set[str] = set()

        for system_id, position in enumerate(positions):
            name = self._generate_system_name(
                prefixes,
                suffixes,
                used_names,
            )

            production = self.rng.uniform(
                config.PRODUCTION_MIN,
                config.PRODUCTION_MAX,
            )

            ships = float(
                self.rng.randint(
                    config.NEUTRAL_SHIPS_MIN,
                    config.NEUTRAL_SHIPS_MAX,
                )
            )

            self.systems.append(
                StarSystem(
                    id=system_id,
                    name=name,
                    pos=position,
                    production=production,
                    ships=ships,
                )
            )

            self.neighbors[system_id] = set()

    def _generate_system_name(
        self,
        prefixes: list[str],
        suffixes: list[str],
        used_names: set[str],
    ) -> str:
        while True:
            name = (
                self.rng.choice(prefixes)
                + self.rng.choice(suffixes)
            )

            if name not in used_names:
                used_names.add(name)
                return name

    def _create_hyperlanes(self) -> None:
        for system in self.systems:
            distances = sorted(
                (
                    (
                        system.pos.distance_to(
                            other.pos
                        ),
                        other.id,
                    )
                    for other in self.systems
                    if other.id != system.id
                ),
                key=lambda item: item[0],
            )

            for _, other_id in distances[
                :config.MIN_CONNECTIONS
            ]:
                self._connect(
                    system.id,
                    other_id,
                )

        for first in self.systems:
            for second in self.systems[first.id + 1:]:
                distance = first.pos.distance_to(
                    second.pos
                )

                if distance > config.EDGE_DISTANCE:
                    continue

                normalized = (
                    distance
                    / config.EDGE_DISTANCE
                )

                chance = (
                    0.5
                    * (1.0 - normalized)
                    + 0.08
                )

                if self.rng.random() < chance:
                    self._connect(
                        first.id,
                        second.id,
                    )

        self._ensure_connected()

    def _connect(
        self,
        first_id: int,
        second_id: int,
    ) -> None:
        if first_id == second_id:
            return

        edge = tuple(
            sorted(
                (
                    first_id,
                    second_id,
                )
            )
        )

        self.edges.add(edge)

        self.neighbors[first_id].add(second_id)
        self.neighbors[second_id].add(first_id)

    def _ensure_connected(self) -> None:
        while True:
            components = self._get_components()

            if len(components) <= 1:
                return

            first_component = components[0]
            best_pair = None
            best_distance = float("inf")

            for first_id in first_component:
                for component in components[1:]:
                    for second_id in component:
                        distance = (
                            self.systems[first_id].pos.distance_to(
                                self.systems[second_id].pos
                            )
                        )

                        if distance < best_distance:
                            best_distance = distance
                            best_pair = (
                                first_id,
                                second_id,
                            )

            if best_pair is not None:
                self._connect(
                    best_pair[0],
                    best_pair[1],
                )

    def _get_components(self) -> list[set[int]]:
        remaining = set(
            range(len(self.systems))
        )

        components: list[set[int]] = []

        while remaining:
            start = next(iter(remaining))
            stack = [start]
            component: set[int] = set()

            while stack:
                current = stack.pop()

                if current in component:
                    continue

                component.add(current)
                remaining.discard(current)

                for neighbor in self.neighbors[current]:
                    if neighbor not in component:
                        stack.append(neighbor)

            components.append(component)

        return components

    def _create_empires(self) -> None:
        for empire_id in range(config.EMPIRE_COUNT):
            name = config.EMPIRE_NAMES[
                empire_id
                % len(config.EMPIRE_NAMES)
            ]

            color = config.EMPIRE_COLORS[
                empire_id
                % len(config.EMPIRE_COLORS)
            ]

            self.empires.append(
                Empire(
                    id=empire_id,
                    name=name,
                    color=color,
                    is_player=(
                        empire_id
                        == config.PLAYER_ID
                    ),
                )
            )

    def _place_empires(self) -> None:
        first_system = self.rng.randrange(
            len(self.systems)
        )

        chosen = [first_system]

        while len(chosen) < len(self.empires):
            candidates = [
                system.id
                for system in self.systems
                if system.id not in chosen
            ]

            candidate = max(
                candidates,
                key=lambda system_id: min(
                    self.systems[system_id].pos.distance_to(
                        self.systems[chosen_id].pos
                    )
                    for chosen_id in chosen
                ),
            )

            chosen.append(candidate)

        for empire, system_id in zip(
            self.empires,
            chosen,
        ):
            system = self.systems[system_id]
            system.owner_id = empire.id
            system.ships = config.STARTING_SHIPS

    def _produce_ships(self, dt: float) -> None:
        for system in self.systems:
            if system.owner_id is None:
                continue

            system.ships += system.production * dt

    def shortest_path(
        self,
        source_id: int,
        target_id: int,
    ) -> Optional[tuple[int, ...]]:
        if source_id == target_id:
            return (source_id,)

        if (
            source_id < 0
            or source_id >= len(self.systems)
            or target_id < 0
            or target_id >= len(self.systems)
        ):
            return None

        queue = [source_id]

        previous: dict[
            int,
            Optional[int],
        ] = {
            source_id: None,
        }

        while queue:
            current = queue.pop(0)

            for neighbor_id in self.neighbors[current]:
                if neighbor_id in previous:
                    continue

                previous[neighbor_id] = current

                if neighbor_id == target_id:
                    path = [target_id]
                    cursor = target_id

                    while previous[cursor] is not None:
                        cursor = previous[cursor]
                        path.append(cursor)

                    path.reverse()
                    return tuple(path)

                queue.append(neighbor_id)

        return None

    def reachable_system_ids(
        self,
        source_id: int,
    ) -> set[int]:
        reachable: set[int] = set()
        queue = [source_id]

        while queue:
            current = queue.pop(0)

            for neighbor_id in self.neighbors[current]:
                if neighbor_id in reachable:
                    continue

                reachable.add(neighbor_id)
                queue.append(neighbor_id)

        reachable.discard(source_id)
        return reachable

    def launch_fleet(
        self,
        source_id: int,
        target_id: int,
        send_percent: int,
    ) -> bool:
        if (
            source_id < 0
            or source_id >= len(self.systems)
            or target_id < 0
            or target_id >= len(self.systems)
        ):
            return False

        source = self.systems[source_id]

        if source.owner_id is None:
            return False

        route = self.shortest_path(
            source_id,
            target_id,
        )

        if route is None or len(route) < 2:
            return False

        amount = math.floor(
            source.ships
            * send_percent
            / 100.0
        )

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
            )
        )

        self.next_fleet_id += 1
        return True

    def _update_fleets(
        self,
        dt: float,
    ) -> None:
        arrived: list[Fleet] = []

        for fleet in self.fleets:
            source = self.systems[
                fleet.source_id
            ]

            target = self.systems[
                fleet.target_id
            ]

            distance = max(
                1.0,
                source.pos.distance_to(
                    target.pos
                ),
            )

            fleet.progress += (
                config.FLEET_SPEED
                * dt
                / distance
            )

            if fleet.progress < 1.0:
                continue

            if (
                fleet.route_index
                < len(fleet.route) - 1
            ):
                fleet.source_id = fleet.target_id
                fleet.route_index += 1
                fleet.target_id = fleet.route[
                    fleet.route_index
                ]
                fleet.progress = 0.0
            else:
                arrived.append(fleet)

        for fleet in arrived:
            target = self.systems[
                fleet.target_id
            ]

            resolve_fleet_arrival(
                fleet,
                target,
            )

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

            empire.alive = (
                owns_system
                or owns_fleet
            )

    def system_at(
        self,
        position: tuple[int, int],
        radius: float = 18,
    ) -> Optional[StarSystem]:
        point = pygame.Vector2(position)

        candidates = [
            system
            for system in self.systems
            if system.pos.distance_to(point)
            <= radius
        ]

        if not candidates:
            return None

        return min(
            candidates,
            key=lambda system: (
                system.pos.distance_to(point)
            ),
        )

    def get_system(
        self,
        system_id: int,
    ) -> StarSystem:
        return self.systems[system_id]

    def get_empire(
        self,
        empire_id: int,
    ) -> Empire:
        return self.empires[empire_id]

    def get_neighbors(
        self,
        system_id: int,
    ) -> list[StarSystem]:
        return [
            self.systems[neighbor_id]
            for neighbor_id in self.neighbors[system_id]
        ]

    def is_neighbor(
        self,
        first_id: int,
        second_id: int,
    ) -> bool:
        return second_id in self.neighbors[first_id]

    def owned_systems(
        self,
        empire_id: int,
    ) -> list[StarSystem]:
        return [
            system
            for system in self.systems
            if system.owner_id == empire_id
        ]

    def empire_system_count(
        self,
        empire_id: int,
    ) -> int:
        return sum(
            1
            for system in self.systems
            if system.owner_id == empire_id
        )

    def empire_ship_count(
        self,
        empire_id: int,
    ) -> float:
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
        return not self.empires[
            config.PLAYER_ID
        ].alive

    def player_won(self) -> bool:
        winner = self.winner()

        return (
            winner is not None
            and winner.id == config.PLAYER_ID
        )