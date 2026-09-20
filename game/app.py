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
            "Dominus Stellarum"
        )

        # TRUE FULLSCREEN by default - no decorations
        self.fullscreen = True
        self.default_width = config.WIDTH
        self.default_height = config.HEIGHT
        self.flags = pygame.FULLSCREEN | pygame.DOUBLEBUF
        
        # Get actual display size for proper fullscreen
        display_info = pygame.display.Info()
        self.display_width = display_info.current_w
        self.display_height = display_info.current_h
        
        self.screen = pygame.display.set_mode(
            (self.display_width, self.display_height),
            self.flags,
        )

        self.clock = pygame.time.Clock()

        self.galaxy = Galaxy()

        self.player = PlayerController(
            self.galaxy
        )

        self.ai = AIController(
            self.galaxy
        )

        # Initialize camera - start centered
        self.camera = {
            'zoom': 1.0,
            'offset_x': self.display_width // 2 - config.GALAXY_CENTER_X,
            'offset_y': self.display_height // 2 - config.GALAXY_CENTER_Y,
        }

        # Now renderer can use self.camera
        self.renderer = Renderer(
            self.screen,
            self.camera
        )

        self.running = True
        self.paused = False

        self.speed_index = (
            config.DEFAULT_SPEED_INDEX
        )

        # Panning state
        self.panning = False
        self.pan_start_pos = (0, 0)
        self.pan_camera_start = {'offset_x': 0, 'offset_y': 0}

    @property
    def speed(self) -> float:
        return config.SIM_SPEEDS[
            self.speed_index
        ]

    @property
    def zoom(self) -> float:
        return self.camera['zoom']

    @zoom.setter
    def zoom(self, value: float) -> None:
        self.camera['zoom'] = max(
            config.CAMERA_ZOOM_MIN,
            min(config.CAMERA_ZOOM_MAX, value)
        )

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

            self.player.update(dt, self.camera)

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

            # Update renderer's reference to screen
            self.renderer.screen = self.screen

            self.renderer.draw(
                self.galaxy,
                self.player,
                self.paused,
                self.speed,
                self.camera,
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

            # Handle window resize if in windowed mode
            if event.type == pygame.VIDEORESIZE and not self.fullscreen:
                self.screen = pygame.display.set_mode(
                    (event.w, event.h),
                    self.flags,
                )
                # Recenter galaxy on resize
                self.camera['offset_x'] = event.w // 2 - config.GALAXY_CENTER_X
                self.camera['offset_y'] = event.h // 2 - config.GALAXY_CENTER_Y
                continue

            if event.type == pygame.KEYDOWN:
                if self._handle_key(
                    event.key
                ):
                    continue

            # Mouse events for camera control
            if event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == pygame.BUTTON_MIDDLE:
                    self.panning = True
                    self.pan_start_pos = pygame.mouse.get_pos()
                    self.pan_camera_start = self.camera.copy()
                elif event.button == 4:  # Scroll up - ZOOM ONLY
                    self.zoom *= (1 + config.CAMERA_ZOOM_SENSITIVITY)
                    # Keep zoom centered on galaxy center
                    self._recenter_zoom()
                elif event.button == 5:  # Scroll down - ZOOM ONLY
                    self.zoom /= (1 + config.CAMERA_ZOOM_SENSITIVITY)
                    # Keep zoom centered on galaxy center
                    self._recenter_zoom()

            elif event.type == pygame.MOUSEBUTTONUP:
                if event.button == pygame.BUTTON_MIDDLE:
                    self.panning = False

            elif event.type == pygame.MOUSEMOTION:
                if self.panning:
                    self._handle_pan(event.rel)

            if self._game_running():
                self.player.handle_event(
                    event,
                    self.camera
                )

    def _recenter_zoom(self) -> None:
        """Keep camera centered on galaxy when zooming."""
        if self.fullscreen:
            screen_width = self.display_width
            screen_height = self.display_height
        else:
            screen_width = self.screen.get_width()
            screen_height = self.screen.get_height()
        
        # Center on galaxy center point
        self.camera['offset_x'] = screen_width // 2 - config.GALAXY_CENTER_X * self.camera['zoom']
        self.camera['offset_y'] = screen_height // 2 - config.GALAXY_CENTER_Y * self.camera['zoom']

    def _handle_pan(self, delta: tuple[int, int]) -> None:
        """Pan the camera by mouse movement."""
        dx = delta[0] * config.CAMERA_PAN_SENSITIVITY
        dy = delta[1] * config.CAMERA_PAN_SENSITIVITY
        
        self.camera['offset_x'] = self.pan_camera_start['offset_x'] + dx
        self.camera['offset_y'] = self.pan_camera_start['offset_y'] + dy

    def _handle_key(
        self,
        key: int,
    ) -> bool:
        if key == pygame.K_ESCAPE:
            if self.fullscreen:
                # Exit fullscreen to windowed mode
                self._toggle_fullscreen()
                return True
            else:
                # Quit game
                self.running = False
                return True

        if key == pygame.K_f:
            # Toggle fullscreen
            self._toggle_fullscreen()
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

        # ALL ARROW KEYS ARE FOR PANNING
        if key == pygame.K_UP:
            self.camera['offset_y'] += 50
            return True

        if key == pygame.K_DOWN:
            self.camera['offset_y'] -= 50
            return True

        if key == pygame.K_LEFT:
            self.camera['offset_x'] += 50
            return True

        if key == pygame.K_RIGHT:
            self.camera['offset_x'] -= 50
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

    def _toggle_fullscreen(self) -> None:
        """Toggle between fullscreen and windowed mode."""
        self.fullscreen = not self.fullscreen
        
        if self.fullscreen:
            # Go to true fullscreen
            display_info = pygame.display.Info()
            self.flags = pygame.FULLSCREEN | pygame.DOUBLEBUF
            self.screen = pygame.display.set_mode(
                (display_info.current_w, display_info.current_h),
                self.flags,
            )
            self.display_width = display_info.current_w
            self.display_height = display_info.current_h
            self.camera['offset_x'] = self.display_width // 2 - config.GALAXY_CENTER_X * self.camera['zoom']
            self.camera['offset_y'] = self.display_height // 2 - config.GALAXY_CENTER_Y * self.camera['zoom']
        else:
            # Go to windowed mode
            self.flags = pygame.RESIZABLE | pygame.DOUBLEBUF
            self.screen = pygame.display.set_mode(
                (self.default_width, self.default_height),
                self.flags,
            )
            self.camera['offset_x'] = self.default_width // 2 - config.GALAXY_CENTER_X * self.camera['zoom']
            self.camera['offset_y'] = self.default_height // 2 - config.GALAXY_CENTER_Y * self.camera['zoom']

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
        
        # Reset camera to center
        if self.fullscreen:
            self.camera['zoom'] = 1.0
            self.camera['offset_x'] = self.display_width // 2 - config.GALAXY_CENTER_X
            self.camera['offset_y'] = self.display_height // 2 - config.GALAXY_CENTER_Y
        else:
            self.camera['zoom'] = 1.0
            self.camera['offset_x'] = self.default_width // 2 - config.GALAXY_CENTER_X
            self.camera['offset_y'] = self.default_height // 2 - config.GALAXY_CENTER_Y