import math
import random
import pygame

from . import config
from .galaxy_generation import GALAXY_DIRECTORY
from .savegame import delete_save_file, list_save_files, rename_save_file

class _RangeSetting:
    def __init__(self, label: str, attr: str, minimum, maximum, step, fmt="{:g}"):
        self.label = label
        self.attr = attr
        self.minimum = minimum
        self.maximum = maximum
        self.step = step
        self.fmt = fmt

    def display(self) -> str:
        return self.fmt.format(getattr(config, self.attr))

    def adjust(self, direction: int) -> None:
        value = getattr(config, self.attr)
        value = value + direction * self.step
        value = max(self.minimum, min(self.maximum, value))
        setattr(config, self.attr, value)

class _GalaxySetting:
    label = "Galaxy map"

    def __init__(self):
        self.index = 0
        self.paths = []
        self.refresh()

    def refresh(self) -> None:
        previous = self.path
        self.paths = sorted(GALAXY_DIRECTORY.glob("*.galaxy"), key=lambda path: path.name.lower())
        self.index = self.paths.index(previous) + 1 if previous in self.paths else 0

    @property
    def path(self):
        if self.index == 0 or self.index - 1 >= len(self.paths):
            return None
        return self.paths[self.index - 1]

    def display(self) -> str:
        self.refresh_if_changed()
        return "Random galaxy" if self.path is None else self.path.stem[:22]

    def refresh_if_changed(self) -> None:
        paths = sorted(GALAXY_DIRECTORY.glob("*.galaxy"), key=lambda path: path.name.lower())
        if paths != self.paths:
            self.refresh()

    def adjust(self, direction: int) -> None:
        self.refresh_if_changed()
        self.index = (self.index + direction) % (len(self.paths) + 1)


class _DifficultySetting:
    label = "AI difficulty"

    def __init__(self):
        self.names = list(config.DIFFICULTY_PRESETS)
        self.index = config.DEFAULT_DIFFICULTY_INDEX

    def display(self) -> str:
        return self.names[self.index]

    def adjust(self, direction: int) -> None:
        self.index = (self.index + direction) % len(self.names)
        for key, value in config.DIFFICULTY_PRESETS[self.names[self.index]].items():
            setattr(config, key, value)

class _EmpireSetting:
    label = "Your empire"

    def __init__(self):
        self.index = config.DEFAULT_PLAYER_EMPIRE_INDEX

    def display(self) -> str:
        return config.EMPIRES[self.index][0]

    @property
    def color(self) -> tuple[int, int, int]:
        return config.EMPIRES[self.index][1]

    def adjust(self, direction: int) -> None:
        self.index = (self.index + direction) % len(config.EMPIRES)
        config.PLAYER_EMPIRE_INDEX = self.index

HELP_CONTENT = [
    ("heading", "THE OBJECTIVE"),
    ("text", "You begin with a single home system and a modest fleet. Systems under your control produce ships over time, and the more of the galaxy you hold, the greater your industrial capacity."),
    ("text", "Victory belongs to the last empire standing: control every system to win. The AI empires are playing for the same prize, and any one of them can take the galaxy from you."),
    ("gap", ""),

    ("heading", "COMMAND SHIP AND CAPITAL"),
    ("text", "Press L to select or deselect your command ship. While selected, right-click a friendly connected system to move it. The command ship cannot conquer planets and does not consume troop fleets."),
    ("text", "Your capital is the friendly planet where the command ship is docked. During transit, the capital travels with the ship. Command ships can be destroyed by incidental enemy fire while moving, nuclear blasts, or the capture of their current planet."),
    ("text", f"Losing a command ship blocks all new orders for {int(config.COMMAND_DISRUPTION_DURATION)} simulation seconds. An AI successor then takes command and establishes a new capital. Every empire follows the same rule."),
    ("text", "Delegating your empire to the AI gives it control of regular fleets and nuclear orders only. You remain in charge of your own command ship: press L and right-click a friendly world to move it, even while the AI general commands your troops."),
    ("gap", ""),

    ("heading", "ESCORTS"),
    ("text", "Press ] to transfer 25 ships from your capital's garrison into your escort screen, and [ to release them back. Escorts can only be adjusted while the command ship is docked."),
    ("text", "Escorts automatically guard the capital when docked and the flagship while travelling, returning fire at any attacker within range. The more escorts you keep, the smaller the chance that enemy fire reaches the flagship itself: a large escort screen makes it nearly untouchable, while a handful of escorts will fall quickly."),
    ("text", "Escorts are yours alone: the AI can never seize or redirect them. But beware — a huge escort screen concentrates value on one world, making your capital a prime target for enemy nuclear strikes."),
    ("gap", ""),

    ("heading", "FLEET ORDERS"),
    ("text", "Left-click one of your systems to select it; the hyperlanes leading to every reachable system light up."),
    ("text", "Right-click any system to send a fleet there. Sending to your own system reinforces it; sending to a neutral or enemy system attacks it."),
    ("text", "Number keys 1 to 9 send a fixed number of ships. Function keys F1 to F10 send a percentage of the selected system's garrison, from 10% to 100%."),
    ("text", "Fleets travel only along hyperlanes, so routes and chokepoints matter. Systems within gun range of hostile neighbours exchange fire automatically, and larger garrisons shoot farther."),
    ("gap", ""),

    ("heading", "GATHERING POINTS"),
    ("text", "Middle-click any system to toggle it as a gathering point, marked with an orange reticle. Middle-drag pans the camera; a middle-click without dragging toggles the point."),
    ("text", "Your systems automatically ship newly produced ships to gathering points, preferring points that are close, thinly defended, and reachable without crossing hostile space."),
    ("text", "Gathering points persist even if the system changes hands. Place one deep in enemy space to stage an invasion, or on a contested chokepoint to funnel reinforcements."),
    ("gap", ""),

    ("heading", "NUCLEAR WARFARE"),
    ("text", "Nuclear missiles launch from your capital only, so your command ship must be docked before you can arm a strike. Press N, then right-click an enemy system to launch. The missile annihilates every ship and garrison within its blast radius and permanently scars production."),
    ("text", "Both launcher and victim suffer morale penalties, and empires worldwide observe launch cooldowns. Systems recently struck are briefly protected. Hidden nuclear depots scattered across the galaxy grant extra missiles when captured — including to you."),
    ("gap", ""),

    ("heading", "MORALE, REVOLTS AND BETRAYALS"),
    ("text", "Empire morale falls with heavy casualties and nuclear strikes, recovers in peacetime, and rises with every system you capture."),
    ("text", "When morale drops too low, unhappy systems start defecting: single worlds may betray to a neighbouring empire, and whole sectors can rise together as new independent rebel states. Capitals are protected from both betrayals and revolts. Keep your people loyal or watch your empire fracture."),
    ("gap", ""),

    ("heading", "INTERFACE"),
    ("text", "Hover a system to inspect its owner, garrison, production, gun range and hyperlanes. Click an empire in the bottom bar to open its dossier."),
    ("text", "Drag the divider above the bottom bar to resize the empire rankings panel. Pan with middle-drag or the arrow keys, and zoom with the mouse wheel."),
    ("gap", ""),

    ("heading", "KEYBOARD AND MOUSE REFERENCE"),
    ("row", "Select one of your systems — Left mouse button"),
    ("row", "Send a fleet to a system — Right mouse button"),
    ("row", "Select/deselect command ship — L"),
    ("row", "Move command ship — L, then right-click friendly system"),
    ("row", "Move command ship on autopilot — L and right-click"),
    ("row", "Recruit 25 escorts — ]"),
    ("row", "Release 25 escorts — ["),
    ("row", "Pan the view — Middle mouse button drag / Arrow keys"),
    ("row", "Toggle a gathering point — Middle mouse button click"),
    ("row", "Zoom in or out — Mouse wheel"),
    ("row", "Send 1 to 9 ships — Number keys 1 to 9"),
    ("row", "Send 10% to 100% of the garrison — F1 to F10"),
    ("row", "Toggle nuclear targeting — N"),
    ("row", "Pause or resume the simulation — Space"),
    ("row", "Increase or decrease simulation speed — + / -"),
    ("row", "Toggle fullscreen — F"),
    ("row", "Save the current game — Ctrl+S"),
    ("row", "Load a saved game — Main menu: Load Game"),
    ("row", "Rename a saved galaxy — Load Game: select a save, then R or Rename"),
    ("row", "Delete a saved galaxy — Load Game: select a save, then Delete; confirm to remove it"),
    ("row", "Start a new game — R"),
    ("row", "Exit fullscreen or quit — Esc"),
]

