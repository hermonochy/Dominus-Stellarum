from collections import deque

import pygame

from . import config
from .combat import gun_range
from .models import CommandShip


class CommandDirector:
    def __init__(self, galaxy):
        self.galaxy = galaxy
        self.ships: dict[int, CommandShip] = {}
        self.ai_relocation_cooldowns: dict[int, float] = {}

    def initialize(self) -> None:
        self.ships.clear()
        self.ai_relocation_cooldowns.clear()
        for empire in self.galaxy.empires:
            self.establish(empire.id)

    def get(self, empire_id: int) -> CommandShip | None:
        return self.ships.get(empire_id)

    def capital(self, empire_id: int) -> int | None:
        ship = self.get(empire_id)
        return ship.system_id if ship is not None else None

    def can_order(self, empire_id: int) -> bool:
        if empire_id < 0 or empire_id >= len(self.galaxy.empires):
            return False
        empire = self.galaxy.empires[empire_id]
        return empire.alive and empire.command_lockout <= 0.0 and empire_id in self.ships

    def _friendly_route(self, start: int, destination: int, empire_id: int) -> tuple[int, ...] | None:
        if self.galaxy.systems[start].owner_id != empire_id:
            return None
        if self.galaxy.systems[destination].owner_id != empire_id:
            return None
        previous: dict[int, int | None] = {start: None}
        queue = deque([start])
        while queue:
            current = queue.popleft()
            if current == destination:
                path = []
                while current is not None:
                    path.append(current)
                    current = previous[current]
                return tuple(reversed(path))
            for neighbor in self.galaxy.neighbors.get(current, ()):
                if neighbor not in previous and self.galaxy.systems[neighbor].owner_id == empire_id:
                    previous[neighbor] = current
                    queue.append(neighbor)
        return None

    def reachable_owned_from(self, system_id: int, empire_id: int) -> set[int]:
        if self.galaxy.systems[system_id].owner_id != empire_id:
            return set()
        visited = {system_id}
        queue = deque([system_id])
        while queue:
            current = queue.popleft()
            for neighbor in self.galaxy.neighbors.get(current, ()):
                if neighbor not in visited and self.galaxy.systems[neighbor].owner_id == empire_id:
                    visited.add(neighbor)
                    queue.append(neighbor)
        return visited

    def reachable_destinations(self, empire_id: int) -> set[int]:
        ship = self.get(empire_id)
        if ship is None or ship.system_id is None:
            return set()
        reachable = self.reachable_owned_from(ship.system_id, empire_id)
        reachable.discard(ship.system_id)
        return reachable

    def _depths(self, empire_id: int) -> dict[int, int]:
        owned = {node.id for node in self.galaxy.systems if node.owner_id == empire_id}
        if not owned:
            return {}
        border = [
            sid for sid in owned
            if any(nid not in owned for nid in self.galaxy.neighbors.get(sid, ()))
        ]
        if not border:
            border = list(owned)
        depths = {sid: 0 for sid in border}
        queue = deque(border)
        while queue:
            current = queue.popleft()
            for neighbor in self.galaxy.neighbors.get(current, ()):
                if neighbor in owned and neighbor not in depths:
                    depths[neighbor] = depths[current] + 1
                    queue.append(neighbor)
        return depths

    def safest_system(self, empire_id: int, from_system: int | None = None) -> int | None:
        depths = self._depths(empire_id)
        if not depths:
            return None
        if from_system is not None:
            reachable = self.reachable_owned_from(from_system, empire_id)
            depths = {sid: depth for sid, depth in depths.items() if sid in reachable}
        if not depths:
            return None

        def score(system_id):
            system = self.galaxy.systems[system_id]
            inbound = sum(
                fleet.ships for fleet in self.galaxy.fleets
                if not fleet.is_missile and fleet.owner_id != empire_id
                and fleet.target_id == system_id
            )
            hostile = sum(
                self.galaxy.systems[nid].ships
                for nid in self.galaxy.neighbors.get(system_id, ())
                if self.galaxy.systems[nid].owner_id not in (None, empire_id)
            )
            return (
                depths[system_id] * config.COMMAND_AI_DEPTH_WEIGHT
                + min(system.ships, 200) * config.COMMAND_AI_GARRISON_WEIGHT
                - inbound * config.COMMAND_AI_DANGER_WEIGHT
                - hostile * config.COMMAND_AI_DANGER_WEIGHT
            )

        return max(depths, key=lambda sid: (score(sid), self.galaxy.systems[sid].ships, -sid))

    def establish(self, empire_id: int) -> bool:
        if empire_id in self.ships:
            return False
        empire = self.galaxy.empires[empire_id]
        if empire.command_lockout > 0.0:
            return False
        system_id = self.safest_system(empire_id)
        if system_id is None:
            return False
        system = self.galaxy.systems[system_id]
        self.ships[empire_id] = CommandShip(
            owner_id=empire_id,
            system_id=system_id,
            position=system.pos.copy(),
            hull=config.COMMAND_SHIP_HULL,
        )
        return True

    def move(self, empire_id: int, target_id: int) -> bool:
        if not self.can_order(empire_id) or target_id < 0 or target_id >= len(self.galaxy.systems):
            return False
        ship = self.ships[empire_id]
        if ship.system_id is None or ship.system_id == target_id:
            return False
        route = self._friendly_route(ship.system_id, target_id, empire_id)
        if route is None or len(route) < 2:
            return False
        ship.system_id = None
        ship.route = route
        ship.route_index = 1
        ship.segment_progress = 0.0
        ship.destination_id = target_id
        return True

    def lose(self, empire_id: int, reason: str) -> None:
        ship = self.ships.pop(empire_id, None)
        if ship is None:
            return
        empire = self.galaxy.empires[empire_id]
        empire.command_lockout = config.COMMAND_DISRUPTION_DURATION
        empire.command_losses += 1
        self.ai_relocation_cooldowns.pop(empire_id, None)
        if empire_id == config.PLAYER_ID and not self.galaxy.player_succession_complete:
            self.galaxy.pending_messages.append(
                f"Command ship {reason}! No new orders for {int(config.COMMAND_DISRUPTION_DURATION)} seconds."
            )

    def on_nuclear_blast(self, position: pygame.Vector2, radius: float) -> None:
        for empire_id, ship in list(self.ships.items()):
            if ship.position.distance_to(position) <= radius:
                self.lose(empire_id, "destroyed by a nuclear strike")

    def _advance(self, ship: CommandShip, dt: float) -> None:
        if ship.system_id is not None:
            system = self.galaxy.systems[ship.system_id]
            ship.position = system.pos.copy()
            if system.owner_id != ship.owner_id:
                self.lose(ship.owner_id, "lost when its capital was captured")
                return
            ship.hull = min(config.COMMAND_SHIP_HULL, ship.hull + config.COMMAND_SHIP_REPAIR_RATE * dt)
            return

        remaining = config.FLEET_SPEED * config.COMMAND_SHIP_SPEED_MULT * dt
        while remaining > 0 and ship.system_id is None:
            source = self.galaxy.systems[ship.route[ship.route_index - 1]]
            target = self.galaxy.systems[ship.route[ship.route_index]]
            length = max(0.001, source.pos.distance_to(target.pos))
            distance_left = (1.0 - ship.segment_progress) * length
            distance = min(remaining, distance_left)
            ship.segment_progress = min(1.0, ship.segment_progress + distance / length)
            prior_position = ship.position.copy()
            ship.position = source.pos.lerp(target.pos, ship.segment_progress)
            remaining -= distance
            travel_time = distance / (config.FLEET_SPEED * config.COMMAND_SHIP_SPEED_MULT)
            midpoint = prior_position.lerp(ship.position, 0.5)
            self._apply_transit_fire(ship, travel_time * 0.5, midpoint)
            if ship.owner_id not in self.ships:
                return
            self._apply_transit_fire(ship, travel_time * 0.5, ship.position)
            if ship.owner_id not in self.ships:
                return
            if ship.segment_progress < 1.0:
                break
            if target.owner_id != ship.owner_id:
                self.lose(ship.owner_id, "intercepted in hostile territory")
                return
            if ship.route_index == len(ship.route) - 1:
                ship.system_id = target.id
                ship.destination_id = None
                ship.route = ()
                ship.route_index = 1
                ship.segment_progress = 0.0
            else:
                ship.route_index += 1
                ship.segment_progress = 0.0

    def _apply_transit_fire(self, ship: CommandShip, dt: float, position: pygame.Vector2) -> None:
        if ship.system_id is not None:
            return
        total_damage = 0.0
        for system in self.galaxy._nearby_systems(position, config.COMMAND_SHIP_SCAN_RADIUS):
            if system.owner_id in (None, ship.owner_id) or system.ships <= config.COMBAT_MIN_SHIPS:
                continue
            if position.distance_to(system.pos) <= gun_range(system):
                total_damage += system.ships * config.COMMAND_SHIP_DAMAGE_PER_SHIP * dt
        for fleet in self.galaxy.fleets:
            if fleet.owner_id == ship.owner_id or fleet.is_missile or fleet.ships <= config.COMBAT_MIN_SHIPS:
                continue
            if position.distance_to(fleet.position) <= gun_range(fleet):
                total_damage += fleet.ships * config.COMMAND_SHIP_DAMAGE_PER_SHIP * dt
        ship.hull -= total_damage
        if ship.hull <= 0.0:
            self.lose(ship.owner_id, "shot down while in transit")

    def update(self, dt: float) -> None:
        for empire_id in list(self.ai_relocation_cooldowns):
            self.ai_relocation_cooldowns[empire_id] = max(0.0, self.ai_relocation_cooldowns[empire_id] - dt)
        for empire in self.galaxy.empires:
            if empire.command_lockout > 0.0:
                empire.command_lockout = max(0.0, empire.command_lockout - dt)
                if empire.command_lockout == 0.0:
                    if empire.id == config.PLAYER_ID and not self.galaxy.player_succession_complete:
                        self.galaxy.player_succession_complete = True
                        self.galaxy.autopilot = True
                        empire.is_player = False
                        self.galaxy.pending_messages.append("Succession complete. Your former empire is now AI-controlled.")
                    self.establish(empire.id)
            elif empire.alive and empire.id not in self.ships:
                self.establish(empire.id)
        for ship in list(self.ships.values()):
            self._advance(ship, dt)

    def manage_ai(self, empire_id: int) -> None:
        if empire_id == config.PLAYER_ID and not self.galaxy.player_succession_complete:
            return
        if not self.can_order(empire_id):
            return
        ship = self.ships[empire_id]
        if ship.system_id is None or self.ai_relocation_cooldowns.get(empire_id, 0.0) > 0.0:
            return
        current = self.galaxy.systems[ship.system_id]
        destination = self.safest_system(empire_id, ship.system_id)
        if destination is None or destination == current.id:
            return
        hostile_neighbors = any(
            self.galaxy.systems[nid].owner_id not in (None, empire_id)
            for nid in self.galaxy.neighbors.get(current.id, ())
        )
        incoming = sum(
            fleet.ships for fleet in self.galaxy.fleets
            if not fleet.is_missile and fleet.owner_id != empire_id and fleet.target_id == current.id
        )
        depths = self._depths(empire_id)
        safer = depths.get(destination, 0) > depths.get(current.id, 0)
        urgent = hostile_neighbors or incoming > max(1.0, current.ships * config.COMMAND_AI_ESCAPE_THRESHOLD)
        if (urgent or safer) and self.move(empire_id, destination):
            self.ai_relocation_cooldowns[empire_id] = config.COMMAND_AI_RELOCATE_COOLDOWN
