import pygame

from . import config

class PopupButton:
    def __init__(self, label: str, action_id: str, enabled: bool = True):
        self.label = label
        self.action_id = action_id
        self.enabled = enabled
        self.rect = None

class EmpirePopup:
    def __init__(self):
        self.visible = False
        self.empire = None
        self.galaxy = None
        self.buttons = []
        self.on_close = None
        self.on_action = None
        self.panel_rect = None
        self.close_rect = None
        self.action_area = None
        self._cache = {}

    def open(self, empire, galaxy):
        self.visible = True
        self.empire = empire
        self.galaxy = galaxy
        self._cache = {}
        self._build_buttons()

    def close(self):
        if not self.visible:
            return
        self.visible = False
        self.empire = None
        self.galaxy = None
        self.buttons = []
        self.panel_rect = None
        self.close_rect = None
        self.action_area = None
        self._cache = {}
        if self.on_close is not None:
            self.on_close()

    def _build_buttons(self):
        self.buttons = []

    def _activate(self, button):
        if self.on_action is not None:
            self.on_action(button.action_id, self.empire)

    def handle_event(self, event):
        if not self.visible:
            return False
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                self.close()
            return True
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.panel_rect is None:
                return True
            if not self.panel_rect.collidepoint(event.pos):
                self.close()
                return True
            if self.close_rect is not None and self.close_rect.collidepoint(event.pos):
                self.close()
                return True
            for button in self.buttons:
                if button.enabled and button.rect is not None and button.rect.collidepoint(event.pos):
                    self._activate(button)
                    return True
            return True
        return True

    def _get_font(self, size):
        key = ("font", size)
        font = self._cache.get(key)
        if font is None:
            font = pygame.font.Font(None, size)
            self._cache[key] = font
        return font

    def _get_text(self, text, size, color):
        key = ("text", text, size, color)
        surface = self._cache.get(key)
        if surface is None:
            surface = self._get_font(size).render(text, True, color)
            self._cache[key] = surface
        return surface

    def _get_wrapped(self, text, size, max_width):
        key = ("wrap", text, size, max_width)
        lines = self._cache.get(key)
        if lines is None:
            font = self._get_font(size)
            lines = []
            current = ""
            for word in text.split(" "):
                candidate = word if not current else current + " " + word
                if font.size(candidate)[0] <= max_width:
                    current = candidate
                else:
                    if current:
                        lines.append(current)
                    current = word
            if current:
                lines.append(current)
            self._cache[key] = lines
        return lines

    def _get_overlay(self, sw, sh):
        key = ("overlay", sw, sh)
        overlay = self._cache.get(key)
        if overlay is None:
            overlay = pygame.Surface((sw, sh), pygame.SRCALPHA)
            overlay.fill((0, 0, 0, 165))
            self._cache[key] = overlay
        return overlay

    def draw(self, screen):
        if not self.visible or self.empire is None or self.galaxy is None:
            return

        sw = screen.get_width()
        sh = screen.get_height()
        empire = self.empire

        scale = min(sw / 1280, sh / 800, 1.5)
        panel_w = max(320, int(sw * config.POPUP_WIDTH_RATIO))
        panel_h = max(240, int(sh * config.POPUP_HEIGHT_RATIO))
        panel_rect = pygame.Rect(0, 0, panel_w, panel_h)
        panel_rect.center = (sw // 2, sh // 2)
        self.panel_rect = panel_rect

        screen.blit(self._get_overlay(sw, sh), (0, 0))
        pygame.draw.rect(screen, config.PANEL, panel_rect, border_radius=16)
        pygame.draw.rect(screen, config.LANE_HIGHLIGHT, panel_rect, 3, border_radius=16)

        pad = int(panel_w * 0.06)
        content_left = panel_rect.left + pad
        content_width = panel_w - pad * 2

        title_size = max(28, int(52 * scale))
        body_size = max(18, int(26 * scale))
        small_size = max(14, int(19 * scale))
        tiny_size = max(12, int(15 * scale))

        cursor_y = panel_rect.top + int(pad * 0.7)
        title = self._get_text(empire.name, title_size, empire.color)
        screen.blit(title, title.get_rect(center=(panel_rect.centerx, cursor_y + title.get_height() // 2)))
        cursor_y += title.get_height() + int(4 * scale)

        subtitle_parts = ["YOUR EMPIRE" if empire.is_player else "AI POWER"]
        if not empire.alive:
            subtitle_parts.append("ELIMINATED")
        subtitle = self._get_text("  |  ".join(subtitle_parts), small_size, config.MUTED_TEXT)
        screen.blit(subtitle, subtitle.get_rect(center=(panel_rect.centerx, cursor_y + subtitle.get_height() // 2)))
        cursor_y += subtitle.get_height() + int(12 * scale)

        pygame.draw.line(
            screen,
            config.LANE_COLOR,
            (content_left, cursor_y),
            (content_left + content_width, cursor_y),
            2,
        )
        cursor_y += int(16 * scale)

        systems = self.galaxy.empire_system_count(empire.id)
        ships = int(self.galaxy.empire_ship_count(empire.id))
        strength = int(self.galaxy.empire_strength(empire.id))
        stats_font = self._get_font(body_size)
        stats = stats_font.render(
            f"Systems: {systems}    Ships: {ships}    Strength: {strength:,}",
            True,
            config.TEXT,
        )
        screen.blit(stats, (content_left, cursor_y))
        cursor_y += stats.get_height() + int(14 * scale)

        heading = self._get_text("INTELLIGENCE REPORT", small_size, config.SELECTION_COLOR)
        screen.blit(heading, (content_left, cursor_y))
        cursor_y += heading.get_height() + int(6 * scale)

        lore = config.EMPIRE_LORE.get(empire.name, "No intelligence available on this power.")
        for line in self._get_wrapped(lore, body_size, content_width):
            surface = self._get_text(line, body_size, config.MUTED_TEXT)
            screen.blit(surface, (content_left, cursor_y))
            cursor_y += surface.get_height() + int(4 * scale)

        footer_y = panel_rect.bottom - int(pad * 0.5)
        hint = self._get_text("Click outside or press Esc to close", tiny_size, config.MUTED_TEXT)
        screen.blit(hint, hint.get_rect(center=(panel_rect.centerx, footer_y - hint.get_height() // 2)))

        action_bottom = footer_y - hint.get_height() - int(12 * scale)
        pygame.draw.line(
            screen,
            config.LANE_COLOR,
            (content_left, action_bottom),
            (content_left + content_width, action_bottom),
            2,
        )
        self.action_area = pygame.Rect(
            content_left,
            action_bottom + int(8 * scale),
            content_width,
            max(24, int(pad * 0.8)),
        )
        self._draw_buttons(screen)

        close_center = (panel_rect.right - pad, panel_rect.top + pad)
        close_r = max(12, int(13 * scale))
        pygame.draw.circle(screen, config.PANEL_LIGHT, close_center, close_r)
        pygame.draw.circle(screen, config.LANE_HIGHLIGHT, close_center, close_r, 2)
        d = int(close_r * 0.45)
        pygame.draw.line(screen, config.TEXT, (close_center[0] - d, close_center[1] - d), (close_center[0] + d, close_center[1] + d), 2)
        pygame.draw.line(screen, config.TEXT, (close_center[0] - d, close_center[1] + d), (close_center[0] + d, close_center[1] - d), 2)
        self.close_rect = pygame.Rect(0, 0, close_r * 2 + 8, close_r * 2 + 8)
        self.close_rect.center = close_center

    def _draw_buttons(self, screen):
        if not self.buttons or self.action_area is None:
            return

        sw = screen.get_width()
        sh = screen.get_height()
        scale = min(sw / 1280, sh / 800, 1.5)
        size = max(16, int(22 * scale))
        padding = max(8, int(12 * scale))
        gap = max(8, int(10 * scale))

        cursor_x = self.action_area.left
        for button in self.buttons:
            color = config.TEXT if button.enabled else config.MUTED_TEXT
            surface = self._get_text(button.label, size, color)
            rect = pygame.Rect(
                cursor_x,
                self.action_area.top,
                surface.get_width() + padding * 2,
                surface.get_height() + padding,
            )
            pygame.draw.rect(screen, config.PANEL_LIGHT, rect, border_radius=6)
            pygame.draw.rect(
                screen,
                config.LANE_HIGHLIGHT if button.enabled else config.LANE_COLOR,
                rect,
                2,
                border_radius=6,
            )
            screen.blit(
                surface,
                (rect.centerx - surface.get_width() // 2, rect.centery - surface.get_height() // 2),
            )
            button.rect = rect
            cursor_x += rect.width + gap