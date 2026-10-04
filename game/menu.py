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

class MainMenu:
    def __init__(self):
        self.settings = [
            _RangeSetting("Star systems", "STAR_COUNT", 20, 400, 10),
            _RangeSetting("Empires", "EMPIRE_COUNT", 2, 8, 1),
            _RangeSetting("Starting ships", "STARTING_SHIPS", 10, 200, 5),
            _RangeSetting("Fleet speed", "FLEET_SPEED", 5, 40, 1),
            _DifficultySetting(),
        ]
        self.selected = 0
        self.start_requested = False
        self._start_rect = None
        self._arrow_rects = []

    def reset(self) -> None:
        self.start_requested = False

    def handle_event(self, event: pygame.event.Event) -> None:
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
            for rect, index, direction in self._arrow_rects:
                if rect.collidepoint(event.pos):
                    self.selected = index
                    self.settings[index].adjust(direction)
                    return
            for index, rect in enumerate(self._row_rects()):
                if rect.collidepoint(event.pos):
                    self.selected = index
                    return

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
            screen.blit(value_surface, value_surface.get_rect(midright=(rect.right - 120, rect.centery)))

            for direction, offset in ((-1, 100), (1, 56)):
                arrow_char = "<" if direction < 0 else ">"
                arrow_surface = label_font.render(arrow_char, True, config.TEXT if active else config.MUTED_TEXT)
                arrow_rect = arrow_surface.get_rect(midright=(rect.right - offset, rect.centery))
                hit_rect = pygame.Rect(arrow_rect.x - 12, arrow_rect.y - 12, arrow_rect.width + 24, arrow_rect.height + 24)
                screen.blit(arrow_surface, arrow_rect)
                self._arrow_rects.append((hit_rect, index, direction))

        self._start_rect = pygame.Rect(0, 0, 280, 58)
        self._start_rect.center = (sw // 2, int(sh * 0.82))
        hovered = self._start_rect.collidepoint(mouse)
        pygame.draw.rect(
            screen,
            config.PANEL_LIGHT if hovered else config.PANEL,
            self._start_rect,
            border_radius=10,
        )
        pygame.draw.rect(
            screen,
            config.LANE_HIGHLIGHT if hovered else config.LANE_COLOR,
            self._start_rect,
            2,
            border_radius=10,
        )
        start_surface = label_font.render("START GAME", True, config.TEXT)
        screen.blit(start_surface, start_surface.get_rect(center=self._start_rect.center))

        hints = "Up/Down: choose   Left/Right: adjust   Enter: start   ESC: quit"
        hint_surface = small_font.render(hints, True, config.MUTED_TEXT)
        screen.blit(hint_surface, hint_surface.get_rect(midbottom=(sw // 2, sh - 24)))