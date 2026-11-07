from __future__ import annotations

from pathlib import Path

import pygame

from . import config
from .galaxy_generation import GALAXY_DIRECTORY, GalaxyLayout, SystemSpec, generate_random_galaxy, load_galaxy, resolve_empire_starts, save_galaxy


class GalaxyEditor:
    PANEL_WIDTH = 330

    def __init__(self, path: str | None = None):
        pygame.init()
        pygame.display.set_caption("Dominus Stellarum | Galaxy Editor")
        self.screen = pygame.display.set_mode((1360, 820), pygame.RESIZABLE)
        self.clock = pygame.time.Clock()
        self.running = True
        self.layout = GalaxyLayout()
        self.filename = "custom.galaxy"
        self.active_path: Path | None = None
        self.mode = "select"
        self.empire_index = 0
        self.generate_dialog = False
        self.generate_values = {"arms": str(config.GALAXY_ARM_COUNT), "systems": str(config.STAR_COUNT)}
        self.generate_focus = "systems"
        self.dialog_fields: dict[str, pygame.Rect] = {}
        self.dialog_buttons: dict[str, pygame.Rect] = {}
        self.selected_id: int | None = None
        self.lane_origin: int | None = None
        self.dragging: int | None = None
        self.panning = False
        self.pan_origin = (0, 0)
        self.offset_origin = (0.0, 0.0)
        self.zoom = 1.0
        self.offset_x = 0.0
        self.offset_y = 0.0
        self.focus: str | None = None
        self.name_input = ""
        self.production_input = ""
        self.message = "Add systems or generate a random galaxy to begin."
        self.is_error = False
        self.dirty = False
        self.buttons: list[tuple[pygame.Rect, str]] = []
        self.fields: dict[str, pygame.Rect] = {}
        self._preview_cache: tuple[bool, int, dict[int, int]] | None = None
        self._cached_names: dict[int, str] | None = None
        self.title_font = pygame.font.Font(None, 35)
        self.body_font = pygame.font.Font(None, 25)
        self.small_font = pygame.font.Font(None, 21)
        if path is not None:
            self.filename = Path(path).name
            self._load(Path(path))
        else:
            self._fit_view()

    @property
    def canvas(self) -> pygame.Rect:
        width, height = self.screen.get_size()
        return pygame.Rect(0, 58, max(1, width - self.PANEL_WIDTH), max(1, height - 98))

    @property
    def sidebar_x(self) -> int:
        return self.screen.get_width() - self.PANEL_WIDTH

    def _status(self, message: str, error: bool = False) -> None:
        self.message = message
        self.is_error = error

    def _mark_dirty(self) -> None:
        self.dirty = True
        self._preview_cache = None
        self._cached_names = None

    def _path(self) -> Path:
        name = Path(self.filename.strip()).name
        if not name or name in (".", ".."):
            raise ValueError("Enter a galaxy filename")
        if not name.lower().endswith(".galaxy"):
            name += ".galaxy"
        return GALAXY_DIRECTORY / name

    def _available(self) -> list[Path]:
        return sorted(GALAXY_DIRECTORY.glob("*.galaxy"), key=lambda path: path.name.lower())

    def _browse(self, direction: int) -> None:
        files = self._available()
        if not files:
            self._status("No saved galaxies found.", True)
            return
        names = [path.name for path in files]
        current = self.filename if self.filename in names else None
        index = (names.index(current) + direction) % len(names) if current is not None else (0 if direction > 0 else -1)
        self.filename = names[index]
        self.focus = None
        self._status(f"Selected {self.filename}. Choose LOAD to open it.")

    def _save(self) -> None:
        self._commit_production()
        try:
            destination = self._path()
            save_galaxy(self.layout, destination)
        except (OSError, ValueError) as exc:
            self._status(str(exc), True)
            return
        self.active_path = destination
        self.filename = destination.name
        self.dirty = False
        self._status(f"Saved {destination.name}; unassigned empire starts use automatic placement.")

    def _load(self, path: Path | None = None) -> None:
        try:
            source = self._path() if path is None else path
            layout = load_galaxy(source)
        except (OSError, ValueError) as exc:
            self._status(str(exc), True)
            return
        self.layout = layout
        self.active_path = source
        self.filename = source.name
        self.selected_id = None
        self.lane_origin = None
        self.focus = None
        self.dirty = False
        self._preview_cache = None
        self._cached_names = None
        self._fit_view()
        self._sync_fields()
        self._status(f"Loaded {source.name}: {len(layout.systems)} systems, {len(layout.edges)} lanes")

    def _generate(self, star_count: int, arm_count: int) -> None:
        self._commit_production()
        try:
            self.layout = generate_random_galaxy(star_count=star_count, arm_count=arm_count)
        except ValueError as exc:
            self._status(str(exc), True)
            return
        self.active_path = None
        self.selected_id = None
        self.lane_origin = None
        self.generate_dialog = False
        self._mark_dirty()
        self._sync_fields()
        self._fit_view()
        self._status(f"Generated {len(self.layout.systems)} systems across {arm_count} arms. You can now edit it.")

    def _new(self) -> None:
        self.layout = GalaxyLayout()
        self.selected_id = None
        self.lane_origin = None
        self.active_path = None
        self._mark_dirty()
        self._sync_fields()
        self._fit_view()
        self._status("Blank galaxy. Select ADD SYSTEM to place stars.")

    def _preview_starts(self) -> dict[int, int]:
        cached = self._preview_cache
        if cached is not None and cached[0] == self.dirty and cached[1] == self.empire_index:
            return cached[2]
        if not self.layout.systems:
            result = {}
        else:
            indices = list(sorted(self.layout.starts))
            if self.empire_index not in indices:
                indices.insert(0, self.empire_index)
            indices.extend(index for index in range(len(config.EMPIRES)) if index not in indices)
            indices = indices[:len(self.layout.systems)]
            result = resolve_empire_starts(self.layout, indices)
        self._preview_cache = (self.dirty, self.empire_index, result)
        return result

    def _resolved_names(self) -> dict[int, str]:
        if self._cached_names is None:
            self._cached_names = self.layout.resolved_names()
        return self._cached_names

    def _selected(self) -> SystemSpec | None:
        return next((system for system in self.layout.systems if system.id == self.selected_id), None)

    def _sync_fields(self) -> None:
        selected = self._selected()
        self.name_input = selected.name if selected is not None else ""
        self.production_input = "" if selected is None or selected.production is None else f"{selected.production:g}"

    def _commit_production(self) -> None:
        system = self._selected()
        if system is None:
            return
        try:
            value = float(self.production_input) if self.production_input.strip() else None
            if value is not None and (not 0 <= value < float("inf")):
                raise ValueError
        except ValueError:
            self._status("Production must be a nonnegative number, or blank for default.", True)
            self.production_input = "" if system.production is None else f"{system.production:g}"
            return
        if system.production != value:
            system.production = value
            self._mark_dirty()

    def _select(self, system_id: int | None) -> None:
        self._commit_production()
        self.selected_id = system_id
        self.focus = None
        self._sync_fields()

    def _delete_selected(self) -> None:
        if self.selected_id is None:
            return
        self.layout.remove_system(self.selected_id)
        self.selected_id = None
        self.lane_origin = None
        self._sync_fields()
        self._mark_dirty()
        self._status("System, connected lanes and assigned empire starts removed.")

    def _fit_view(self) -> None:
        rect = self.canvas
        if not self.layout.systems:
            self.zoom = 1.0
            self.offset_x = rect.centerx - config.GALAXY_CENTER_X
            self.offset_y = rect.centery - config.GALAXY_CENTER_Y
            return
        xs = [system.x for system in self.layout.systems]
        ys = [system.y for system in self.layout.systems]
        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)
        self.zoom = max(0.05, min(4.0, (rect.width - 100) / max(230, max_x - min_x), (rect.height - 100) / max(230, max_y - min_y)))
        self.offset_x = rect.centerx - (min_x + max_x) * 0.5 * self.zoom
        self.offset_y = rect.centery - (min_y + max_y) * 0.5 * self.zoom

    def _world(self, pos: tuple[int, int]) -> tuple[float, float]:
        return ((pos[0] - self.offset_x) / self.zoom, (pos[1] - self.offset_y) / self.zoom)

    def _screen(self, system: SystemSpec) -> tuple[int, int]:
        return (round(system.x * self.zoom + self.offset_x), round(system.y * self.zoom + self.offset_y))

    def _hit(self, pos: tuple[int, int]) -> SystemSpec | None:
        best = None
        best_distance = 13 * 13
        for system in self.layout.systems:
            px, py = self._screen(system)
            distance = (px - pos[0]) ** 2 + (py - pos[1]) ** 2
            if distance < best_distance:
                best = system
                best_distance = distance
        return best

    def _zoom_at(self, pos: tuple[int, int], factor: float) -> None:
        x, y = self._world(pos)
        self.zoom = max(0.04, min(10.0, self.zoom * factor))
        self.offset_x = pos[0] - x * self.zoom
        self.offset_y = pos[1] - y * self.zoom

    def _canvas_click(self, pos: tuple[int, int]) -> None:
        hit = self._hit(pos)
        if self.mode == "add":
            if hit is None:
                system = self.layout.add_system(*self._world(pos))
                self._mark_dirty()
                self._select(system.id)
                self._status(f"Added {self.layout.system_name(system)} (#{system.id}).")
            else:
                self._select(hit.id)
        elif self.mode == "select":
            self._select(hit.id if hit is not None else None)
            if hit is not None:
                self.dragging = hit.id
        elif self.mode == "lane":
            if hit is None:
                self.lane_origin = None
                return
            if self.lane_origin is None:
                self.lane_origin = hit.id
                self._select(hit.id)
                self._status("Now click another system to add or remove the hyperlane.")
            elif self.lane_origin != hit.id:
                try:
                    added = self.layout.toggle_lane(self.lane_origin, hit.id)
                except ValueError as exc:
                    self._status(str(exc), error=True)
                else:
                    self._mark_dirty()
                    self._status("Hyperlane added." if added else "Hyperlane removed.")
                self.lane_origin = None
            else:
                self.lane_origin = None
        elif self.mode == "start" and hit is not None:
            self._select(hit.id)
            self.layout.starts = {empire: sid for empire, sid in self.layout.starts.items() if sid != hit.id or empire == self.empire_index}
            self.layout.starts[self.empire_index] = hit.id
            self._mark_dirty()
            self._status(f"{config.EMPIRES[self.empire_index][0]} starts at {self.layout.system_name(hit)}.")
        elif self.mode == "delete" and hit is not None:
            self._select(hit.id)
            self._delete_selected()

    def _action(self, action: str) -> None:
        if action in ("select", "add", "lane", "start", "delete"):
            self._commit_production()
            self.focus = None
            self.mode = action
            self.lane_origin = None
        elif action == "save":
            self._save()
        elif action == "load":
            self._load()
        elif action == "random":
            self.generate_dialog = True
            self.generate_focus = "systems"
            self.is_error = False
        elif action == "new":
            self._new()
        elif action == "prev_file":
            self._browse(-1)
        elif action == "next_file":
            self._browse(1)
        elif action == "prev_empire":
            self.empire_index = (self.empire_index - 1) % len(config.EMPIRES)
        elif action == "next_empire":
            self.empire_index = (self.empire_index + 1) % len(config.EMPIRES)
        elif action == "clear_start":
            if self.empire_index in self.layout.starts:
                del self.layout.starts[self.empire_index]
                self._mark_dirty()
                self._status(f"{config.EMPIRES[self.empire_index][0]} will use an automatic start.")
        elif action == "remove":
            self._delete_selected()
        elif action == "fit":
            self._fit_view()

    def _handle_text(self, event: pygame.event.Event) -> None:
        if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
            self._commit_production()
            self.focus = None
            return
        if event.key == pygame.K_ESCAPE:
            self.focus = None
            self._sync_fields()
            return
        attr = {"filename": "filename", "name": "name_input", "production": "production_input"}[self.focus]
        text = getattr(self, attr)
        if event.key == pygame.K_BACKSPACE:
            text = text[:-1]
        elif event.unicode and event.unicode.isprintable() and len(text) < 90:
            text += event.unicode
        else:
            return
        setattr(self, attr, text)
        if self.focus == "name":
            system = self._selected()
            if system is not None:
                system.name = text
                self._mark_dirty()
        elif self.focus == "production":
            self._mark_dirty()

    def _handle_generate_dialog(self, event: pygame.event.Event) -> None:
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                self.generate_dialog = False
            elif event.key == pygame.K_TAB:
                self.generate_focus = "arms" if self.generate_focus == "systems" else "systems"
            elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                self._submit_generation()
            elif event.key == pygame.K_BACKSPACE:
                self.generate_values[self.generate_focus] = self.generate_values[self.generate_focus][:-1]
            elif event.unicode in "0123456789" and event.unicode:
                value = self.generate_values[self.generate_focus]
                if len(value) < 5:
                    self.generate_values[self.generate_focus] = value + event.unicode
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            for key, rect in self.dialog_fields.items():
                if rect.collidepoint(event.pos):
                    self.generate_focus = key
                    return
            for action, rect in self.dialog_buttons.items():
                if rect.collidepoint(event.pos):
                    if action == "generate":
                        self._submit_generation()
                    else:
                        self.generate_dialog = False
                    return

    def _submit_generation(self) -> None:
        try:
            arms = int(self.generate_values["arms"])
            systems = int(self.generate_values["systems"])
            if not 1 <= arms <= 24:
                raise ValueError("Arms must be between 1 and 24")
            if not 2 <= systems <= 1000:
                raise ValueError("Systems must be between 2 and 1000")
        except ValueError as exc:
            self._status(str(exc) if str(exc) and "invalid literal" not in str(exc) else "Enter a number for both arms and systems", True)
            return
        self._generate(systems, arms)

    def _draw_generate_dialog(self) -> None:
        shade = pygame.Surface(self.screen.get_size(), pygame.SRCALPHA)
        shade.fill((0, 0, 0, 190))
        self.screen.blit(shade, (0, 0))
        rect = pygame.Rect(0, 0, 480, 300)
        rect.center = self.screen.get_rect().center
        pygame.draw.rect(self.screen, config.PANEL_LIGHT, rect, border_radius=12)
        pygame.draw.rect(self.screen, config.LANE_HIGHLIGHT, rect, 2, border_radius=12)
        self._text("GENERATE RANDOM GALAXY", (rect.x + 30, rect.y + 24), config.TEXT, self.title_font)
        self._text("Uses the same generator as the game", (rect.x + 30, rect.y + 62), config.MUTED_TEXT, self.small_font)
        self.dialog_fields = {}
        for index, (key, label) in enumerate((("arms", "Spiral arms (1-24)"), ("systems", "Star systems (2-1000)"))):
            y = rect.y + 92 + index * 66
            self._text(label, (rect.x + 30, y), config.MUTED_TEXT, self.small_font)
            field_rect = pygame.Rect(rect.x + 275, y - 3, 160, 39)
            pygame.draw.rect(self.screen, config.BACKGROUND, field_rect, border_radius=5)
            pygame.draw.rect(self.screen, config.SELECTION_COLOR if self.generate_focus == key else config.LANE_COLOR, field_rect, 2, border_radius=5)
            self._text(self.generate_values[key] + ("|" if self.generate_focus == key else ""), (field_rect.x + 12, field_rect.y + 8))
            self.dialog_fields[key] = field_rect
        if self.is_error:
            self._text(self.message[:58], (rect.x + 30, rect.y + 215), (240, 115, 115), self.small_font)
        self.dialog_buttons = {
            "cancel": pygame.Rect(rect.x + 30, rect.bottom - 65, 190, 39),
            "generate": pygame.Rect(rect.right - 220, rect.bottom - 65, 190, 39),
        }
        for action, button in self.dialog_buttons.items():
            pygame.draw.rect(self.screen, (48, 68, 94) if action == "generate" else config.PANEL, button, border_radius=6)
            pygame.draw.rect(self.screen, config.LANE_HIGHLIGHT, button, 1, border_radius=6)
            label = self.body_font.render("GENERATE" if action == "generate" else "CANCEL", True, config.TEXT)
            self.screen.blit(label, label.get_rect(center=button.center))

    def _handle_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.QUIT:
            self.running = False
        elif event.type == pygame.VIDEORESIZE:
            self.screen = pygame.display.set_mode((max(900, event.w), max(620, event.h)), pygame.RESIZABLE)
        elif self.generate_dialog:
            self._handle_generate_dialog(event)
        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_s and event.mod & pygame.KMOD_CTRL:
                self._save()
            elif event.key == pygame.K_o and event.mod & pygame.KMOD_CTRL:
                self._load()
            elif self.focus is not None:
                self._handle_text(event)
            elif event.key == pygame.K_ESCAPE:
                self.lane_origin = None
                self._select(None)
            elif event.key == pygame.K_DELETE:
                self._delete_selected()
            elif event.key == pygame.K_f:
                self._fit_view()
            elif event.key in (pygame.K_1, pygame.K_2, pygame.K_3, pygame.K_4, pygame.K_5):
                self._action(("select", "add", "lane", "start", "delete")[event.key - pygame.K_1])
            elif event.key == pygame.K_TAB:
                self._action("next_empire")
        elif event.type == pygame.MOUSEWHEEL:
            pos = pygame.mouse.get_pos()
            if self.canvas.collidepoint(pos):
                self._zoom_at(pos, 1.15 ** event.y)
        elif event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == 2 or (event.button == 3 and self.canvas.collidepoint(event.pos)):
                self.panning = True
                self.pan_origin = event.pos
                self.offset_origin = (self.offset_x, self.offset_y)
            elif event.button == 1:
                for key, rect in self.fields.items():
                    if rect.collidepoint(event.pos):
                        self._commit_production()
                        self.focus = key if key == "filename" or self._selected() is not None else None
                        return
                for rect, action in self.buttons:
                    if rect.collidepoint(event.pos):
                        self._action(action)
                        return
                self._commit_production()
                self.focus = None
                if self.canvas.collidepoint(event.pos):
                    self._canvas_click(event.pos)
        elif event.type == pygame.MOUSEBUTTONUP:
            if event.button == 1:
                self.dragging = None
            if event.button in (2, 3):
                self.panning = False
        elif event.type == pygame.MOUSEMOTION:
            if self.panning:
                self.offset_x = self.offset_origin[0] + event.pos[0] - self.pan_origin[0]
                self.offset_y = self.offset_origin[1] + event.pos[1] - self.pan_origin[1]
            elif self.dragging is not None and self.canvas.collidepoint(event.pos):
                system = self._selected()
                if system is not None:
                    if self.layout.move_system(system.id, *self._world(event.pos)):
                        self._mark_dirty()
                    else:
                        self._status("Cannot move system: hyperlanes would overlap.", error=True)

    def _text(self, text: str, pos: tuple[int, int], color=None, font=None) -> None:
        surface = (font or self.body_font).render(text, True, color or config.TEXT)
        self.screen.blit(surface, pos)

    def _button(self, label: str, action: str, rect: pygame.Rect, active: bool = False) -> None:
        hovered = rect.collidepoint(pygame.mouse.get_pos())
        fill = (43, 65, 91) if active else (28, 39, 61) if hovered else config.PANEL
        pygame.draw.rect(self.screen, fill, rect, border_radius=6)
        pygame.draw.rect(self.screen, config.SELECTION_COLOR if active else config.LANE_COLOR, rect, 1, border_radius=6)
        text = self.small_font.render(label, True, config.TEXT)
        self.screen.blit(text, text.get_rect(center=rect.center))
        self.buttons.append((rect, action))

    def _field(self, key: str, label: str, value: str, x: int, y: int, width: int = 290) -> None:
        self._text(label, (x, y), config.MUTED_TEXT, self.small_font)
        rect = pygame.Rect(x, y + 21, width, 32)
        pygame.draw.rect(self.screen, (8, 13, 25), rect, border_radius=5)
        pygame.draw.rect(self.screen, config.SELECTION_COLOR if self.focus == key else config.LANE_COLOR, rect, 1, border_radius=5)
        font = self.body_font
        shown = value
        while shown and font.size(shown)[0] > width - 22:
            shown = shown[1:]
        self._text(shown + ("|" if self.focus == key else ""), (x + 10, y + 26), config.TEXT, font)
        self.fields[key] = rect

    def _draw_canvas(self) -> None:
        canvas = self.canvas
        self.screen.set_clip(canvas)
        pygame.draw.rect(self.screen, config.BACKGROUND, canvas)
        grid_spacing = 100 * self.zoom
        if grid_spacing > 20:
            origin_x = self.offset_x % grid_spacing
            origin_y = self.offset_y % grid_spacing
            for i in range(int(canvas.width / grid_spacing) + 3):
                x = int(origin_x + i * grid_spacing)
                pygame.draw.line(self.screen, (16, 23, 38), (x, canvas.top), (x, canvas.bottom))
            for i in range(int(canvas.height / grid_spacing) + 3):
                y = int(origin_y + i * grid_spacing)
                pygame.draw.line(self.screen, (16, 23, 38), (0, y), (canvas.right, y))
        positions = {system.id: self._screen(system) for system in self.layout.systems}
        names = self._resolved_names()
        starts_preview = self._preview_starts()
        lane_mode = self.mode == "lane"
        lane_color = (110, 175, 235) if lane_mode else config.LANE_COLOR
        lane_width = max(3, round(self.zoom * 5)) if lane_mode else max(1, round(self.zoom * 3))
        for a, b in self.layout.edges:
            pygame.draw.line(self.screen, lane_color, positions[a], positions[b], lane_width)
        if self.mode == "lane" and self.lane_origin in positions:
            pygame.draw.line(self.screen, config.SELECTION_COLOR, positions[self.lane_origin], pygame.mouse.get_pos(), 2)
        show_all_labels = self.zoom > 0.70
        for system in self.layout.systems:
            px, py = positions[system.id]
            if not canvas.inflate(30, 30).collidepoint((px, py)):
                continue
            starts = [eid for eid, sid in starts_preview.items() if sid == system.id]
            if starts:
                color = config.EMPIRES[starts[0]][1]
                if sum(color) < 130:
                    color = config.COMMAND_DARK_EMPIRE_MARKER_COLOR
                pygame.draw.circle(self.screen, color, (px, py), 11, 3 if starts[0] in self.layout.starts else 1)
            radius = max(3, min(7, int(5 * max(0.65, self.zoom))))
            pygame.draw.circle(self.screen, config.STAR_CORE_COLOR, (px, py), radius)
            if system.id == self.selected_id:
                pygame.draw.circle(self.screen, config.SELECTION_COLOR, (px, py), 15, 2)
            if show_all_labels or starts or system.id == self.selected_id:
                color = config.SELECTION_COLOR if system.id == self.selected_id else config.MUTED_TEXT
                self._text(names[system.id], (px + 11, py - 9), color, self.small_font)
        self.screen.set_clip(None)

    def _draw_sidebar(self) -> None:
        x = self.sidebar_x + 18
        self.buttons = []
        self.fields = {}
        pygame.draw.rect(self.screen, config.PANEL_LIGHT, (self.sidebar_x, 0, self.PANEL_WIDTH, self.screen.get_height()))
        self._text("GALAXY EDITOR", (x, 15), config.TEXT, self.title_font)
        self._field("filename", "File in galaxies/", self.filename, x, 55)
        self._button("SAVE", "save", pygame.Rect(x, 113, 141, 32))
        self._button("LOAD", "load", pygame.Rect(x + 149, 113, 141, 32))
        self._button("< FILE", "prev_file", pygame.Rect(x, 151, 141, 30))
        self._button("FILE >", "next_file", pygame.Rect(x + 149, 151, 141, 30))
        self._button("GENERATE RANDOM GALAXY", "random", pygame.Rect(x, 194, 290, 37))
        tool_names = [("1 SELECT", "select"), ("2 ADD STAR", "add"), ("3 HYPERLANE", "lane"), ("4 EMPIRE START", "start"), ("5 DELETE", "delete")]
        self._text("Tools", (x, 241), config.MUTED_TEXT, self.small_font)
        for index, (label, action) in enumerate(tool_names):
            row, col = divmod(index, 2)
            rect = pygame.Rect(x + col * 149, 265 + row * 36, 141, 31)
            self._button(label, action, rect, self.mode == action)
        self._text("Empire starting position", (x, 375), config.MUTED_TEXT, self.small_font)
        self._button("<", "prev_empire", pygame.Rect(x, 399, 31, 32))
        self._button(">", "next_empire", pygame.Rect(x + 259, 399, 31, 32))
        empire = self.empire_index
        color = config.EMPIRES[empire][1]
        self._text(f"{empire + 1}: {config.EMPIRES[empire][0]}", (x + 37, 407), color, self.small_font)
        self._text("Auto if unset", (x, 442), config.MUTED_TEXT, self.small_font)
        self._button("CLEAR START", "clear_start", pygame.Rect(x + 186, 436, 104, 28))
        preview = self._preview_starts()
        start_system = next((system for system in self.layout.systems if system.id == preview.get(empire)), None)
        start_label = f"Start: {self.layout.system_name(start_system)}" if start_system is not None else "Start: automatic"
        if empire not in self.layout.starts and start_system is not None:
            start_label += " (auto)"
        self._text(start_label[:35], (x, 468), config.MUTED_TEXT, self.small_font)
        selected = self._selected()
        label = f"SYSTEM {selected.id}" if selected is not None else "NO SYSTEM SELECTED"
        self._text(label, (x, 493), config.SELECTION_COLOR, self.body_font)
        self._field("name", "Name (blank = default)", self.name_input, x, 521)
        self._field("production", f"Production (blank = {config.PRODUCTION_MIN / 2 + config.PRODUCTION_MAX / 2:g})", self.production_input, x, 584)
        self._button("REMOVE SELECTED", "remove", pygame.Rect(x, 649, 141, 32))
        self._button("FIT GALAXY", "fit", pygame.Rect(x + 149, 649, 141, 32))
        self._button("NEW BLANK GALAXY", "new", pygame.Rect(x, 687, 290, 29))
        hints = ["Left click: use selected tool", "Select + drag: reposition a star", "Lane: click two stars to toggle", "Start: choose empire, click star", "Right/middle drag: pan   Wheel: zoom", "Ctrl+S: save   Ctrl+O: load   F: fit"]
        for i, hint in enumerate(hints):
            y = 722 + i * 19
            if y < self.screen.get_height() - 9:
                self._text(hint, (x, y), config.MUTED_TEXT, self.small_font)

    def _draw(self) -> None:
        self.screen.fill(config.BACKGROUND)
        self._draw_canvas()
        pygame.draw.rect(self.screen, config.PANEL, (0, 0, self.sidebar_x, 58))
        self._text("GALAXY MAP", (18, 14), config.TEXT, self.title_font)
        info = f"{len(self.layout.systems)} systems  |  {len(self.layout.edges)} hyperlanes  |  {len(self.layout.starts)} custom starts (others automatic)"
        self._text(info, (235, 24), config.MUTED_TEXT, self.small_font)
        pygame.draw.rect(self.screen, config.PANEL, (0, self.screen.get_height() - 40, self.sidebar_x, 40))
        message = ("UNSAVED  |  " if self.dirty else "") + self.message
        while self.small_font.size(message)[0] > self.sidebar_x - 35 and len(message) > 5:
            message = message[:-4] + "..."
        color = (240, 115, 115) if self.is_error else config.SELECTION_COLOR
        self._text(message, (16, self.screen.get_height() - 29), color, self.small_font)
        self._draw_sidebar()
        if self.generate_dialog:
            self._draw_generate_dialog()
        pygame.display.flip()

    def run(self) -> None:
        while self.running:
            self.clock.tick(config.FPS)
            for event in pygame.event.get():
                self._handle_event(event)
            self._draw()
        pygame.quit()


def main() -> None:
    import sys

    GalaxyEditor(sys.argv[1] if len(sys.argv) > 1 else None).run()


if __name__ == "__main__":
    main()
