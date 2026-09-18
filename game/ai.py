import random
from typing import List, Optional

from . import config
from .galaxy import Galaxy
from .models import StarSystem


class AIController:
    def __init__(self, galaxy: Galaxy):
        self.galaxy = galaxy
        self.rng = random.Random()
        self.think_timer = 0.0
        self.attack_cooldown: dict[int, float] = {}
        self.defensive_priorities: dict[int, float] = {}

    def update(self, dt: float) -> None:
        self.think_timer += dt
        
        if self.think_timer < config.AI_THINK_INTERVAL:
            return

        self.think_timer -= config.AI_THINK_INTERVAL

        for empire in self.galaxy.empires:
            if empire.is_player or not empire.alive:
                continue

            self._think_for_empire(empire.id)

    def _think_for_empire(self, empire_id: int) -> None:
        """Main AI decision loop with strategic phases."""
        owned_systems = self.galaxy.owned_systems(empire_id)
        
        if not owned_systems:
            return

        # Phase 1: Defense first - reinforce threatened frontiers
        self._handle_defense(empire_id, owned_systems)
        
        # Phase 2: Expansion - attack weak neighbors
        self._handle_expansion(empire_id, owned_systems)
        
        # Phase 3: Consolidation - strengthen rear areas
        self._handle_consolidation(empire_id, owned_systems)

    def _handle_defense(self, empire_id: int, owned_systems: List[StarSystem]) -> None:
        """Identify and reinforce frontier systems under threat."""
        frontier_systems = []
        
        for system in owned_systems:
            if self._is_frontier(system, empire_id):
                threat_level = self._calculate_threat(system, empire_id)
                frontier_systems.append((system, threat_level))

        # Sort by threat level (highest first)
        frontier_systems.sort(key=lambda x: x[1], reverse=True)
        
        # Reinforce most threatened systems
        for system, threat in frontier_systems[:3]:  # Top 3 threats
            self._attempt_reinforcement(system, empire_id, min(threat * 0.5, 0.7))

    def _handle_expansion(self, empire_id: int, owned_systems: List[StarSystem]) -> None:
        """Attack vulnerable enemy systems."""
        potential_targets = []
        
        for system in owned_systems:
            if system.ships < config.AI_ATTACK_THRESHOLD + config.AI_RESERVE_SHIPS:
                continue
                
            enemies = self._get_enemy_neighbors(system, empire_id)
            
            for enemy in enemies:
                # Calculate attack viability
                advantage = self._calculate_attack_advantage(system, enemy)
                
                if advantage > 0:
                    # Factor in production value
                    score = advantage + (enemy.production * 2.0)
                    
                    # Penalize recently attacked systems
                    cooldown = self.attack_cooldown.get((system.id, enemy.id), 0)
                    if cooldown > 0:
                        score *= 0.3
                    
                    potential_targets.append((system, enemy, score))

        # Attack highest-value targets
        if potential_targets:
            potential_targets.sort(key=lambda x: x[2], reverse=True)
            source, target, _ = potential_targets[0]
            
            if self._should_execute_attack(source, target):
                self._execute_attack(source, target, empire_id)
                self.attack_cooldown[(source.id, target.id)] = config.AI_COOLDOWN

    def _handle_consolidation(self, empire_id: int, owned_systems: List[StarSystem]) -> None:
        """Move ships from safe rear systems to productive centers."""
        if random.random() < config.AI_CONSOLIDATION_CHANCE:
            # Find low-production systems with excess ships
            rear_systems = [
                s for s in owned_systems
                if not self._is_frontier(s, empire_id)
                and s.ships > config.AI_RESERVE_SHIPS * 2
                and s.production < config.PRODUCTION_MIN + 0.3
            ]
            
            # Find high-production systems that could use reinforcement
            centers = [
                s for s in owned_systems
                if s.production > config.PRODUCTION_MAX - 0.3
                and s.ships < s.production * 10
            ]
            
            if rear_systems and centers:
                source = random.choice(rear_systems)
                target = min(centers, key=lambda s: s.ships)
                
                # Send small reinforcement
                self.galaxy.launch_fleet(
                    source.id,
                    target.id,
                    config.AI_RETROGRADE_PERCENT
                )

    def _get_enemy_neighbors(self, system: StarSystem, empire_id: int) -> List[StarSystem]:
        """Get neighboring systems not owned by this empire."""
        return [
            self.galaxy.systems[nid]
            for nid in self.galaxy.neighbors[system.id]
            if self.galaxy.systems[nid].owner_id != empire_id
        ]

    def _is_frontier(self, system: StarSystem, empire_id: int) -> bool:
        """Check if system borders enemy territory."""
        return any(
            self.galaxy.systems[nid].owner_id != empire_id
            for nid in self.galaxy.neighbors[system.id]
        )

    def _calculate_threat(self, system: StarSystem, empire_id: int) -> float:
        """Estimate threat level from enemy neighbors."""
        threat = 0.0
        
        for neighbor_id in self.galaxy.neighbors[system.id]:
            neighbor = self.galaxy.systems[neighbor_id]
            
            if neighbor.owner_id == empire_id or neighbor.owner_id is None:
                continue
            
            # Enemy ships directly threaten this system
            threat += neighbor.ships * 0.3
            
            # High production enemies are more dangerous
            threat += neighbor.production * 2.0
        
        return threat

    def _calculate_attack_advantage(self, source: StarSystem, target: StarSystem) -> float:
        """Calculate numerical advantage for a potential attack."""
        available_ships = source.ships - config.AI_RESERVE_SHIPS
        
        if available_ships <= 0:
            return -1.0
        
        # Need to win decisively
        required_ratio = config.AI_MIN_ATTACK_RATIO
        
        # Account for combat damage during transit
        distance_factor = self._estimate_transit_damage(source, target)
        
        effective_strength = available_ships * (1 - distance_factor * 0.3)
        
        return (effective_strength / max(1.0, target.ships)) - required_ratio

    def _estimate_transit_damage(self, source: StarSystem, target: StarSystem) -> float:
        """Estimate ship losses during transit based on enemy neighbors."""
        damage_estimate = 0.0
        
        # Check for hostile systems along the path
        if source.id in self.galaxy.neighbors[target.id]:
            # Direct neighbor - no transit
            return 0.0
        
        # Multi-hop journey - estimate exposure
        path = self.galaxy.shortest_path(source.id, target.id)
        if path:
            for node_id in path[1:-1]:  # Skip source and destination
                node = self.galaxy.systems[node_id]
                if node.owner_id not in (None, source.owner_id):
                    damage_estimate += 0.15
        
        return min(damage_estimate, 0.5)

    def _should_execute_attack(self, source: StarSystem, target: StarSystem) -> bool:
        """Final check before committing to attack."""
        available = source.ships - config.AI_RESERVE_SHIPS
        
        # Must have minimum advantage
        if available < target.ships * config.AI_MIN_ATTACK_RATIO:
            return False
        
        # Random chance for bold attacks
        if random.random() < config.AI_BOLDNESS_FACTOR:
            return True
        
        return False

    def _execute_attack(self, source: StarSystem, target: StarSystem, empire_id: int) -> None:
        """Launch an attack fleet."""
        available = source.ships - config.AI_RESERVE_SHIPS
        
        send_percent = self._calculate_attack_percentage(available, target)
        
        self.galaxy.launch_fleet(source.id, target.id, send_percent)

    def _calculate_attack_percentage(self, available_ships: float, target: StarSystem) -> int:
        """Determine how many ships to commit to attack."""
        target_strength = max(1.0, target.ships)
        ratio = available_ships / target_strength
        
        if ratio >= 2.0:
            return 85  # Overwhelming force
        elif ratio >= 1.5:
            return 75
        elif ratio >= 1.35:
            return 65  # Minimum viable attack
        else:
            return 50  # Risky attack

    def _attempt_reinforcement(self, system: StarSystem, empire_id: int, strength: float) -> None:
        """Try to find reinforcements for this system."""
        friendly_neighbors = [
            self.galaxy.systems[nid]
            for nid in self.galaxy.neighbors[system.id]
            if self.galaxy.systems[nid].owner_id == empire_id
        ]
        
        # Find weakest neighbor that can spare ships
        donors = [
            s for s in friendly_neighbors
            if s.ships > config.AI_RESERVE_SHIPS * 2
        ]
        
        if donors:
            donor = max(donors, key=lambda s: s.ships - config.AI_RESERVE_SHIPS)
            
            # Calculate reasonable donation amount
            donate_amount = (donor.ships - config.AI_RESERVE_SHIPS) * strength
            
            if donate_amount > config.AI_RESERVE_SHIPS:
                self.galaxy.launch_fleet(
                    donor.id,
                    system.id,
                    int((donate_amount / donor.ships) * 100)
                )

    def _try_reinforce_frontier(self, system: StarSystem, empire_id: int) -> None:
        """Fallback reinforcement logic."""
        if random.random() > config.AI_FRONTIER_REINFORCE_CHANCE:
            return
        
        friendly_neighbors = [
            self.galaxy.systems[nid]
            for nid in self.galaxy.neighbors[system.id]
            if self.galaxy.systems[nid].owner_id == empire_id
        ]
        
        frontier = [
            s for s in friendly_neighbors
            if self._is_frontier(s, empire_id)
        ]
        
        if not frontier:
            return
        
        target = min(frontier, key=lambda s: s.ships)
        
        available = system.ships - config.AI_RESERVE_SHIPS
        
        if target.ships < available:
            self.galaxy.launch_fleet(system.id, target.id, 35)