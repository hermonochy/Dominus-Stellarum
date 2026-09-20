# app.py
import pygame

from . import config
from .ai import AIController
from .galaxy import Galaxy
from .player import PlayerController
from .renderer import Renderer

class GameApp:
    def __init__(self):
        pygame.init()
        pygame.display.set_caption("Dominus Stellarum")

        self.fullscreen = True
        self.default_width = config.WIDTH
        self.default_height = config.HEIGHT
        
        display_info = pygame.display.Info()
        self.display_width = display_info.current_w
        self.display_height = display_info.current_h
        
        self.flags = pygame.FULLSCREEN | pygame.DOUBLEBUF
        self.screen = pygame.display.set_mode(
            (self.display_width, self.display_height),
            self.flags,
        )

        self.clock = pygame.time.Clock()
        self.galaxy = Galaxy()
        self.player = PlayerController(self.galaxy)
        self.ai = AIController(self.galaxy)

        self.camera = {
            'zoom': 1.0,
            'offset_x': self.display_width // 2 - config.GALAXY_CENTER_X,
            'offset_y': self.display_height // 2 - config.GALAXY_CENTER_Y,
        }

        self.renderer = Renderer(self.screen, self.camera)
        self.running = True
        self.paused = False
        self.speed_index = config.DEFAULT_SPEED_INDEX

        self.panning = False
        self.pan_start_screen = (0, 0)
        self.pan_start_offset = (0.0, 0.0)

    @property
    def speed(self):
        return config.SIM_SPEEDS[self.speed_index]

    @property
    def zoom(self):
        return self.camera['zoom']

    @zoom.setter
    def zoom(self, value):
        self.camera['zoom'] = max(
            config.CAMERA_ZOOM_MIN,
            min(config.CAMERA_ZOOM_MAX, value)
        )

    def run(self):
        while self.running:
            dt = self.clock.tick(config.FPS) / 1000.0
            dt = min(dt, 0.1)

            self._handle_events()
            self.player.update(dt, self.camera)

            if self._game_running():
                simulation_dt = dt * self.speed
                self.galaxy.update(simulation_dt)
                self.ai.update(simulation_dt)

            self.renderer.screen = self.screen
            self.renderer.draw(self.galaxy, self.player, self.paused, self.speed, self.camera)
            pygame.display.flip()

        pygame.quit()

    def _game_running(self):
        if self.paused:
            return False
        if self.galaxy.player_won():
            return False
        if self.galaxy.player_defeated():
            return False
        return True

    def _handle_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
                continue

            if event.type == pygame.VIDEORESIZE and not self.fullscreen:
                self.screen = pygame.display.set_mode((event.w, event.h), self.flags)
                self.camera['offset_x'] = event.w // 2 - config.GALAXY_CENTER_X * self.camera['zoom']
                self.camera['offset_y'] = event.h // 2 - config.GALAXY_CENTER_Y * self.camera['zoom']
                continue

            if event.type == pygame.KEYDOWN:
                if self._handle_key(event.key):
                    continue

            if event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == pygame.BUTTON_MIDDLE:
                    self.panning = True
                    self.pan_start_screen = pygame.mouse.get_pos()
                    self.pan_start_offset = (
                        self.camera['offset_x'],
                        self.camera['offset_y']
                    )
                elif event.button == 4:
                    self._zoom_at_cursor(event.pos, 1 + config.CAMERA_ZOOM_SENSITIVITY)
                elif event.button == 5:
                    self._zoom_at_cursor(event.pos, 1 / (1 + config.CAMERA_ZOOM_SENSITIVITY))

            elif event.type == pygame.MOUSEBUTTONUP:
                if event.button == pygame.BUTTON_MIDDLE:
                    self.panning = False

            elif event.type == pygame.MOUSEMOTION:
                if self.panning:
                    screen_delta = (
                        event.pos[0] - self.pan_start_screen[0],
                        event.pos[1] - self.pan_start_screen[1]
                    )
                    self.camera['offset_x'] = self.pan_start_offset[0] + screen_delta[0]
                    self.camera['offset_y'] = self.pan_start_offset[1] + screen_delta[1]

            if self._game_running():
                self.player.handle_event(event, self.camera)

    def _zoom_at_cursor(self, mouse_pos, zoom_factor):
        world_x = (mouse_pos[0] - self.camera['offset_x']) / self.camera['zoom']
        world_y = (mouse_pos[1] - self.camera['offset_y']) / self.camera['zoom']

        new_zoom = self.camera['zoom'] * zoom_factor
        new_zoom = max(
            config.CAMERA_ZOOM_MIN,
            min(config.CAMERA_ZOOM_MAX, new_zoom)
        )

        self.camera['offset_x'] = mouse_pos[0] - world_x * new_zoom
        self.camera['offset_y'] = mouse_pos[1] - world_y * new_zoom
        self.camera['zoom'] = new_zoom

    def _handle_key(self, key):
        if key == pygame.K_ESCAPE:
            if self.fullscreen:
                self._toggle_fullscreen()
            else:
                self.running = False
            return True

        if key == pygame.K_f:
            self._toggle_fullscreen()
            return True

        if key == pygame.K_r:
            self._new_game()
            return True

        if key == pygame.K_SPACE:
            if not self.galaxy.player_won() and not self.galaxy.player_defeated():
                self.paused = not self.paused
            return True

        if key in (pygame.K_EQUALS, pygame.K_PLUS, pygame.K_KP_PLUS):
            self._increase_speed()
            return True

        if key in (pygame.K_MINUS, pygame.K_KP_MINUS):
            self._decrease_speed()
            return True

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

    def _toggle_fullscreen(self):
        self.fullscreen = not self.fullscreen
        
        if self.fullscreen:
            display_info = pygame.display.Info()
            self.flags = pygame.FULLSCREEN | pygame.DOUBLEBUF
            self.screen = pygame.display.set_mode(
                (display_info.current_w, display_info.current_h),
                self.flags,
            )
            self.display_width = display_info.current_w
            self.display_height = display_info.current_h
        else:
            self.flags = pygame.RESIZABLE | pygame.DOUBLEBUF
            self.screen = pygame.display.set_mode(
                (self.default_width, self.default_height),
                self.flags,
            )

        self.camera['offset_x'] = self.screen.get_width() // 2 - config.GALAXY_CENTER_X * self.camera['zoom']
        self.camera['offset_y'] = self.screen.get_height() // 2 - config.GALAXY_CENTER_Y * self.camera['zoom']

    def _increase_speed(self):
        maximum = len(config.SIM_SPEEDS) - 1
        self.speed_index = min(maximum, self.speed_index + 1)

    def _decrease_speed(self):
        self.speed_index = max(0, self.speed_index - 1)

    def _new_game(self):
        self.galaxy = Galaxy()
        self.player.set_galaxy(self.galaxy)
        self.ai = AIController(self.galaxy)
        self.paused = False
        self.speed_index = config.DEFAULT_SPEED_INDEX
        self.camera['zoom'] = 1.0
        self.camera['offset_x'] = self.screen.get_width() // 2 - config.GALAXY_CENTER_X
        self.camera['offset_y'] = self.screen.get_height() // 2 - config.GALAXY_CENTER_Y