class MainMenu:
    def __init__(self):
        self.galaxy_setting = _GalaxySetting()
        self.empire_setting = _EmpireSetting()
        self.difficulty_setting = _DifficultySetting()
        self.settings = [
            self.galaxy_setting,
            _RangeSetting("Star systems", "STAR_COUNT", 100, 1000, 50),
            _RangeSetting("Empires", "EMPIRE_COUNT", 2, 10, 1),
            _RangeSetting("Starting ships", "STARTING_SHIPS", 10, 200, 5),
            _RangeSetting("Fleet speed", "FLEET_SPEED", 5, 40, 1),
            self.empire_setting,
            self.difficulty_setting,
        ]
        self.selected = 0
        self.start_requested = False
        self.error_message = ""
        self.status_message = ""
        self.page = "main"
        self.scroll = 0
        self._start_rect = None
        self._load_rect = None
        self._controls_rect = None
        self._back_rect = None
        self._load_selected_rect = None
        self._rename_selected_rect = None
        self._delete_selected_rect = None
        self._arrow_rects = []
        self._save_row_rects = []
        self._save_viewport = None
        self.save_files = []
        self.selected_save_index = 0
        self.load_requested = False
        self.load_path = None
        self.rename_dialog_visible = False
        self.rename_name = ""
        self.rename_cursor = 0
        self.rename_select_all = False
        self.rename_error = ""
        self.confirm_delete_visible = False
        self.pending_delete_path = None
        self._backdrop = None
        self._backdrop_size = None
        self._dialog_overlay = None
        self._dialog_overlay_size = None
        self._dialog_font_cache = {}

    @property
    def galaxy_file(self):
        self.galaxy_setting.refresh_if_changed()
        return self.galaxy_setting.path

    def reset(self) -> None:
        self._close_rename_dialog()
        self.confirm_delete_visible = False
        self.pending_delete_path = None
        self.start_requested = False
        self.load_requested = False
        self.load_path = None
        self.error_message = ""
        self.status_message = ""
        self.galaxy_setting.refresh()
        self.page = "main"
        self.scroll = 0

    def sync_settings(self) -> None:
        self.empire_setting.index = config.PLAYER_EMPIRE_INDEX
        for index, name in enumerate(self.difficulty_setting.names):
            preset = config.DIFFICULTY_PRESETS[name]
            if all(getattr(config, key) == value for key, value in preset.items()):
                self.difficulty_setting.index = index
                break

    def go_back(self) -> None:
        self._close_rename_dialog()
        self.confirm_delete_visible = False
        self.pending_delete_path = None
        self.page = "main"
        self.scroll = 0

    def open_saves(self) -> None:
        self.save_files = list_save_files()
        self.selected_save_index = min(self.selected_save_index, max(0, len(self.save_files) - 1))
        self.scroll = 0
        self._save_row_rects = []
        self._save_viewport = None
        self.error_message = ""
        self.status_message = ""
        self.page = "saves"

    def _request_selected_save(self) -> None:
        self.save_files = list_save_files()
        if not self.save_files:
            self.error_message = "No saved games found in the saves folder."
            return
        self.selected_save_index = max(0, min(self.selected_save_index, len(self.save_files) - 1))
        self.load_path = self.save_files[self.selected_save_index]
        self.load_requested = True

    def _selected_save_path(self):
        self.save_files = list_save_files()
        if not self.save_files:
            self.selected_save_index = 0
            self.error_message = "No saved games found in the saves folder."
            return None
        self.selected_save_index = max(0, min(self.selected_save_index, len(self.save_files) - 1))
        return self.save_files[self.selected_save_index]

    def _open_rename_dialog(self) -> None:
        path = self._selected_save_path()
        if path is None:
            return
        self.rename_name = path.name
        self.rename_cursor = len(self.rename_name)
        self.rename_select_all = True
        self.rename_error = ""
        self.rename_dialog_visible = True
        pygame.key.start_text_input()

    def _close_rename_dialog(self) -> None:
        if self.rename_dialog_visible:
            pygame.key.stop_text_input()
        self.rename_dialog_visible = False
        self.rename_error = ""

    def _rename_selected_save(self) -> None:
        path = self._selected_save_path()
        if path is None:
            self._close_rename_dialog()
            return
        try:
            renamed_path = rename_save_file(path, self.rename_name)
        except (OSError, ValueError) as exc:
            self.rename_error = str(exc)
            return
        self.save_files = list_save_files()
        self.selected_save_index = self.save_files.index(renamed_path)
        self._close_rename_dialog()
        self.error_message = ""
        self.status_message = f"Renamed to {renamed_path.name}."

    def _request_delete_selected_save(self) -> None:
        path = self._selected_save_path()
        if path is None:
            return
        self.pending_delete_path = path
        self.confirm_delete_visible = True

    def _confirm_delete_save(self) -> None:
        path = self.pending_delete_path
        if path is None:
            self.confirm_delete_visible = False
            return
        try:
            delete_save_file(path)
        except (OSError, ValueError) as exc:
            self.error_message = str(exc)
            self.status_message = ""
        else:
            self.error_message = ""
            self.status_message = f"Deleted {path.name}."
        self.confirm_delete_visible = False
        self.pending_delete_path = None
        self.save_files = list_save_files()
        self.selected_save_index = min(self.selected_save_index, max(0, len(self.save_files) - 1))
        self._keep_selected_save_visible()

    def _rename_dialog_layout(self, screen: pygame.Surface):
        width = min(620, screen.get_width() - 48)
        panel = pygame.Rect(0, 0, width, 270)
        panel.center = screen.get_rect().center
        field = pygame.Rect(panel.left + 34, panel.top + 112, panel.width - 68, 46)
        button_width = 170
        button_y = panel.bottom - 72
        rename_button = pygame.Rect(panel.centerx - button_width - 10, button_y, button_width, 44)
        cancel_button = pygame.Rect(panel.centerx + 10, button_y, button_width, 44)
        return panel, field, rename_button, cancel_button

    def _delete_confirmation_layout(self, screen: pygame.Surface):
        width = min(620, screen.get_width() - 48)
        panel = pygame.Rect(0, 0, width, 230)
        panel.center = screen.get_rect().center
        button_width = 170
        button_y = panel.bottom - 66
        delete_button = pygame.Rect(panel.centerx - button_width - 10, button_y, button_width, 44)
        cancel_button = pygame.Rect(panel.centerx + 10, button_y, button_width, 44)
        return panel, delete_button, cancel_button

    def _handle_rename_dialog_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                self._close_rename_dialog()
            elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                self._rename_selected_save()
            elif event.key == pygame.K_BACKSPACE:
                if self.rename_select_all:
                    self.rename_name = ""
                    self.rename_cursor = 0
                    self.rename_select_all = False
                elif self.rename_cursor > 0:
                    self.rename_name = self.rename_name[:self.rename_cursor - 1] + self.rename_name[self.rename_cursor:]
                    self.rename_cursor -= 1
            elif event.key == pygame.K_DELETE:
                if self.rename_select_all:
                    self.rename_name = ""
                    self.rename_cursor = 0
                    self.rename_select_all = False
                elif self.rename_cursor < len(self.rename_name):
                    self.rename_name = self.rename_name[:self.rename_cursor] + self.rename_name[self.rename_cursor + 1:]
            elif event.key == pygame.K_a and event.mod & pygame.KMOD_CTRL:
                self.rename_select_all = True
            elif event.key == pygame.K_LEFT:
                self.rename_select_all = False
                self.rename_cursor = max(0, self.rename_cursor - 1)
            elif event.key == pygame.K_RIGHT:
                self.rename_select_all = False
                self.rename_cursor = min(len(self.rename_name), self.rename_cursor + 1)
            elif event.key == pygame.K_HOME:
                self.rename_select_all = False
                self.rename_cursor = 0
            elif event.key == pygame.K_END:
                self.rename_select_all = False
                self.rename_cursor = len(self.rename_name)
            return

        if event.type == pygame.TEXTINPUT:
            if self.rename_select_all:
                self.rename_name = ""
                self.rename_cursor = 0
                self.rename_select_all = False
            insertion = event.text[:max(0, 72 - len(self.rename_name))]
            self.rename_name = self.rename_name[:self.rename_cursor] + insertion + self.rename_name[self.rename_cursor:]
            self.rename_cursor += len(insertion)
            return

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            _, _, rename_button, cancel_button = self._rename_dialog_layout(pygame.display.get_surface())
            if rename_button.collidepoint(event.pos):
                self._rename_selected_save()
            elif cancel_button.collidepoint(event.pos):
                self._close_rename_dialog()

    def _handle_delete_confirmation_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_ESCAPE, pygame.K_n):
                self.confirm_delete_visible = False
                self.pending_delete_path = None
            elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_y):
                self._confirm_delete_save()
            return
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            _, delete_button, cancel_button = self._delete_confirmation_layout(pygame.display.get_surface())
            if delete_button.collidepoint(event.pos):
                self._confirm_delete_save()
            elif cancel_button.collidepoint(event.pos):
                self.confirm_delete_visible = False
                self.pending_delete_path = None

    def handle_event(self, event: pygame.event.Event) -> None:
        if self.page == "controls":
            self._handle_controls_event(event)
            return
        if self.page == "saves":
            self._handle_saves_event(event)
            return

        if event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_UP, pygame.K_w):
                self.selected = (self.selected - 1) % len(self.settings)
            elif event.key in (pygame.K_DOWN, pygame.K_s):
                self.selected = (self.selected + 1) % len(self.settings)
            elif event.key in (pygame.K_LEFT, pygame.K_a):
                self.settings[self.selected].adjust(-1)
            elif event.key in (pygame.K_RIGHT, pygame.K_d):
                self.settings[self.selected].adjust(1)
            elif event.key == pygame.K_l:
                self.open_saves()
            elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                self.start_requested = True

        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self._start_rect and self._start_rect.collidepoint(event.pos):
                self.start_requested = True
                return
            if self._load_rect and self._load_rect.collidepoint(event.pos):
                self.open_saves()
                return
            if self._controls_rect and self._controls_rect.collidepoint(event.pos):
                self.page = "controls"
                self.scroll = 0
                return
            for rect, index, direction in self._arrow_rects:
                if rect.collidepoint(event.pos):
                    self.selected = index
                    self.settings[index].adjust(direction)
                    return
            for index, rect in enumerate(self._row_rects()):
                if rect.collidepoint(event.pos):
                    self.selected = index
                    return

    def _handle_saves_event(self, event: pygame.event.Event) -> None:
        if self.rename_dialog_visible:
            self._handle_rename_dialog_event(event)
            return
        if self.confirm_delete_visible:
            self._handle_delete_confirmation_event(event)
            return

        if event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_ESCAPE, pygame.K_BACKSPACE, pygame.K_b):
                self.go_back()
            elif event.key in (pygame.K_UP, pygame.K_w):
                if self.save_files:
                    self.selected_save_index = (self.selected_save_index - 1) % len(self.save_files)
                    self._keep_selected_save_visible()
            elif event.key in (pygame.K_DOWN, pygame.K_s):
                if self.save_files:
                    self.selected_save_index = (self.selected_save_index + 1) % len(self.save_files)
                    self._keep_selected_save_visible()
            elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                self._request_selected_save()
            elif event.key == pygame.K_r:
                self._open_rename_dialog()
            elif event.key == pygame.K_DELETE:
                self._request_delete_selected_save()

        elif event.type == pygame.MOUSEWHEEL:
            self.scroll = max(0, self.scroll - event.y * 58)

        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self._back_rect and self._back_rect.collidepoint(event.pos):
                self.go_back()
                return
            if self._load_selected_rect and self._load_selected_rect.collidepoint(event.pos):
                self._request_selected_save()
                return
            if self._rename_selected_rect and self._rename_selected_rect.collidepoint(event.pos):
                self._open_rename_dialog()
                return
            if self._delete_selected_rect and self._delete_selected_rect.collidepoint(event.pos):
                self._request_delete_selected_save()
                return
            if self._save_viewport is not None and not self._save_viewport.collidepoint(event.pos):
                return
            for index, rect in self._save_row_rects:
                if rect.collidepoint(event.pos):
                    self.selected_save_index = index
                    if getattr(event, "clicks", 1) >= 2:
                        self._request_selected_save()
                    return

    def _keep_selected_save_visible(self) -> None:
        if not self._save_row_rects:
            return
        row_height = 58
        selected_top = self.selected_save_index * row_height
        viewport_height = self._save_viewport.height if self._save_viewport is not None else row_height
        if selected_top < self.scroll:
            self.scroll = selected_top
        elif selected_top + row_height > self.scroll + viewport_height:
            self.scroll = selected_top + row_height - viewport_height

    def _handle_controls_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_ESCAPE, pygame.K_BACKSPACE, pygame.K_b):
                self.go_back()
            elif event.key in (pygame.K_UP, pygame.K_w):
                self.scroll -= 60
            elif event.key in (pygame.K_DOWN, pygame.K_s):
                self.scroll += 60
            elif event.key == pygame.K_PAGEUP:
                self.scroll -= 300
            elif event.key == pygame.K_PAGEDOWN:
                self.scroll += 300
            elif event.key == pygame.K_HOME:
                self.scroll = 0
            elif event.key == pygame.K_END:
                self.scroll += 100000

        elif event.type == pygame.MOUSEWHEEL:
            self.scroll -= event.y * 50

        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self._back_rect and self._back_rect.collidepoint(event.pos):
                self.go_back()

    def _row_rects(self) -> list[pygame.Rect]:
        screen = pygame.display.get_surface()
        sw = screen.get_width()
        sh = screen.get_height()
        band_width = min(640, sw - 80)
        left = sw // 2 - band_width // 2
        top = int(sh * 0.275)
        row_height = 48
        return [
            pygame.Rect(left, top + i * row_height, band_width, row_height)
            for i in range(len(self.settings))
        ]

    def draw(self) -> None:
        screen = pygame.display.get_surface()
        self._draw_backdrop(screen)
        if self.page == "controls":
            self._draw_controls_page(screen)
        elif self.page == "saves":
            self._draw_saves_page(screen)
            if self.rename_dialog_visible:
                self._draw_rename_dialog(screen)
            elif self.confirm_delete_visible:
                self._draw_delete_confirmation(screen)
        else:
            self._draw_main_page(screen)
        pygame.display.flip()

    def _draw_backdrop(self, screen: pygame.Surface) -> None:
        size = screen.get_size()
        if self._backdrop is None or self._backdrop_size != size:
            width, height = size
            surface = pygame.Surface(size).convert()
            surface.fill(config.BACKGROUND)
            rng = random.Random(41827)
            haze = pygame.Surface(size, pygame.SRCALPHA)
            for _ in range(15):
                center = (rng.randrange(width), rng.randrange(height))
                radius = rng.randint(max(45, min(size) // 12), max(70, min(size) // 4))
                tint = rng.choice(((35, 52, 100), (65, 38, 92), (24, 70, 92)))
                pygame.draw.circle(haze, (*tint, 9), center, radius)
            haze = pygame.transform.smoothscale(haze, (max(1, width // 3), max(1, height // 3)))
            surface.blit(pygame.transform.smoothscale(haze, size), (0, 0))
            stars = pygame.Surface(size, pygame.SRCALPHA)
            for _ in range(max(100, width * height // 8000)):
                x, y = rng.randrange(width), rng.randrange(height)
                radius = rng.choices((1, 2), (88, 12))[0]
                pygame.draw.circle(stars, (170, 195, 235, rng.randint(45, 145)), (x, y), radius)
            surface.blit(stars, (0, 0))
            self._backdrop = surface
            self._backdrop_size = size
        screen.blit(self._backdrop, (0, 0))

    def _draw_main_page(self, screen: pygame.Surface) -> None:
        sw = screen.get_width()
        sh = screen.get_height()
        mouse = pygame.mouse.get_pos()

        scale = min(sw / 1280, sh / 800, 1.5)
        title_font = pygame.font.Font(None, int(72 * scale))
        label_font = pygame.font.Font(None, 36)
        small_font = pygame.font.Font(None, 26)

        title = title_font.render("DOMINUS STELLARUM", True, config.TEXT)
        title_rect = title.get_rect(center=(sw // 2, int(sh * 0.15)))
        glow = title_font.render("DOMINUS STELLARUM", True, (90, 135, 205))
        screen.blit(glow, glow.get_rect(center=(sw // 2, title_rect.centery + 2)))
        screen.blit(title, title_rect)
        pygame.draw.line(screen, config.LANE_HIGHLIGHT, (sw // 2 - 150, int(sh * 0.185)), (sw // 2 + 150, int(sh * 0.185)), 2)
        subtitle = small_font.render("GALACTIC CONQUEST SIMULATOR", True, config.MUTED_TEXT)
        screen.blit(subtitle, subtitle.get_rect(center=(sw // 2, int(sh * 0.21))))

        rows = self._row_rects()
        self._arrow_rects = []
        for index, (setting, rect) in enumerate(zip(self.settings, rows)):
            if rect.collidepoint(mouse):
                self.selected = index
            active = index == self.selected

            pygame.draw.rect(screen, (10, 17, 31) if not active else config.PANEL, rect, border_radius=9)
            pygame.draw.rect(screen, config.LANE_HIGHLIGHT if active else config.LANE_COLOR, rect, 2 if active else 1, border_radius=9)
            if active:
                pygame.draw.rect(screen, (32, 48, 76), (rect.x + 2, rect.y + 2, 3, rect.height - 4), border_radius=2)

            label_surface = label_font.render(setting.label, True, config.TEXT if active else config.MUTED_TEXT)
            screen.blit(label_surface, label_surface.get_rect(midleft=(rect.x + 16, rect.centery)))

            value_surface = label_font.render(setting.display(), True, config.SELECTION_COLOR if active else config.TEXT)
            value_rect = value_surface.get_rect(midright=(rect.right - 120, rect.centery))
            screen.blit(value_surface, value_rect)

            if hasattr(setting, "color"):
                swatch_rect = pygame.Rect(value_rect.left - 34, rect.centery - 9, 20, 20)
                pygame.draw.rect(screen, setting.color, swatch_rect, border_radius=4)
                pygame.draw.rect(screen, config.LANE_HIGHLIGHT, swatch_rect, 2, border_radius=4)

            for direction, offset in ((-1, 100), (1, 56)):
                arrow_char = "<" if direction < 0 else ">"
                arrow_surface = label_font.render(arrow_char, True, config.TEXT if active else config.MUTED_TEXT)
                arrow_rect = arrow_surface.get_rect(midright=(rect.right - offset, rect.centery))
                hit_rect = pygame.Rect(arrow_rect.x - 12, arrow_rect.y - 12, arrow_rect.width + 24, arrow_rect.height + 24)
                screen.blit(arrow_surface, arrow_rect)
                self._arrow_rects.append((hit_rect, index, direction))

        button_width = min(250, (sw - 72) // 2)
        self._start_rect = pygame.Rect(0, 0, button_width, 54)
        self._start_rect.center = (sw // 2 - button_width // 2 - 10, int(sh * 0.78))
        self._load_rect = pygame.Rect(0, 0, button_width, 54)
        self._load_rect.center = (sw // 2 + button_width // 2 + 10, int(sh * 0.78))
        for rect, label in ((self._start_rect, "START GAME"), (self._load_rect, "LOAD GAME")):
            hovered = rect.collidepoint(mouse)
            pygame.draw.rect(screen, (0, 0, 0), rect.move(0, 4), border_radius=10)
            pygame.draw.rect(screen, config.PANEL_LIGHT if hovered else config.PANEL, rect, border_radius=10)
            pygame.draw.rect(screen, config.LANE_HIGHLIGHT if hovered else config.LANE_COLOR, rect, 2, border_radius=10)
            button_surface = label_font.render(label, True, config.TEXT)
            screen.blit(button_surface, button_surface.get_rect(center=rect.center))

        self._controls_rect = pygame.Rect(0, 0, 280, 46)
        self._controls_rect.center = (sw // 2, int(sh * 0.885))
        controls_hovered = self._controls_rect.collidepoint(mouse)
        pygame.draw.rect(screen, (0, 0, 0), self._controls_rect.move(0, 3), border_radius=10)
        pygame.draw.rect(
            screen,
            config.PANEL_LIGHT if controls_hovered else config.PANEL,
            self._controls_rect,
            border_radius=10,
        )
        pygame.draw.rect(
            screen,
            config.LANE_HIGHLIGHT if controls_hovered else config.LANE_COLOR,
            self._controls_rect,
            2,
            border_radius=10,
        )
        controls_surface = label_font.render("CONTROLS & HELP", True, config.TEXT)
        screen.blit(controls_surface, controls_surface.get_rect(center=self._controls_rect.center))

        if self.error_message:
            error = small_font.render(self.error_message[:100], True, (240, 115, 115))
            screen.blit(error, error.get_rect(center=(sw // 2, int(sh * 0.955))))
        elif self.galaxy_file is not None:
            note = small_font.render("Saved maps use their own stars; empire count is selected above", True, config.MUTED_TEXT)
            screen.blit(note, note.get_rect(center=(sw // 2, int(sh * 0.955))))

        hints = "Up/Down: choose   Left/Right: adjust   Enter: start   L: load game   ESC: quit"
        hint_surface = small_font.render(hints, True, config.MUTED_TEXT)
        screen.blit(hint_surface, hint_surface.get_rect(midbottom=(sw // 2, sh - 24)))

    def _draw_saves_page(self, screen: pygame.Surface) -> None:
        sw = screen.get_width()
        sh = screen.get_height()
        mouse = pygame.mouse.get_pos()
        scale = min(sw / 1280, sh / 800, 1.5)
        title_font = pygame.font.Font(None, max(34, int(56 * scale)))
        body_font = pygame.font.Font(None, max(18, int(27 * scale)))
        small_font = pygame.font.Font(None, max(14, int(19 * scale)))

        title = title_font.render("LOAD GAME", True, config.TEXT)
        screen.blit(title, title.get_rect(center=(sw // 2, int(sh * 0.12))))
        subtitle = small_font.render("SELECT A SAVED GALAXY TO RESUME", True, config.MUTED_TEXT)
        screen.blit(subtitle, subtitle.get_rect(center=(sw // 2, int(sh * 0.17))))

        if self.save_files:
            self.selected_save_index = max(0, min(self.selected_save_index, len(self.save_files) - 1))
        else:
            self.selected_save_index = 0

        viewport = pygame.Rect(0, int(sh * 0.23), min(780, sw - 80), int(sh * 0.53))
        viewport.centerx = sw // 2
        self._save_viewport = viewport
        row_height = 58
        total_height = len(self.save_files) * row_height
        max_scroll = max(0, total_height - viewport.height)
        self.scroll = max(0, min(self.scroll, max_scroll))
        screen.set_clip(viewport)
        self._save_row_rects = []
        first_index = self.scroll // row_height
        last_index = min(len(self.save_files), (self.scroll + viewport.height + row_height - 1) // row_height)
        for index in range(first_index, last_index):
            path = self.save_files[index]
            rect = pygame.Rect(viewport.left, viewport.top + index * row_height - self.scroll, viewport.width, row_height - 6)
            self._save_row_rects.append((index, rect))
            if not rect.colliderect(viewport):
                continue
            selected = index == self.selected_save_index
            hovered = rect.collidepoint(mouse)
            pygame.draw.rect(screen, config.PANEL_LIGHT if selected or hovered else config.PANEL, rect, border_radius=8)
            pygame.draw.rect(screen, config.LANE_HIGHLIGHT if selected else config.LANE_COLOR, rect, 2 if selected else 1, border_radius=8)
            label = body_font.render(path.name, True, config.TEXT if selected else config.MUTED_TEXT)
            screen.blit(label, label.get_rect(midleft=(rect.left + 20, rect.centery)))
        screen.set_clip(None)

        if not self.save_files:
            empty = body_font.render("No saved games found in the saves folder.", True, config.MUTED_TEXT)
            screen.blit(empty, empty.get_rect(center=viewport.center))

        button_y = int(sh * 0.84)
        button_band = min(920, sw - 64)
        button_gap = 12
        button_width = (button_band - button_gap * 3) // 4
        button_left = (sw - button_band) // 2
        actions = (
            ("load", "LOAD SELECTED", bool(self.save_files)),
            ("rename", "RENAME", bool(self.save_files)),
            ("delete", "DELETE", bool(self.save_files)),
            ("back", "BACK", True),
        )
        for index, (action, label, enabled) in enumerate(actions):
            rect = pygame.Rect(
                button_left + index * (button_width + button_gap),
                button_y - 24,
                button_width,
                48,
            )
            if action == "load":
                self._load_selected_rect = rect
            elif action == "rename":
                self._rename_selected_rect = rect
            elif action == "delete":
                self._delete_selected_rect = rect
            elif action == "back":
                self._back_rect = rect
            hovered = rect.collidepoint(mouse)
            pygame.draw.rect(screen, config.PANEL_LIGHT if hovered and enabled else config.PANEL, rect, border_radius=9)
            pygame.draw.rect(screen, config.LANE_HIGHLIGHT if hovered and enabled else config.LANE_COLOR, rect, 2, border_radius=9)
            text_surface = body_font.render(label, True, config.TEXT if enabled else config.MUTED_TEXT)
            screen.blit(text_surface, text_surface.get_rect(center=rect.center))

        if self.error_message:
            error = small_font.render(self.error_message[:100], True, (240, 115, 115))
            screen.blit(error, error.get_rect(center=(sw // 2, int(sh * 0.92))))
        elif self.status_message:
            status = small_font.render(self.status_message[:100], True, config.SELECTION_COLOR)
            screen.blit(status, status.get_rect(center=(sw // 2, int(sh * 0.92))))
        hints = "Up/Down: select   Enter: load   R: rename   Delete: delete   Double-click: load   Esc: back"
        hint_surface = small_font.render(hints, True, config.MUTED_TEXT)
        screen.blit(hint_surface, hint_surface.get_rect(midbottom=(sw // 2, sh - 12)))

    def _draw_rename_dialog(self, screen: pygame.Surface) -> None:
        panel, field, rename_button, cancel_button = self._rename_dialog_layout(screen)
        self._draw_dialog_backdrop(screen)
        pygame.draw.rect(screen, config.PANEL, panel, border_radius=16)
        pygame.draw.rect(screen, config.LANE_HIGHLIGHT, panel, 2, border_radius=16)
        title_font, body_font, small_font = self._dialog_fonts(screen)
        title = title_font.render("RENAME SAVED GALAXY", True, config.TEXT)
        screen.blit(title, title.get_rect(center=(panel.centerx, panel.top + 38)))
        prompt = small_font.render("Choose a new filename for this save", True, config.MUTED_TEXT)
        screen.blit(prompt, prompt.get_rect(center=(panel.centerx, panel.top + 82)))
        pygame.draw.rect(screen, config.BACKGROUND, field, border_radius=7)
        pygame.draw.rect(screen, config.LANE_HIGHLIGHT, field, 2, border_radius=7)
        visible_name = self.rename_name
        while body_font.size(visible_name)[0] > field.width - 28 and visible_name:
            visible_name = visible_name[1:]
        visible_cursor = max(0, self.rename_cursor - (len(self.rename_name) - len(visible_name)))
        if self.rename_select_all and visible_name:
            selected_surface = body_font.render(visible_name, True, config.TEXT)
            selection_rect = pygame.Rect(field.left + 12, field.centery - selected_surface.get_height() // 2, selected_surface.get_width(), selected_surface.get_height())
            pygame.draw.rect(screen, config.LANE_COLOR, selection_rect)
        name_surface = body_font.render(visible_name, True, config.TEXT)
        screen.blit(name_surface, (field.left + 12, field.centery - name_surface.get_height() // 2))
        cursor_text = body_font.render(visible_name[:visible_cursor], True, config.TEXT)
        if not self.rename_select_all and pygame.time.get_ticks() % 1000 < 550:
            cursor_x = min(field.right - 10, field.left + 12 + cursor_text.get_width() + 2)
            pygame.draw.line(screen, config.SELECTION_COLOR, (cursor_x, field.top + 10), (cursor_x, field.bottom - 10), 2)
        self._draw_dialog_button(screen, rename_button, "RENAME", body_font)
        self._draw_dialog_button(screen, cancel_button, "CANCEL", body_font)
        if self.rename_error:
            error = small_font.render(self.rename_error[:80], True, (240, 115, 115))
            screen.blit(error, error.get_rect(center=(panel.centerx, panel.bottom - 16)))

    def _draw_delete_confirmation(self, screen: pygame.Surface) -> None:
        panel, delete_button, cancel_button = self._delete_confirmation_layout(screen)
        self._draw_dialog_backdrop(screen)
        pygame.draw.rect(screen, config.PANEL, panel, border_radius=16)
        pygame.draw.rect(screen, config.LANE_HIGHLIGHT, panel, 2, border_radius=16)
        title_font, body_font, small_font = self._dialog_fonts(screen)
        title = title_font.render("DELETE SAVED GALAXY?", True, config.TEXT)
        screen.blit(title, title.get_rect(center=(panel.centerx, panel.top + 42)))
        filename = self.pending_delete_path.name if self.pending_delete_path is not None else ""
        prompt = body_font.render(filename[:52], True, config.SELECTION_COLOR)
        screen.blit(prompt, prompt.get_rect(center=(panel.centerx, panel.top + 94)))
        warning = small_font.render("This permanently deletes the save file.", True, config.MUTED_TEXT)
        screen.blit(warning, warning.get_rect(center=(panel.centerx, panel.top + 130)))
        self._draw_dialog_button(screen, delete_button, "DELETE", body_font)
        self._draw_dialog_button(screen, cancel_button, "CANCEL", body_font)

    def _dialog_fonts(self, screen: pygame.Surface):
        scale = min(screen.get_width() / 1280, screen.get_height() / 800, 1.5)
        sizes = (
            max(30, int(38 * scale)),
            max(20, int(25 * scale)),
            max(17, int(20 * scale)),
        )
        for size in sizes:
            if size not in self._dialog_font_cache:
                self._dialog_font_cache[size] = pygame.font.Font(None, size)
        title_font, body_font, small_font = (self._dialog_font_cache[size] for size in sizes)
        return title_font, body_font, small_font

    def _draw_dialog_backdrop(self, screen: pygame.Surface) -> None:
        if self._dialog_overlay is None or self._dialog_overlay_size != screen.get_size():
            self._dialog_overlay = pygame.Surface(screen.get_size(), pygame.SRCALPHA)
            self._dialog_overlay.fill((0, 0, 0, 185))
            self._dialog_overlay_size = screen.get_size()
        screen.blit(self._dialog_overlay, (0, 0))

    def _draw_dialog_button(self, screen: pygame.Surface, rect: pygame.Rect, label: str, font: pygame.font.Font) -> None:
        hovered = rect.collidepoint(pygame.mouse.get_pos())
        pygame.draw.rect(screen, config.PANEL_LIGHT if hovered else config.PANEL, rect, border_radius=8)
        pygame.draw.rect(screen, config.LANE_HIGHLIGHT if hovered else config.LANE_COLOR, rect, 2, border_radius=8)
        text_surface = font.render(label, True, config.TEXT)
        screen.blit(text_surface, text_surface.get_rect(center=rect.center))

    def _wrap_text(self, font: pygame.font.Font, text: str, max_width: int) -> list[str]:
        lines: list[str] = []
        current = ""
        for word in text.split(" "):
            candidate = word if not current else current + " " + word
            if font.size(candidate)[0] <= max_width or not current:
                current = candidate
            else:
                lines.append(current)
                current = word
        if current:
            lines.append(current)
        return lines

    def _build_help_layout(
        self,
        heading_font: pygame.font.Font,
        body_font: pygame.font.Font,
        content_width: int,
    ) -> list[tuple[str, object, int, int, int]]:
        layout: list[tuple[str, object, int, int, int]] = []
        for kind, text in HELP_CONTENT:
            if kind == "heading":
                surface = heading_font.render(text, True, config.SELECTION_COLOR)
                layout.append(("heading", surface, 16, surface.get_height(), 6))
            elif kind == "text":
                wrapped = self._wrap_text(body_font, text, content_width)
                for i, line in enumerate(wrapped):
                    surface = body_font.render(line, True, config.MUTED_TEXT)
                    layout.append(("text", surface, 12 if i == 0 else 3, surface.get_height(), 0))
            elif kind == "row":
                key, separator, action = text.partition(" — ")
                key_surface = body_font.render(key, True, config.TEXT)
                if separator:
                    action_surface = body_font.render(action, True, config.MUTED_TEXT)
                    payload = (key_surface, action_surface)
                else:
                    payload = (key_surface, None)
                height = key_surface.get_height()
                layout.append(("row", payload, 3, height, 0))
            else:
                layout.append(("gap", None, 6, 0, 6))
        return layout

    def _draw_controls_page(self, screen: pygame.Surface) -> None:
        sw = screen.get_width()
        sh = screen.get_height()
        mouse = pygame.mouse.get_pos()

        scale = min(sw / 1280, sh / 800, 1.5)
        title_font = pygame.font.Font(None, max(34, int(56 * scale)))
        heading_font = pygame.font.Font(None, max(22, int(32 * scale)))
        body_font = pygame.font.Font(None, max(17, int(25 * scale)))
        small_font = pygame.font.Font(None, max(14, int(19 * scale)))

        title = title_font.render("HOW TO PLAY", True, config.TEXT)
        screen.blit(title, title.get_rect(center=(sw // 2, int(sh * 0.085))))
        subtitle = small_font.render(
            "OBJECTIVES, CONTROLS AND FIELD MANUAL",
            True,
            config.MUTED_TEXT,
        )
        screen.blit(subtitle, subtitle.get_rect(center=(sw // 2, int(sh * 0.13))))

        content_width = min(config.HELP_CONTENT_WIDTH, sw - 140)
        left = sw // 2 - content_width // 2

        self._back_rect = pygame.Rect(0, 0, 220, 48)
        self._back_rect.center = (sw // 2, int(sh * 0.915))
        viewport_top = int(sh * 0.165)
        viewport_bottom = self._back_rect.top - 24
        viewport_height = viewport_bottom - viewport_top

        layout = self._build_help_layout(heading_font, body_font, content_width)
        total_height = sum(before + height + after for _, _, before, height, after in layout)

        max_scroll = max(0, total_height - viewport_height)
        self.scroll = max(0, min(self.scroll, max_scroll))

        viewport = pygame.Rect(left, viewport_top, content_width, viewport_height)
        pygame.draw.line(
            screen,
            config.LANE_COLOR,
            (left, viewport_top - 10),
            (left + content_width, viewport_top - 10),
            2,
        )

        screen.set_clip(viewport)
        cursor_y = viewport_top - self.scroll
        for kind, payload, before, height, after in layout:
            cursor_y += before
            if kind == "heading" or kind == "text":
                screen.blit(payload, (left, cursor_y))
            elif kind == "row":
                key_surface, action_surface = payload
                screen.blit(key_surface, (left, cursor_y))
                if action_surface is not None:
                    screen.blit(
                        action_surface,
                        (left + key_surface.get_width() + 24, cursor_y),
                    )
            cursor_y += height + after
        screen.set_clip(None)

        if max_scroll > 0:
            track_x = left + content_width + 10
            thumb_height = max(40, int(viewport_height * viewport_height / total_height))
            thumb_y = viewport_top + int(
                (viewport_height - thumb_height) * self.scroll / max_scroll
            )
            pygame.draw.rect(
                screen,
                config.LANE_COLOR,
                (track_x, viewport_top, 6, viewport_height),
                border_radius=3,
            )
            pygame.draw.rect(
                screen,
                config.LANE_HIGHLIGHT,
                (track_x, thumb_y, 6, thumb_height),
                border_radius=3,
            )

        back_hovered = self._back_rect.collidepoint(mouse)
        pygame.draw.rect(
            screen,
            config.PANEL_LIGHT if back_hovered else config.PANEL,
            self._back_rect,
            border_radius=10,
        )
        pygame.draw.rect(
            screen,
            config.LANE_HIGHLIGHT if back_hovered else config.LANE_COLOR,
            self._back_rect,
            2,
            border_radius=10,
        )
        back_surface = body_font.render("BACK", True, config.TEXT)
        screen.blit(back_surface, back_surface.get_rect(center=self._back_rect.center))

        hints = "Mouse wheel or Up/Down: scroll   Esc: back"
        hint_surface = small_font.render(hints, True, config.MUTED_TEXT)
        screen.blit(hint_surface, hint_surface.get_rect(midbottom=(sw // 2, sh - 16)))
