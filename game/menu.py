import pygame

from . import config

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
    ("text", "Press N to arm nuclear targeting, then right-click an enemy system to launch. The missile annihilates every ship and garrison within its blast radius and permanently scars production."),
    ("text", "Both launcher and victim suffer morale penalties, and empires worldwide observe launch cooldowns. Systems recently struck are briefly protected. Hidden nuclear depots scattered across the galaxy grant extra missiles when captured — including to you."),
    ("gap", ""),

    ("heading", "MORALE, REVOLTS AND BETRAYALS"),
    ("text", "Empire morale falls with heavy casualties and nuclear strikes, recovers in peacetime, and rises with every system you capture."),
    ("text", "When morale drops too low, unhappy systems start defecting: single worlds may betray to a neighbouring empire, and whole sectors can rise together as new independent rebel states. Keep your people loyal or watch your empire fracture."),
    ("gap", ""),

    ("heading", "INTERFACE"),
    ("text", "Hover a system to inspect its owner, garrison, production, gun range and hyperlanes. Click an empire in the bottom bar to open its dossier — from your own dossier you can delegate your empire to the AI autopilot."),
    ("text", "Drag the divider above the bottom bar to resize the empire rankings panel. Pan with middle-drag or the arrow keys, and zoom with the mouse wheel."),
    ("gap", ""),

    ("heading", "KEYBOARD AND MOUSE REFERENCE"),
    ("row", "Select one of your systems — Left mouse button"),
    ("row", "Send a fleet to a system — Right mouse button"),
    ("row", "Pan the view — Middle mouse button drag / Arrow keys"),
    ("row", "Toggle a gathering point — Middle mouse button click"),
    ("row", "Zoom in or out — Mouse wheel"),
    ("row", "Send 1 to 9 ships — Number keys 1 to 9"),
    ("row", "Send 10% to 100% of the garrison — F1 to F10"),
    ("row", "Toggle nuclear targeting — N"),
    ("row", "Pause or resume the simulation — Space"),
    ("row", "Increase or decrease simulation speed — + / -"),
    ("row", "Toggle fullscreen — F"),
    ("row", "Start a new game — R"),
    ("row", "Exit fullscreen or quit — Esc"),
]

class MainMenu:
    def __init__(self):
        self.settings = [
            _RangeSetting("Star systems", "STAR_COUNT", 100, 1000, 10),
            _RangeSetting("Empires", "EMPIRE_COUNT", 2, 10, 1),
            _RangeSetting("Starting ships", "STARTING_SHIPS", 10, 200, 5),
            _RangeSetting("Fleet speed", "FLEET_SPEED", 5, 40, 1),
            _EmpireSetting(),
            _DifficultySetting(),
        ]
        self.selected = 0
        self.start_requested = False
        self.page = "main"
        self.scroll = 0
        self._start_rect = None
        self._controls_rect = None
        self._back_rect = None
        self._arrow_rects = []

    def reset(self) -> None:
        self.start_requested = False
        self.page = "main"
        self.scroll = 0

    def go_back(self) -> None:
        self.page = "main"
        self.scroll = 0

    def handle_event(self, event: pygame.event.Event) -> None:
        if self.page == "controls":
            self._handle_controls_event(event)
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
            elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                self.start_requested = True

        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self._start_rect and self._start_rect.collidepoint(event.pos):
                self.start_requested = True
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
        top = int(sh * 0.34)
        row_height = 52
        return [
            pygame.Rect(left, top + i * row_height, band_width, row_height)
            for i in range(len(self.settings))
        ]

    def draw(self) -> None:
        screen = pygame.display.get_surface()
        screen.fill(config.BACKGROUND)
        if self.page == "controls":
            self._draw_controls_page(screen)
        else:
            self._draw_main_page(screen)
        pygame.display.flip()

    def _draw_main_page(self, screen: pygame.Surface) -> None:
        sw = screen.get_width()
        sh = screen.get_height()
        mouse = pygame.mouse.get_pos()

        scale = min(sw / 1280, sh / 800, 1.5)
        title_font = pygame.font.Font(None, int(72 * scale))
        label_font = pygame.font.Font(None, 36)
        small_font = pygame.font.Font(None, 26)

        title = title_font.render("DOMINUS STELLARUM", True, config.TEXT)
        screen.blit(title, title.get_rect(center=(sw // 2, int(sh * 0.15))))
        subtitle = small_font.render("GALACTIC CONQUEST SIMULATOR", True, config.MUTED_TEXT)
        screen.blit(subtitle, subtitle.get_rect(center=(sw // 2, int(sh * 0.21))))

        rows = self._row_rects()
        self._arrow_rects = []
        for index, (setting, rect) in enumerate(zip(self.settings, rows)):
            if rect.collidepoint(mouse):
                self.selected = index
            active = index == self.selected

            if active:
                pygame.draw.rect(screen, config.PANEL, rect, border_radius=8)
                pygame.draw.rect(screen, config.LANE_HIGHLIGHT, rect, 2, border_radius=8)

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

        self._start_rect = pygame.Rect(0, 0, 280, 54)
        self._start_rect.center = (sw // 2, int(sh * 0.80))
        start_hovered = self._start_rect.collidepoint(mouse)
        pygame.draw.rect(
            screen,
            config.PANEL_LIGHT if start_hovered else config.PANEL,
            self._start_rect,
            border_radius=10,
        )
        pygame.draw.rect(
            screen,
            config.LANE_HIGHLIGHT if start_hovered else config.LANE_COLOR,
            self._start_rect,
            2,
            border_radius=10,
        )
        start_surface = label_font.render("START GAME", True, config.TEXT)
        screen.blit(start_surface, start_surface.get_rect(center=self._start_rect.center))

        self._controls_rect = pygame.Rect(0, 0, 280, 46)
        self._controls_rect.center = (sw // 2, int(sh * 0.895))
        controls_hovered = self._controls_rect.collidepoint(mouse)
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

        hints = "Up/Down: choose   Left/Right: adjust   Enter: start   ESC: quit"
        hint_surface = small_font.render(hints, True, config.MUTED_TEXT)
        screen.blit(hint_surface, hint_surface.get_rect(midbottom=(sw // 2, sh - 24)))

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

        content_width = min(900, sw - 140)
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