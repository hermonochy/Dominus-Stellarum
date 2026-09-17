import pygame

from . import config
from .ai import AIController
from .galaxy import Galaxy
from .player import PlayerController
from .renderer import Renderer


class GameApp:
    def __init__(self):
        pygame.init()

        pygame.display.set_caption(
            "Hyperlane Wars"
        )

        self.screen = (
            pygame.display.set_mode(
                (
                    config.WIDTH,
                    config.HEIGHT,
                )
            )
        )

        self.clock = pygame.time.Clock()

        self.galaxy = Galaxy()

        self.player = PlayerController(
            self.galaxy
        )

        self.ai = AIController(
            self.galaxy
        )

        self.renderer = Renderer(
            self.screen
        )

        self.running = True
        self.paused = False

        self.speed_index = (
            config.DEFAULT_SPEED_INDEX
        )

    @property
    def speed(self) -> float:
        return config.SIM_SPEEDS[
            self.speed_index
        ]

    def run(self) -> None:
        while self.running:
            dt = (
                self.clock.tick(
                    config.FPS
                )
                / 1000.0
            )

            dt = min(
                dt,
                0.1,
            )

            self._handle_events()

            self.player.update(dt)

            if self._game_running():
                simulation_dt = (
                    dt * self.speed
                )

                self.galaxy.update(
                    simulation_dt
                )

                self.ai.update(
                    simulation_dt
                )

            self.renderer.draw(
                self.galaxy,
                self.player,
                self.paused,
                self.speed,
            )

            pygame.display.flip()

        pygame.quit()

    def _game_running(
        self,
    ) -> bool:
        if self.paused:
            return False

        if self.galaxy.player_won():
            return False

        if self.galaxy.player_defeated():
            return False

        return True

    def _handle_events(
        self,
    ) -> None:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
                continue

            if event.type == pygame.KEYDOWN:
                if self._handle_key(
                    event.key
                ):
                    continue

            if self._game_running():
                self.player.handle_event(
                    event
                )

    def _handle_key(
        self,
        key: int,
    ) -> bool:
        if key == pygame.K_ESCAPE:
            self.running = False
            return True

        if key == pygame.K_r:
            self._new_game()
            return True

        if key == pygame.K_SPACE:
            if (
                not self.galaxy.player_won()
                and not self.galaxy.player_defeated()
            ):
                self.paused = (
                    not self.paused
                )

            return True

        if key in (
            pygame.K_EQUALS,
            pygame.K_PLUS,
            pygame.K_KP_PLUS,
        ):
            self._increase_speed()
            return True

        if key in (
            pygame.K_MINUS,
            pygame.K_KP_MINUS,
        ):
            self._decrease_speed()
            return True

        if key == pygame.K_1:
            self.player.send_percent = 25
            return True

        if key == pygame.K_2:
            self.player.send_percent = 50
            return True

        if key == pygame.K_3:
            self.player.send_percent = 75
            return True

        if key == pygame.K_4:
            self.player.send_percent = 100
            return True

        return False

    def _increase_speed(
        self,
    ) -> None:
        maximum = (
            len(config.SIM_SPEEDS)
            - 1
        )

        self.speed_index = min(
            maximum,
            self.speed_index + 1,
        )

    def _decrease_speed(
        self,
    ) -> None:
        self.speed_index = max(
            0,
            self.speed_index - 1,
        )

    def _new_game(
        self,
    ) -> None:
        self.galaxy = Galaxy()

        self.player.set_galaxy(
            self.galaxy
        )

        self.ai = AIController(
            self.galaxy
        )

        self.paused = False

        self.speed_index = (
            config.DEFAULT_SPEED_INDEX
        )