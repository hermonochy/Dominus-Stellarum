import pygame

from . import config
from . import ui
from .ai import AIController
from .galaxy import Galaxy
from .galaxy_generation import active_empire_indices, load_galaxy
from .menu import MainMenu
from .player import PlayerController
from .renderer import Renderer
from .savegame import (
    load_game,
    next_save_path,
    restore_ai,
    restore_galaxy,
    restore_player,
    resolve_save_path,
    save_game,
)

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
        self.menu = MainMenu()
        self.in_menu = True
        self.galaxy = None
        self.active_layout = None
        self.player = None
        self.ai = None

        self.camera = {
            'zoom': 1.0,
            'offset_x': self.display_width // 2 - config.GALAXY_CENTER_X,
            'offset_y': self.display_height // 2 - config.GALAXY_CENTER_Y,
        }

        self.renderer = Renderer(self.screen, self.camera)
        self.renderer.popup.on_close = self._on_popup_closed
        self.running = True
        self.paused = False
        self._paused_before_popup = False
        self.speed_index = config.DEFAULT_SPEED_INDEX
        self.save_dialog_visible = False
        self.save_dialog_name = ""
        self.save_dialog_error = ""
        self.save_dialog_cursor = 0
        self.save_dialog_select_all = False
        self._save_dialog_overlay = None
        self._save_dialog_overlay_size = None
        self._save_dialog_fonts = {}

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
            dt = self.clock.tick(config.FPS) / 500.0
            dt = min(dt, 0.1)

            if self.in_menu:
                self._run_menu_frame()
                continue

            self._handle_events()
            self.player.update(dt, self.camera)

            if self._game_running():
                simulation_dt = dt * self.speed
                self.galaxy.update(simulation_dt, visual_dt=dt)
                self.ai.update(simulation_dt)
                self._drain_pending_messages()

            self.renderer.screen = self.screen
            self.renderer.draw(self.galaxy, self.player, self.paused, self.speed, self.camera, dt)
            if self.save_dialog_visible:
                self._draw_save_dialog()
            pygame.display.flip()

        pygame.quit()

    def _drain_pending_messages(self) -> None:
        if not self.galaxy.pending_messages:
            return
        message = self.galaxy.pending_messages.pop(0)
        if len(self.galaxy.pending_messages) < 2:
            self.player._set_message(message)
        self.galaxy.pending_messages.clear()

    def _run_menu_frame(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
                return
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                if self.menu.page != "main" and not (
                    self.menu.rename_dialog_visible or self.menu.confirm_delete_visible
                ):
                    self.menu.go_back()
                    continue
                if self.menu.page == "main":
                    self.running = False
                    return
            if event.type == pygame.VIDEORESIZE and not self.fullscreen:
                self.screen = pygame.display.set_mode((event.w, event.h), self.flags)
                continue
            self.menu.handle_event(event)

        if self.menu.load_requested:
            load_path = self.menu.load_path
            self.menu.load_requested = False
            self._load_game(load_path)
            return

        if self.menu.start_requested:
            self._start_game()
            return

        self.menu.draw()
        pygame.display.flip()

    def _start_game(self):
        try:
            layout = load_galaxy(self.menu.galaxy_file) if self.menu.galaxy_file is not None else None
            if layout is not None:
                layout.validate(playable=True, empire_indices=active_empire_indices(config.EMPIRE_COUNT, config.PLAYER_EMPIRE_INDEX))
            galaxy = Galaxy(layout=layout)
        except (OSError, ValueError) as exc:
            self.menu.start_requested = False
            self.menu.error_message = str(exc)
            return
        self.active_layout = layout
        self._new_game(galaxy)
        self.menu.reset()
        self.in_menu = False

    def _open_save_dialog(self):
        self.save_dialog_name = next_save_path().name
        self.save_dialog_cursor = len(self.save_dialog_name)
        self.save_dialog_select_all = True
        self.save_dialog_error = ""
        self.save_dialog_visible = True
        pygame.key.start_text_input()

    def _close_save_dialog(self):
        if self.save_dialog_visible:
            pygame.key.stop_text_input()
        self.save_dialog_visible = False
        self.save_dialog_error = ""

    def _save_game(self):
        try:
            destination_path = resolve_save_path(self.save_dialog_name)
            if destination_path.exists():
                raise ValueError("A save with that name already exists.")
            destination = save_game(
                self.galaxy,
                self.ai,
                self.player,
                self.camera,
                self.speed_index,
                self.paused,
                destination_path,
            )
        except (OSError, ValueError, TypeError) as exc:
            self.save_dialog_error = str(exc)
            return
        self._close_save_dialog()
        self.player._set_message(f"Game saved to {destination.name}.")

    def _load_game(self, path):
        try:
            snapshot = load_game(path)
            galaxy = restore_galaxy(snapshot)
            self.active_layout = galaxy.layout
            self._new_game(galaxy)
            restore_ai(self.ai, snapshot["ai"])
            restore_player(self.player, snapshot["player"])
            self.camera.update({key: float(value) for key, value in snapshot["camera"].items()})
            self.zoom = self.camera.get("zoom", 1.0)
            self.speed_index = max(0, min(len(config.SIM_SPEEDS) - 1, int(snapshot["app"]["speed_index"])))
            self.paused = bool(snapshot["app"]["paused"])
            self.in_menu = False
            self.menu.reset()
            self.menu.sync_settings()
            if not self.player.message:
                self.player._set_message("Game loaded.")
        except (OSError, ValueError, TypeError, KeyError, IndexError, OverflowError) as exc:
            message = f"Could not load save: {exc}"
            if self.in_menu:
                self.menu.error_message = message
            elif self.player is not None:
                self.player._set_message(message)

    def _open_menu(self):
        self.in_menu = True
        self.paused = False
        self.renderer.popup.close()
        self.menu.reset()

    def _game_running(self):
        if self.paused or self.save_dialog_visible:
            return False
        if self.renderer.popup.visible:
            return False
        winner = self.galaxy.winner()
        if winner is not None and winner.command_lockout <= 0.0:
            return False
        return True

    def _open_empire_popup(self, empire):
        self._paused_before_popup = self.paused
        self.paused = True
        self.renderer.popup.open(empire, self.galaxy)

    def _on_popup_closed(self):
        self.paused = self._paused_before_popup

    def _toggle_autopilot(self):
        if self.galaxy.player_succession_complete:
            return
        if not self.galaxy.command.can_order(config.PLAYER_ID):
            return
        self.galaxy.autopilot = not self.galaxy.autopilot
        if self.galaxy.autopilot:
            self.player.selected_system_id = None
            self.player.nuke_targeting = False
            self.player._set_message("Fleet orders delegated to AI. You still control your command ship with L.")
        else:
            self.player._set_message("Fleet control restored.")

    def _empire_row_click(self, pos):
        if pos[1] < self.screen.get_height() - int(ui.bottom_bar_height):
            return
        empire = self.renderer.empire_at(pos)
        if empire is not None:
            self._open_empire_popup(empire)

    def _handle_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
                continue

            if self.save_dialog_visible:
                self._handle_save_dialog_event(event)
                continue

            if event.type == pygame.KEYDOWN and event.mod & pygame.KMOD_CTRL:
                if event.key == pygame.K_s:
                    self._open_save_dialog()
                    continue

            if self.renderer.popup.visible:
                self.renderer.popup.handle_event(event)
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
                if event.button == 1:
                    self._empire_row_click(event.pos)
                elif event.button == pygame.BUTTON_MIDDLE:
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
                    if self.panning:
                        dx = event.pos[0] - self.pan_start_screen[0]
                        dy = event.pos[1] - self.pan_start_screen[1]
                        if dx * dx + dy * dy < 36:
                            self.player.toggle_gathering_point(
                                self.camera,
                                event.pos,
                            )
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

    def _save_dialog_layout(self):
        width = min(620, self.screen.get_width() - 48)
        height = 270
        panel = pygame.Rect(0, 0, width, height)
        panel.center = self.screen.get_rect().center
        field = pygame.Rect(panel.left + 34, panel.top + 112, panel.width - 68, 46)
        button_width = 170
        button_y = panel.bottom - 72
        save_button = pygame.Rect(panel.centerx - button_width - 10, button_y, button_width, 44)
        cancel_button = pygame.Rect(panel.centerx + 10, button_y, button_width, 44)
        return panel, field, save_button, cancel_button

    def _handle_save_dialog_event(self, event):
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                self._close_save_dialog()
            elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                self._save_game()
            elif event.key == pygame.K_BACKSPACE:
                if self.save_dialog_select_all:
                    self.save_dialog_name = ""
                    self.save_dialog_cursor = 0
                    self.save_dialog_select_all = False
                elif self.save_dialog_cursor > 0:
                    self.save_dialog_name = (
                        self.save_dialog_name[:self.save_dialog_cursor - 1]
                        + self.save_dialog_name[self.save_dialog_cursor:]
                    )
                    self.save_dialog_cursor -= 1
            elif event.key == pygame.K_DELETE:
                if self.save_dialog_select_all:
                    self.save_dialog_name = ""
                    self.save_dialog_cursor = 0
                    self.save_dialog_select_all = False
                elif self.save_dialog_cursor < len(self.save_dialog_name):
                    self.save_dialog_name = (
                        self.save_dialog_name[:self.save_dialog_cursor]
                        + self.save_dialog_name[self.save_dialog_cursor + 1:]
                    )
            elif event.key == pygame.K_a and event.mod & pygame.KMOD_CTRL:
                self.save_dialog_select_all = True
            elif event.key == pygame.K_LEFT:
                self.save_dialog_select_all = False
                self.save_dialog_cursor = max(0, self.save_dialog_cursor - 1)
            elif event.key == pygame.K_RIGHT:
                self.save_dialog_select_all = False
                self.save_dialog_cursor = min(len(self.save_dialog_name), self.save_dialog_cursor + 1)
            elif event.key == pygame.K_HOME:
                self.save_dialog_select_all = False
                self.save_dialog_cursor = 0
            elif event.key == pygame.K_END:
                self.save_dialog_select_all = False
                self.save_dialog_cursor = len(self.save_dialog_name)
            return

        if event.type == pygame.TEXTINPUT:
            if self.save_dialog_select_all:
                self.save_dialog_name = ""
                self.save_dialog_cursor = 0
                self.save_dialog_select_all = False
            insertion = event.text
            available = max(0, 72 - len(self.save_dialog_name))
            insertion = insertion[:available]
            self.save_dialog_name = (
                self.save_dialog_name[:self.save_dialog_cursor]
                + insertion
                + self.save_dialog_name[self.save_dialog_cursor:]
            )
            self.save_dialog_cursor += len(insertion)
            return

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            _, _, save_button, cancel_button = self._save_dialog_layout()
            if save_button.collidepoint(event.pos):
                self._save_game()
            elif cancel_button.collidepoint(event.pos):
                self._close_save_dialog()

    def _draw_save_dialog(self):
        screen = self.screen
        panel, field, save_button, cancel_button = self._save_dialog_layout()
        if self._save_dialog_overlay is None or self._save_dialog_overlay_size != screen.get_size():
            self._save_dialog_overlay = pygame.Surface(screen.get_size(), pygame.SRCALPHA)
            self._save_dialog_overlay.fill((0, 0, 0, 185))
            self._save_dialog_overlay_size = screen.get_size()
        screen.blit(self._save_dialog_overlay, (0, 0))

        pygame.draw.rect(screen, config.PANEL, panel, border_radius=16)
        pygame.draw.rect(screen, config.LANE_HIGHLIGHT, panel, 2, border_radius=16)

        scale = min(screen.get_width() / 1280, screen.get_height() / 800, 1.5)
        title_size = max(30, int(38 * scale))
        body_size = max(20, int(25 * scale))
        small_size = max(17, int(20 * scale))
        for size in (title_size, body_size, small_size):
            if size not in self._save_dialog_fonts:
                self._save_dialog_fonts[size] = pygame.font.Font(None, size)
        title_font = self._save_dialog_fonts[title_size]
        body_font = self._save_dialog_fonts[body_size]
        small_font = self._save_dialog_fonts[small_size]
        title = title_font.render("SAVE GALAXY", True, config.TEXT)
        screen.blit(title, title.get_rect(center=(panel.centerx, panel.top + 38)))
        prompt = small_font.render("Enter a name for this save file", True, config.MUTED_TEXT)
        screen.blit(prompt, prompt.get_rect(center=(panel.centerx, panel.top + 82)))

        pygame.draw.rect(screen, config.BACKGROUND, field, border_radius=7)
        pygame.draw.rect(screen, config.LANE_HIGHLIGHT, field, 2, border_radius=7)
        visible_name = self.save_dialog_name
        while body_font.size(visible_name)[0] > field.width - 28 and visible_name:
            visible_name = visible_name[1:]
        visible_cursor = max(0, self.save_dialog_cursor - (len(self.save_dialog_name) - len(visible_name)))
        if self.save_dialog_select_all and visible_name:
            selected_surface = body_font.render(visible_name, True, config.TEXT)
            selection_rect = pygame.Rect(field.left + 12, field.centery - selected_surface.get_height() // 2, selected_surface.get_width(), selected_surface.get_height())
            pygame.draw.rect(screen, config.LANE_COLOR, selection_rect)
        name_surface = body_font.render(visible_name, True, config.TEXT)
        screen.blit(name_surface, (field.left + 12, field.centery - name_surface.get_height() // 2))
        cursor_text = body_font.render(visible_name[:visible_cursor], True, config.TEXT)
        if not self.save_dialog_select_all and pygame.time.get_ticks() % 1000 < 550:
            cursor_x = min(field.right - 10, field.left + 12 + cursor_text.get_width() + 2)
            pygame.draw.line(screen, config.SELECTION_COLOR, (cursor_x, field.top + 10), (cursor_x, field.bottom - 10), 2)

        for rect, label, hovered in (
            (save_button, "SAVE", save_button.collidepoint(pygame.mouse.get_pos())),
            (cancel_button, "CANCEL", cancel_button.collidepoint(pygame.mouse.get_pos())),
        ):
            pygame.draw.rect(screen, config.PANEL_LIGHT if hovered else config.PANEL, rect, border_radius=8)
            pygame.draw.rect(screen, config.LANE_HIGHLIGHT if hovered else config.LANE_COLOR, rect, 2, border_radius=8)
            label_surface = body_font.render(label, True, config.TEXT)
            screen.blit(label_surface, label_surface.get_rect(center=rect.center))

        if self.save_dialog_error:
            error = small_font.render(self.save_dialog_error[:80], True, (240, 115, 115))
            screen.blit(error, error.get_rect(center=(panel.centerx, panel.bottom - 16)))

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
            self._open_menu()
            return True

        if key == pygame.K_f:
            self._toggle_fullscreen()
            return True

        if key == pygame.K_r:
            self._new_game()
            return True

        if key == pygame.K_a:
            self._toggle_autopilot()
            return True

        if key == pygame.K_SPACE:
            if self.galaxy.winner() is None:
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

        if key == pygame.K_l:
            self.player.toggle_command_mode()
            return True

        if key == pygame.K_n:
            if not self.galaxy.autopilot:
                self.player.toggle_nuke_mode()
            return True

        if key == pygame.K_LEFTBRACKET:
            self.player.adjust_escorts(-config.ESCORT_RECRUIT_STEP)
            return True

        if key == pygame.K_RIGHTBRACKET:
            self.player.adjust_escorts(config.ESCORT_RECRUIT_STEP)
            return True

        if self.galaxy.autopilot:
            return False

        if pygame.K_F1 <= key <= pygame.K_F10:
            self.player.use_percent = True
            self.player.send_percent = (key - pygame.K_F1 + 1) * 10
            return True

        if pygame.K_1 <= key <= pygame.K_9:
            self.player.use_percent = False
            self.player.send_count = key - pygame.K_1 + 1
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

    def _new_game(self, galaxy=None):
        self.renderer.popup.close()
        self.galaxy = galaxy if galaxy is not None else Galaxy(layout=self.active_layout)
        if self.player is None:
            self.player = PlayerController(self.galaxy)
        else:
            self.player.set_galaxy(self.galaxy)
        self.ai = AIController(self.galaxy)
        self.paused = False
        self.speed_index = config.DEFAULT_SPEED_INDEX
        self.camera['zoom'] = 1.0
        self.camera['offset_x'] = self.screen.get_width() // 2 - config.GALAXY_CENTER_X
        self.camera['offset_y'] = self.screen.get_height() // 2 - config.GALAXY_CENTER_Y
