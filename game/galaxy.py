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

        center = pygame.Vector2(
            config.GALAXY_CENTER_X,
            config.GALAXY_CENTER_Y,
        )

        for system_id in range(
            config.STAR_COUNT
        ):
            arm = system_id % config.GALAXY_ARMS

            progress = (
                system_id
                / max(
                    1,
                    config.STAR_COUNT - 1,
                )
            )

            radius = 35.0 + (
                progress
                * min(
                    config.GALAXY_RADIUS_X,
                    config.GALAXY_RADIUS_Y,
                )
            )

            angle = (
                arm
                * (
                    math.tau
                    / config.GALAXY_ARMS
                )
                + progress
                * config.GALAXY_ARM_TWIST
                * math.tau
            )

            position = center + pygame.Vector2(
                math.cos(angle)
                * radius
                * 1.7,
                math.sin(angle)
                * radius,
            )

            position.x += self.rng.uniform(
                -config.GALAXY_POSITION_JITTER,
                config.GALAXY_POSITION_JITTER,
            )

            position.y += self.rng.uniform(
                -config.GALAXY_POSITION_JITTER,
                config.GALAXY_POSITION_JITTER,
            )

            position.x = max(
                60,
                min(
                    config.WIDTH - 60,
                    position.x,
                ),
            )

            position.y = max(
                config.TOP_BAR_HEIGHT + 35,
                min(
                    config.HEIGHT
                    - config.BOTTOM_BAR_HEIGHT
                    - 30,
                    position.y,
                ),
            )

            if any(
                position.distance_to(other)
                < config.MIN_STAR_DISTANCE
                for other in positions
            ):
                position += pygame.Vector2(
                    self.rng.uniform(-30, 30),
                    self.rng.uniform(-30, 30),
                )

            positions.append(position)

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

        for system_id, position in enumerate(
            positions
        ):
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
        candidates: list[
            tuple[float, int, int]
        ] = []

        for first in self.systems:
            for second in self.systems[
                first.id + 1:
            ]:
                distance = first.pos.distance_to(
                    second.pos
                )

                candidates.append(
                    (
                        distance,
                        first.id,
                        second.id,
                    )
                )

        candidates.sort()

        # First build a connected, non-crossing
        # backbone using short links.
        for _, first_id, second_id in candidates:
            if self._has_path(
                first_id,
                second_id,
            ):
                continue

            if self._can_connect(
                first_id,
                second_id,
            ):
                self._connect(
                    first_id,
                    second_id,
                )

        # Add short, non-crossing links until most
        # systems have two or three connections.
        for _, first_id, second_id in candidates:
            if (
                len(self.neighbors[first_id])
                >= config.MAX_CONNECTIONS
            ):
                continue

            if (
                len(self.neighbors[second_id])
                >= config.MAX_CONNECTIONS
            ):
                continue

            if self.rng.random() > 0.35:
                continue

            if self._can_connect(
                first_id,
                second_id,
            ):
                self._connect(
                    first_id,
                    second_id,
                )

        # A final pass guarantees that isolated systems
        # have at least one connection.
        for system in self.systems:
            if self.neighbors[system.id]:
                continue

            nearest = min(
                (
                    other
                    for other in self.systems
                    if other.id != system.id
                ),
                key=lambda other: (
                    system.pos.distance_to(
                        other.pos
                    )
                ),
            )

            if self._can_connect(
                system.id,
                nearest.id,
                ignore_degree=True,
            ):
                self._connect(
                    system.id,
                    nearest.id,
                )

    def _can_connect(
        self,
        first_id: int,
        second_id: int,
        ignore_degree: bool = False,
    ) -> bool:
        if first_id == second_id:
            return False

        if (
            second_id
            in self.neighbors[first_id]
        ):
            return False

        if not ignore_degree:
            if (
                len(self.neighbors[first_id])
                >= config.MAX_CONNECTIONS
            ):
                return False

            if (
                len(self.neighbors[second_id])
                >= config.MAX_CONNECTIONS
            ):
                return False

        first = self.systems[first_id]
        second = self.systems[second_id]

        for edge_first, edge_second in self.edges:
            if first_id in (
                edge_first,
                edge_second,
            ):
                continue

            if second_id in (
                edge_first,
                edge_second,
            ):
                continue

            other_first = self.systems[
                edge_first
            ]

            other_second = self.systems[
                edge_second
            ]

            if self._segments_intersect(
                first.pos,
                second.pos,
                other_first.pos,
                other_second.pos,
            ):
                return False

        return True

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
                (b.x - a.x)
                * (c.y - a.y)
                - (b.y - a.y)
                * (c.x - a.x)
            )

        first_orientation = orientation(
            first,
            second,
            third,
        )

        second_orientation = orientation(
            first,
            second,
            fourth,
        )

        third_orientation = orientation(
            third,
            fourth,
            first,
        )

        fourth_orientation = orientation(
            third,
            fourth,
            second,
        )

        return (
            first_orientation
            * second_orientation
            < 0
            and third_orientation
            * fourth_orientation
            < 0
        )

    def _connect(
        self,
        first_id: int,
        second_id: int,
    ) -> None:
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

    def _has_path(
        self,
        source_id: int,
        target_id: int,
    ) -> bool:
        if source_id == target_id:
            return True

        visited = {source_id}
        queue = [source_id]

        while queue:
            current = queue.pop(0)

            for neighbor in self.neighbors[current]:
                if neighbor == target_id:
                    return True

                if neighbor in visited:
                    continue

                visited.add(neighbor)
                queue.append(neighbor)

        return False

    def _create_empires(self) -> None:
        for empire_id in range(
            config.EMPIRE_COUNT
        ):
            self.empires.append(
                Empire(
                    id=empire_id,
                    name=config.EMPIRE_NAMES[
                        empire_id
                        % len(config.EMPIRE_NAMES)
                    ],
                    color=config.EMPIRE_COLORS[
                        empire_id
                        % len(config.EMPIRE_COLORS)
                    ],
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
                    self.systems[
                        system_id
                    ].pos.distance_to(
                        self.systems[
                            chosen_id
                        ].pos
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

    def _produce_ships(
        self,
        dt: float,
    ) -> None:
        owned_counts: dict[int, int] = {}

        for system in self.systems:
            if system.owner_id is None:
                continue

            owned_counts[system.owner_id] = (
                owned_counts.get(
                    system.owner_id,
                    0,
                )
                + 1
            )

        for system in self.systems:
            if system.owner_id is None:
                continue

            owned_count = max(
                1,
                owned_counts.get(
                    system.owner_id,
                    1,
                ),
            )

            efficiency = (
                owned_count
                ** config.PRODUCTION_CONCENTRATION
            )

            system.ships += (
                system.production
                * dt
                / efficiency
            )

    def shortest_path(
        self,
        source_id: int,
        target_id: int,
    ) -> Optional[tuple[int, ...]]:
        if source_id == target_id:
            return (source_id,)

        if (
            source_id not in self.neighbors
            or target_id not in self.neighbors
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
        queue = [source_id]

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

        fraction = max(
            0.0,
            min(
                1.0,
                send_percent / 100.0,
            ),
        )

        amount = math.floor(
            source.ships * fraction
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
                segment_progress=0.0,
            )
        )

        self.next_fleet_id += 1
        return True

    def fleet_position(
        self,
        fleet: Fleet,
    ) -> pygame.Vector2:
        source = self.systems[
            fleet.source_id
        ]

        target = self.systems[
            fleet.target_id
        ]

        return source.pos.lerp(
            target.pos,
            min(1.0, fleet.progress),
        )

    def _update_fleets(self, dt: float) -> None:
        arrived: list[Fleet] = []

        # Update combat shots
        for shot in self.combat_shots:
            shot.lifetime -= dt

        self.combat_shots = [
            shot for shot in self.combat_shots if shot.lifetime > 0.0
        ]

        for fleet in list(self.fleets):
            # Get current waypoint (current node in route)
            current_id = fleet.route[fleet.route_index - 1]
            next_id = fleet.route[fleet.route_index] if fleet.route_index < len(fleet.route) else fleet.route[-1]
            
            current_system = self.systems[current_id]
            next_system = self.systems[next_id]
            
            # Calculate distance to next hop
            segment_distance = current_system.pos.distance_to(next_system.pos)
            
            # Update progress along current segment
            fleet.segment_progress += (config.FLEET_SPEED * dt) / max(1.0, segment_distance)
            
            # Interpolate position along current segment
            if fleet.segment_progress <= 1.0:
                fleet.position = current_system.pos.lerp(
                    next_system.pos,
                    min(1.0, fleet.segment_progress)
                )
            else:
                # Reached next hop
                fleet.position = next_system.pos
                
                # Check if we need to continue or arrive
                if fleet.route_index >= len(fleet.route) - 1:
                    # Final destination reached
                    fleet.progress = 1.0
                    arrived.append(fleet)
                else:
                    # Move to next hop
                    fleet.route_index += 1
                    fleet.segment_progress = 0.0
                    
                    # Check for combat at intermediate systems
                    intermediate_system = self.systems[next_id]
                    if intermediate_system.owner_id != fleet.owner_id and intermediate_system.owner_id is not None:
                        new_shots = resolve_fleet_combat(
                            fleet=fleet,
                            fleet_position=fleet.position,
                            target=intermediate_system,
                            dt=dt,
                            attacker_color=self.empires[fleet.owner_id].color,
                            defender_color=self.empires[intermediate_system.owner_id].color,
                            rng=self.rng,
                        )
                        self.combat_shots.extend(new_shots)
            
            # Combat with destination system when close enough
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

            # Remove destroyed fleets
            if fleet.ships <= 0.01:
                if fleet in self.fleets:
                    self.fleets.remove(fleet)
                continue
            
            # Limit visible combat shots
            if len(self.combat_shots) > config.MAX_VISIBLE_SHOTS:
                self.combat_shots = self.combat_shots[-config.MAX_VISIBLE_SHOTS:]

        # Process fleet arrivals at destinations
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