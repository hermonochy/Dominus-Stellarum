import random

from . import config
from .galaxy import Galaxy
from .models import StarSystem


class AIController:
    def __init__(
        self,
        galaxy: Galaxy,
    ):
        self.galaxy = galaxy

        self.rng = random.Random()

        self.timer = 0.0

    def update(
        self,
        dt: float,
    ) -> None:
        self.timer += dt

        if (
            self.timer
            < config.AI_THINK_INTERVAL
        ):
            return

        self.timer -= (
            config.AI_THINK_INTERVAL
        )

        for empire in self.galaxy.empires:
            if empire.is_player:
                continue

            if not empire.alive:
                continue

            self._update_empire(
                empire.id
            )

    def _update_empire(
        self,
        empire_id: int,
    ) -> None:
        systems = (
            self.galaxy.owned_systems(
                empire_id
            )
        )

        self.rng.shuffle(systems)

        for source in systems:
            if (
                source.ships
                < config.AI_ATTACK_THRESHOLD
            ):
                continue

            enemies = (
                self._enemy_neighbors(
                    source,
                    empire_id,
                )
            )

            if enemies:
                target = (
                    self._choose_attack_target(
                        enemies
                    )
                )

                if self._should_attack(
                    source,
                    target,
                ):
                    send_percent = (
                        self._attack_percentage(
                            source,
                            target,
                        )
                    )

                    self.galaxy.launch_fleet(
                        source.id,
                        target.id,
                        send_percent,
                    )

                continue

            if self.rng.random() < 0.15:
                self._reinforce_frontier(
                    source,
                    empire_id,
                )

    def _enemy_neighbors(
        self,
        source: StarSystem,
        empire_id: int,
    ) -> list[StarSystem]:
        return [
            system
            for system
            in self.galaxy.get_neighbors(
                source.id
            )
            if system.owner_id
            != empire_id
        ]

    def _choose_attack_target(
        self,
        targets: list[StarSystem],
    ) -> StarSystem:
        return min(
            targets,
            key=self._target_score,
        )

    def _target_score(
        self,
        target: StarSystem,
    ) -> float:
        score = target.ships

        score -= (
            target.production
            * 4.0
        )

        if target.owner_id is not None:
            score += 5.0

        return score

    def _should_attack(
        self,
        source: StarSystem,
        target: StarSystem,
    ) -> bool:
        if target.owner_id is None:
            required_ratio = 1.15
        else:
            required_ratio = 1.35

        ratio = (
            source.ships
            / max(
                1.0,
                target.ships,
            )
        )

        if ratio >= required_ratio:
            return True

        return (
            self.rng.random()
            < 0.06
        )

    def _attack_percentage(
        self,
        source: StarSystem,
        target: StarSystem,
    ) -> int:
        ratio = (
            target.ships
            / max(
                1.0,
                source.ships,
            )
        )

        if ratio < 0.25:
            return 40

        if ratio < 0.5:
            return 55

        if ratio < 0.75:
            return 70

        return 80

    def _reinforce_frontier(
        self,
        source: StarSystem,
        empire_id: int,
    ) -> None:
        friendly_neighbors = [
            system
            for system
            in self.galaxy.get_neighbors(
                source.id
            )
            if system.owner_id
            == empire_id
        ]

        frontier = [
            system
            for system
            in friendly_neighbors
            if self._is_frontier(
                system,
                empire_id,
            )
        ]

        if not frontier:
            return

        target = min(
            frontier,
            key=lambda system:
            system.ships,
        )

        if (
            target.ships
            >= source.ships
        ):
            return

        self.galaxy.launch_fleet(
            source.id,
            target.id,
            35,
        )

    def _is_frontier(
        self,
        system: StarSystem,
        empire_id: int,
    ) -> bool:
        return any(
            neighbor.owner_id
            != empire_id
            for neighbor
            in self.galaxy.get_neighbors(
                system.id
            )
        )