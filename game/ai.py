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

        if self.think_timer < config.AI_THINK_INTERVAL:
            return
        self.think_timer -= config.AI_THINK_INTERVAL

        for empire in self.galaxy.empires:
            if empire.is_player or not empire.alive:
                continue
            self._think_for_empire(empire.id)

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

    def _try_initiate_breakthrough(self, empire_id: int, front_lines: set[int]) -> None:
        total_ships = self.galaxy.empire_ship_count(empire_id)
        front_reserves = sum(
            self.galaxy.systems[fid].ships
            for fid in front_lines
            if self.galaxy.systems[fid].owner_id == empire_id
        )

        surplus = total_ships - front_reserves - config.AI_BREAKTHROUGH_MIN_SURPLUS

        if surplus < config.AI_BREAKTHROUGH_MIN_SURPLUS:
            self.breakthrough_focus[empire_id] = None
            return

        target = self._find_best_breakthrough_target(empire_id, front_lines)
        if target is None:
            self.breakthrough_focus[empire_id] = None
            return

        self.breakthrough_focus[empire_id] = target
        self.breakthrough_timer[empire_id] = config.AI_BREAKTHROUGH_FOCUS_DURATION

    def _think_for_empire(self, empire_id: int) -> None:
        owned = self.galaxy.owned_systems(empire_id)
        if not owned:
            return

        front_lines = self._identify_front_lines(empire_id)

        own_power = self.galaxy.empire_ship_count(empire_id)
        enemy_powers = self._adjacent_enemy_empires(empire_id)
        self._update_blitz_posture(empire_id, own_power, enemy_powers)

        expansions = self._handle_expansion(empire_id, owned)

        self._strip_excess_from_rear(empire_id, owned, front_lines)

        if self.blitz_target.get(empire_id) is not None:
            self._handle_blitz(empire_id, owned)
        elif self.breakthrough_focus.get(empire_id) is not None:
            self._handle_breakthrough_push(empire_id, owned, front_lines)
        elif expansions == 0 or self.rng.random() > 0.6:
            self._handle_skirmish(empire_id, owned, front_lines)

        self._handle_multi_front_defense(empire_id, owned, front_lines)

    def _strip_excess_from_rear(
        self,
        empire_id: int,
        owned: List[StarSystem],
        front_lines: set[int],
    ) -> None:
        rear_excess: list[Tuple[float, StarSystem]] = []
        for system in owned:
            if system.id in front_lines:
                continue
            excess = system.ships - config.AI_REAR_GUARD_MAX
            if excess > 1.0:
                rear_excess.append((excess, system))

        if not rear_excess:
            return
        if not front_lines:
            return

        front_list = [self.galaxy.systems[fid] for fid in front_lines]
        rear_excess.sort(key=lambda x: x[0], reverse=True)

        dispatched = 0
        for excess, system in rear_excess:
            if dispatched >= config.AI_MAX_REAR_DISPATCHES:
                break
            target = min(front_list, key=lambda s: s.ships)
            send_pct = min(95, int(excess / max(1.0, system.ships) * 100) + 5)
            if self.galaxy.launch_fleet(system.id, target.id, send_pct):
                dispatched += 1

    def _update_blitz_posture(
        self,
        empire_id: int,
        own_power: float,
        enemy_powers: dict[int, float],
    ) -> None:
        dominant = [
            (power, eid)
            for eid, power in enemy_powers.items()
            if own_power >= config.AI_BLITZ_POWER_RATIO * max(1.0, power)
        ]
        if dominant:
            self.blitz_target[empire_id] = min(dominant)[1]
        else:
            self.blitz_target[empire_id] = None

    def _handle_expansion(
        self,
        empire_id: int,
        owned: List[StarSystem],
    ) -> int:
        options: list[Tuple[float, StarSystem, StarSystem]] = []
        for system in owned:
            if system.ships < config.AI_REAR_GUARD_MAX + config.AI_RESERVE_SHIPS:
                continue
            for nid in self.galaxy.neighbors[system.id]:
                node = self.galaxy.systems[nid]
                if node.owner_id is not None:
                    continue
                if self._on_cooldown(system.id, node.id):
                    continue
                score = node.production + config.AI_NEUTRAL_PRIORITY_BONUS + system.ships * 0.01
                options.append((score, system, node))

        if not options:
            return 0
        options.sort(key=lambda x: x[0], reverse=True)

        launched = 0
        for _, source, target in options:
            if launched >= config.AI_MAX_EXPANSIONS_PER_TICK:
                break
            if self.galaxy.launch_fleet(source.id, target.id, 70):
                self.attack_cooldowns[(source.id, target.id)] = config.AI_COOLDOWN
                launched += 1
        return launched

    def _handle_breakthrough_push(
        self,
        empire_id: int,
        owned: List[StarSystem],
        front_lines: set[int],
    ) -> None:
        target_enemy_id = self.breakthrough_focus.get(empire_id)
        if target_enemy_id is None:
            return

        attack_options: list[Tuple[float, StarSystem, StarSystem]] = []

        for system in owned:
            if system.id not in front_lines:
                continue
            for nid in self.galaxy.neighbors[system.id]:
                node = self.galaxy.systems[nid]
                if node.owner_id != target_enemy_id:
                    continue
                if self._on_cooldown(system.id, node.id):
                    continue
                advantage = self._calculate_attack_advantage(system, node)
                if advantage > 0:
                    attack_options.append((advantage + node.ships * 3.0, system, node))

        if not attack_options:
            return
        attack_options.sort(key=lambda x: x[0], reverse=True)

        for _, source, target in attack_options[:3]:
            available = source.ships - config.AI_FRONT_LINE_RESERVE
            if available <= 0:
                continue
            send_pct = min(85, max(50, int(available / max(1.0, source.ships) * 100)))
            if self.galaxy.launch_fleet(source.id, target.id, send_pct):
                self.attack_cooldowns[(source.id, target.id)] = config.AI_COOLDOWN / config.AI_BREAKTHROUGH_EXTRA_AGGRESSIVE

    def _handle_blitz(
        self,
        empire_id: int,
        owned: List[StarSystem],
    ) -> None:
        enemy_id = self.blitz_target.get(empire_id)
        if enemy_id is None:
            return

        options: list[Tuple[float, StarSystem, StarSystem]] = []
        for system in owned:
            for nid in self.galaxy.neighbors[system.id]:
                node = self.galaxy.systems[nid]
                if node.owner_id != enemy_id:
                    continue
                if self._on_cooldown(system.id, node.id):
                    continue
                options.append((node.ships, system, node))

        if not options:
            return
        options.sort(key=lambda x: x[0])

        waves_left = config.AI_BLITZ_WAVE_SIZE
        for _, source, target in options:
            if waves_left <= 0:
                break
            needed = target.ships * config.AI_BLITZ_LOCAL_RATIO + config.AI_FRONT_LINE_RESERVE
            if source.ships < needed:
                continue
            if self.galaxy.launch_fleet(source.id, target.id, 85):
                self.attack_cooldowns[(source.id, target.id)] = config.AI_BLITZ_COOLDOWN
                waves_left -= 1

    def _handle_skirmish(
        self,
        empire_id: int,
        owned: List[StarSystem],
        front_lines: set[int],
    ) -> None:
        if self.rng.random() < config.AI_BREAKTHROUGH_CONCENTRATION:
            surplus = self._count_total_surplus(empire_id, front_lines)
            if surplus >= config.AI_BREAKTHROUGH_MIN_SURPLUS:
                self._try_initiate_breakthrough(empire_id, front_lines)

        best: Tuple[float, StarSystem, StarSystem] | None = None
        for system in owned:
            if system.ships < config.AI_ATTACK_THRESHOLD + config.AI_FRONT_LINE_RESERVE:
                continue
            for enemy in self._get_enemy_neighbors(system, empire_id):
                if self._on_cooldown(system.id, enemy.id):
                    continue
                advantage = self._calculate_attack_advantage(system, enemy)
                if advantage <= 0:
                    continue
                score = advantage + enemy.production * 2.0
                if best is None or score > best[0]:
                    best = (score, system, enemy)

        if best is None:
            return
        _, source, target = best
        if self._should_execute_attack(source, target):
            self._execute_attack(source, target)
            self.attack_cooldowns[(source.id, target.id)] = config.AI_COOLDOWN

    def _handle_multi_front_defense(
        self,
        empire_id: int,
        owned: List[StarSystem],
        front_lines: set[int],
    ) -> None:
        frontier_threats: list[Tuple[float, StarSystem]] = []
        for system in owned:
            if system.id not in front_lines:
                continue
            threat = self._calculate_threat(system, empire_id)
            if threat > 0:
                frontier_threats.append((threat, system))

        frontier_threats.sort(key=lambda x: x[0], reverse=True)
        top_strongpoints = [system for threat, system in frontier_threats[:config.AI_DEFENSE_STRONGPOINTS]]

        for system in top_strongpoints:
            self._attempt_reinforcement(system, empire_id)

        staging = top_strongpoints[0] if top_strongpoints else None
        if not staging:
            return

        frontier_ids = {system.id for _, system in frontier_threats[:config.AI_DEFENSE_STRONGPOINTS]}
        dispatched = 0

        for system in owned:
            if dispatched >= config.AI_MAX_REAR_DISPATCHES:
                break
            if system.id in frontier_ids or system.id == staging.id:
                continue
            release_level = config.AI_REAR_GUARD_MAX * config.AI_REAR_RELEASE_MULTIPLIER
            if system.ships <= release_level:
                continue
            if self.galaxy.launch_fleet(system.id, staging.id, config.AI_REAR_SEND_PERCENT):
                dispatched += 1

    def _attempt_reinforcement(
        self,
        system: StarSystem,
        empire_id: int,
    ) -> None:
        friendly_neighbors = [
            self.galaxy.systems[nid]
            for nid in self.galaxy.neighbors[system.id]
            if self.galaxy.systems[nid].owner_id == empire_id
        ]
        donors = [s for s in friendly_neighbors if s.ships > config.AI_FRONT_LINE_RESERVE * 2]
        if not donors:
            return
        donor = max(donors, key=lambda s: s.ships - config.AI_FRONT_LINE_RESERVE)
        donate_fraction = max(25, int((donor.ships - config.AI_FRONT_LINE_RESERVE) / max(1.0, donor.ships) * 100))
        self.galaxy.launch_fleet(donor.id, system.id, donate_fraction)

    def _on_cooldown(self, source_id: int, target_id: int) -> bool:
        return self.attack_cooldowns.get((source_id, target_id), 0.0) > 0.0

    def _get_enemy_neighbors(
        self,
        system: StarSystem,
        empire_id: int,
    ) -> list[StarSystem]:
        return [
            self.galaxy.systems[nid]
            for nid in self.galaxy.neighbors[system.id]
            if self.galaxy.systems[nid].owner_id not in (empire_id, None)
        ]

    def _calculate_threat(self, system: StarSystem, empire_id: int) -> float:
        threat = 0.0
        for neighbor_id in self.galaxy.neighbors[system.id]:
            neighbor = self.galaxy.systems[neighbor_id]
            if neighbor.owner_id == empire_id or neighbor.owner_id is None:
                continue
            threat += neighbor.ships * 0.3 + neighbor.production * 2.0
        return threat

    def _calculate_attack_advantage(
        self,
        source: StarSystem,
        target: StarSystem,
    ) -> float:
        available = source.ships - config.AI_FRONT_LINE_RESERVE
        if available <= 0:
            return -1.0
        distance_factor = self._estimate_transit_damage(source, target)
        effective_strength = available * (1 - distance_factor * 0.3)
        return (effective_strength / max(1.0, target.ships)) - config.AI_MIN_ATTACK_RATIO

    def _estimate_transit_damage(
        self,
        source: StarSystem,
        target: StarSystem,
    ) -> float:
        if source.id in self.galaxy.neighbors[target.id]:
            return 0.0
        damage_estimate = 0.0
        path = self.galaxy.shortest_path(source.id, target.id)
        if path:
            for node_id in path[1:-1]:
                node = self.galaxy.systems[node_id]
                if node.owner_id not in (None, source.owner_id):
                    damage_estimate += 0.15
        return min(damage_estimate, 0.5)

    def _should_execute_attack(self, source: StarSystem, target: StarSystem) -> bool:
        available = source.ships - config.AI_FRONT_LINE_RESERVE
        if available < target.ships * config.AI_MIN_ATTACK_RATIO:
            return False
        return self.rng.random() < config.AI_BOLDNESS_FACTOR

    def _execute_attack(self, source: StarSystem, target: StarSystem) -> None:
        available = source.ships - config.AI_FRONT_LINE_RESERVE
        send_percent = self._calculate_attack_percentage(available, target)
        self.galaxy.launch_fleet(source.id, target.id, send_percent)

    def _calculate_attack_percentage(
        self,
        available_ships: float,
        target: StarSystem,
    ) -> int:
        ratio = available_ships / max(1.0, target.ships)
        if ratio >= 2.0:
            return 85
        elif ratio >= 1.5:
            return 75
        elif ratio >= 1.35:
            return 65
        else:
            return 50