import math
import pygame

from . import config
from . import ui
from .combat import gun_range
from .galaxy import Galaxy
from .player import PlayerController

class Renderer:
    def __init__(self, screen, camera):
        self.screen = screen
        self.camera = camera
        self.base_width = 1280
        self.base_height = 800
        self._range_cache: dict[tuple[int, tuple[int, int, int]], pygame.Surface] = {}
        self._range_cache_zoom = camera['zoom']
        self._font_size = None
        self._ship_font_cache: dict[int, pygame.font.Font] = {}
        self._ship_label_cache: dict[tuple[int, str], pygame.Surface] = {}
        self._fleet_label_cache: dict[str, pygame.Surface] = {}
        self._recache_fonts()
        self._bottom_font_key = None
        self._empire_row_font = None
        self._empire_title_font = None
        self._selection_font_key = None
        self._selection_body_font = None

    def _recache_fonts(self):
        w = self.screen.get_width()
        h = self.screen.get_height()
        scale_x = w / self.base_width
        scale_y = h / self.base_height
        scale = min(scale_x, scale_y, 1.5)
        font_size = int(22 * scale), int(18 * scale), int(14 * scale), int(64 * scale)
        if font_size == self._font_size:
            return
        self._font_size = font_size
        self.font = pygame.font.Font(None, font_size[0])
        self.small_font = pygame.font.Font(None, font_size[1])
        self.tiny_font = pygame.font.Font(None, font_size[2])
        self.huge_font = pygame.font.Font(None, font_size[3])
        self._ship_font_cache.clear()
        self._ship_label_cache.clear()
        self._fleet_label_cache.clear()

    def world_to_screen(self, world_pos):
        return pygame.Vector2(
            world_pos.x * self.camera['zoom'] + self.camera['offset_x'],
            world_pos.y * self.camera['zoom'] + self.camera['offset_y'],
        )

    def screen_to_world(self, screen_pos):
        return pygame.Vector2(
            (screen_pos[0] - self.camera['offset_x']) / self.camera['zoom'],
            (screen_pos[1] - self.camera['offset_y']) / self.camera['zoom'],
        )

    def draw(self, galaxy, player, paused, speed, camera):
        self._recache_fonts()
        self.screen.fill(config.BACKGROUND)
        valid_targets = player.valid_target_ids()
        self._draw_hyperlanes(galaxy, player, camera, valid_targets)
        self._draw_gun_ranges(galaxy, camera)
        self._draw_fleets(galaxy, camera)
        self._draw_combat_shots(galaxy, camera)
        self._draw_systems(galaxy, player, camera, valid_targets)
        self._draw_top_bar(galaxy, player, paused, speed)
        self._draw_bottom_bar(galaxy, player)
        self._draw_camera_info(camera)
        self._draw_game_state(galaxy)

    def _fit_font(self, target_height: int, label: str) -> pygame.font.Font:
        size = max(9, target_height)
        font = pygame.font.Font(None, size)
        while size > 9 and font.size(label)[1] > target_height:
            size -= 1
            font = pygame.font.Font(None, size)
        return font

    def _get_range_surface(self, radius_i: int, color: tuple[int, int, int]) -> pygame.Surface:
        key = (radius_i, color)
        cached = self._range_cache.get(key)
        if cached is not None:
            return cached

        if len(self._range_cache) > 600:
            self._range_cache.clear()

        diameter = radius_i * 2 + 4
        surface = pygame.Surface((diameter, diameter), pygame.SRCALPHA)
        center = (radius_i + 2, radius_i + 2)

        fill_color = (*color, config.GUN_RANGE_FILL_ALPHA)
        pygame.draw.circle(surface, fill_color, center, radius_i)

        ring_color = (*color, config.GUN_RANGE_RING_ALPHA)
        ring_width = max(1, min(3, radius_i // 30 + 1))
        pygame.draw.circle(surface, ring_color, center, radius_i, ring_width)

        self._range_cache[key] = surface
        return surface

    def _draw_gun_ranges(self, galaxy, camera):
        if self._range_cache_zoom != camera['zoom']:
            self._range_cache.clear()
            self._range_cache_zoom = camera['zoom']

        zoom = camera['zoom']
        offset_x = camera['offset_x']
        offset_y = camera['offset_y']
        sw = self.screen.get_width()
        sh = self.screen.get_height()
        margin = 260 * zoom

        entities = [
            (system.pos, system.owner_id, gun_range(system))
            for system in galaxy.systems
            if system.owner_id is not None
        ]
        entities.extend(
            (fleet.position, fleet.owner_id, gun_range(fleet))
            for fleet in galaxy.fleets
        )

        for world_pos, owner_id, world_radius in entities:
            radius = world_radius * zoom
            radius_i = int(radius)
            if radius_i < 3:
                continue

            screen_x = world_pos.x * zoom + offset_x
            screen_y = world_pos.y * zoom + offset_y
            if screen_x < -margin - radius or screen_x > sw + margin + radius:
                continue
            if screen_y < -margin - radius or screen_y > sh + margin + radius:
                continue

            color = galaxy.empires[owner_id].color
            surface = self._get_range_surface(radius_i, color)

            topleft = (int(screen_x) - radius_i - 2, int(screen_y) - radius_i - 2)
            self.screen.blit(surface, topleft)

    def _draw_hyperlanes(self, galaxy, player, camera, valid_targets):
        selected = player.selected_system_id
        zoom = camera['zoom']
        offset_x = camera['offset_x']
        offset_y = camera['offset_y']
        sw = self.screen.get_width()
        sh = self.screen.get_height()
        line_width = int(max(2, 3 if selected is not None else 2) * zoom)

        for first_id, second_id in galaxy.edges:
            first = galaxy.systems[first_id]
            second = galaxy.systems[second_id]
            first_x = first.pos.x * zoom + offset_x
            first_y = first.pos.y * zoom + offset_y
            second_x = second.pos.x * zoom + offset_x
            second_y = second.pos.y * zoom + offset_y

            if max(first_x, second_x) < -20 or min(first_x, second_x) > sw + 20:
                continue
            if max(first_y, second_y) < -20 or min(first_y, second_y) > sh + 20:
                continue

            highlighted = selected is not None and (
                (first_id == selected and second_id in valid_targets) or
                (second_id == selected and first_id in valid_targets)
            )
            color = config.LANE_HIGHLIGHT if highlighted else config.LANE_COLOR
            pygame.draw.line(self.screen, color, (first_x, first_y), (second_x, second_y), line_width)

    def _draw_fleets(self, galaxy, camera):
        zoom = camera['zoom']
        offset_x = camera['offset_x']
        offset_y = camera['offset_y']
        sw = self.screen.get_width()
        sh = self.screen.get_height()

        for fleet in galaxy.fleets:
            position = fleet.position
            screen_x = position.x * zoom + offset_x
            screen_y = position.y * zoom + offset_y
            if screen_x < -30 or screen_x > sw + 30:
                continue
            if screen_y < -30 or screen_y > sh + 30:
                continue

            color = galaxy.empires[fleet.owner_id].color
            sx = int(screen_x)
            sy = int(screen_y)

            if len(fleet.route) > 1 and fleet.route_index < len(fleet.route):
                current_node = galaxy.systems[fleet.route[fleet.route_index - 1]]
                next_node = galaxy.systems[fleet.route[fleet.route_index]]
                direction = next_node.pos - current_node.pos
            else:
                direction = galaxy.systems[fleet.target_id].pos - position

            fleet_size = max(1, int(fleet.ships))
            base_size = 3 + fleet_size * 0.15
            shape_size = min(base_size * zoom, 18)

            if direction.length_squared() > 0:
                direction = direction.normalize()
                perp = pygame.Vector2(-direction.y, direction.x)

                head_len = shape_size * 1.2
                tail_len = shape_size * 0.6
                half_width = shape_size * 0.4

                tip_x = position.x + direction.x * head_len
                tip_y = position.y + direction.y * head_len
                left_x = position.x - direction.x * tail_len + perp.x * half_width
                left_y = position.y - direction.y * tail_len + perp.y * half_width
                right_x = position.x - direction.x * tail_len - perp.x * half_width
                right_y = position.y - direction.y * tail_len - perp.y * half_width

                points = [
                    (int(tip_x * zoom + offset_x), int(tip_y * zoom + offset_y)),
                    (int(left_x * zoom + offset_x), int(left_y * zoom + offset_y)),
                    (int(right_x * zoom + offset_x), int(right_y * zoom + offset_y)),
                ]

                pygame.draw.polygon(self.screen, color, points)
                outline_color = (
                    min(255, color[0] + 50),
                    min(255, color[1] + 50),
                    min(255, color[2] + 50),
                )
                pygame.draw.polygon(self.screen, outline_color, points, 1)

            text = str(int(fleet.ships))
            label = self._fleet_label_cache.get(text)
            if label is None:
                if len(self._fleet_label_cache) > 512:
                    self._fleet_label_cache.clear()
                label = self.small_font.render(text, True, config.TEXT)
                self._fleet_label_cache[text] = label

            lx = sx - label.get_width() // 2 + 2
            ly = sy - int(shape_size) - 7
            label_bg_rect = pygame.Rect(lx - 2, ly - 1, label.get_width() + 4, label.get_height() + 2)
            bg = self._fleet_label_cache.get("___bg___" + str(label.get_width()) + "_" + str(label.get_height()))
            if bg is None:
                bg = pygame.Surface((label.get_width() + 4, label.get_height() + 2), pygame.SRCALPHA)
                bg.fill((0, 0, 0, 160))
                self._fleet_label_cache["___bg___" + str(label.get_width()) + "_" + str(label.get_height())] = bg
            self.screen.blit(bg, (lx - 2, ly - 1))
            self.screen.blit(label, (lx, ly))

    def _draw_combat_shots(self, galaxy, camera):
        zoom = camera['zoom']
        offset_x = camera['offset_x']
        offset_y = camera['offset_y']
        sw = self.screen.get_width()
        sh = self.screen.get_height()
        thickness = int(max(1, 3 * zoom))

        for shot in galaxy.combat_shots:
            start_x = shot.start.x * zoom + offset_x
            start_y = shot.start.y * zoom + offset_y
            end_x = shot.end.x * zoom + offset_x
            end_y = shot.end.y * zoom + offset_y

            if max(start_x, end_x) < -20 or min(start_x, end_x) > sw + 20:
                continue
            if max(start_y, end_y) < -20 or min(start_y, end_y) > sh + 20:
                continue

            ratio = max(0.0, min(1.0, shot.lifetime / shot.max_lifetime))
            color = (
                int(shot.color[0] * ratio),
                int(shot.color[1] * ratio),
                int(shot.color[2] * ratio),
            )
            pygame.draw.line(self.screen, color, (start_x, start_y), (end_x, end_y), thickness)
            dot_radius = max(1, int(3 * zoom))
            pygame.draw.circle(self.screen, config.STAR_CORE_COLOR, (int(end_x), int(end_y)), dot_radius)

    def _get_ship_font(self, font_size: int) -> pygame.font.Font:
        font = self._ship_font_cache.get(font_size)
        if font is None:
            if len(self._ship_font_cache) > 32:
                self._ship_font_cache.clear()
            font = pygame.font.Font(None, font_size)
            self._ship_font_cache[font_size] = font
        return font

    def _get_ship_label(self, font_size: int, text: str) -> pygame.Surface:
        key = (font_size, text)
        surface = self._ship_label_cache.get(key)
        if surface is None:
            if len(self._ship_label_cache) > 1024:
                self._ship_label_cache.clear()
            font = self._get_ship_font(font_size)
            surface = font.render(text, True, config.TEXT)
            self._ship_label_cache[key] = surface
        return surface

    def _draw_systems(self, galaxy, player, camera, valid_targets):
        pulse_phase = pygame.time.get_ticks() / 500.0
        zoom = camera['zoom']
        offset_x = camera['offset_x']
        offset_y = camera['offset_y']
        base_star_radius = config.STAR_RADIUS * zoom
        base_owned_radius = config.OWNED_STAR_RADIUS * zoom
        font_size = int(18 * max(1, int(zoom)))

        sw = self.screen.get_width()
        sh = self.screen.get_height()
        cull_left = -60.0
        cull_top = -60.0
        cull_right = sw + 60.0
        cull_bottom = sh + 60.0

        hovered_id = player.hovered_system_id
        selected_id = player.selected_system_id
        gathering_points = galaxy.gathering_points
        empires_colors = [empire.color for empire in galaxy.empires]

        for system in galaxy.systems:
            screen_x = system.pos.x * zoom + offset_x
            screen_y = system.pos.y * zoom + offset_y
            if screen_x < cull_left or screen_x > cull_right:
                continue
            if screen_y < cull_top or screen_y > cull_bottom:
                continue
            sx = int(screen_x)
            sy = int(screen_y)

            if system.owner_id is None:
                color = config.NEUTRAL_COLOR
                radius = base_star_radius
                display_radius = radius
            else:
                color = empires_colors[system.owner_id]
                radius = base_owned_radius
                pulse_offset = int(math.sin(pulse_phase + system.id) * 2 * zoom)
                display_radius = radius + pulse_offset
            if system.id in valid_targets:
                glow_radius = radius + 10 * zoom + int(math.sin(pulse_phase * 2) * 3 * zoom)
                pygame.draw.circle(self.screen, config.VALID_TARGET_COLOR, (sx, sy), int(glow_radius), 2)
            if system.id == hovered_id:
                pygame.draw.circle(self.screen, (190, 200, 220), (sx, sy), int(radius + 6 * zoom), 2)
            if system.id == selected_id:
                selection_size = radius + 12 * zoom + int(math.sin(pulse_phase * 1.5) * 2 * zoom)
                pygame.draw.circle(self.screen, config.SELECTION_COLOR, (sx, sy), int(selection_size), 3)
            if system.id in gathering_points:
                gr = radius + 16 * zoom + int(math.sin(pulse_phase * 2.0 + system.id) * 3 * zoom)
                c = config.GATHERING_POINT_COLOR
                pygame.draw.circle(self.screen, c, (sx, sy), int(gr), 2)
                arm = int(6 * zoom)
                corner = int(gr * 0.7)
                for dx, dy in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
                    cx = sx + dx * corner
                    cy = sy + dy * corner
                    pygame.draw.line(self.screen, c, (cx - dx * arm, cy), (cx + dx * arm, cy), 2)
                    pygame.draw.line(self.screen, c, (cx, cy - dy * arm), (cx, cy + dy * arm), 2)
            dr = int(display_radius)
            pygame.draw.circle(self.screen, config.STAR_CORE_COLOR, (sx, sy), dr + int(2 * zoom))
            pygame.draw.circle(self.screen, color, (sx, sy), dr)
            label = self._get_ship_label(font_size, str(int(system.ships)))
            self.screen.blit(label, (sx + dr + 5, sy - 8))

    def _fleet_order_label(self, player):
        if player.use_percent:
            return f"Fleet order: {player.send_percent}%"
        return (
            f"Fleet order: {player.send_count} ship"
            if player.send_count == 1
            else f"Fleet order: {player.send_count} ships"
        )

    def _draw_top_bar(self, galaxy, player, paused, speed):
        sw = self.screen.get_width()
        pygame.draw.rect(self.screen, config.PANEL, (0, 0, sw, config.TOP_BAR_HEIGHT))
        state = "PAUSED" if paused else "RUNNING"
        title = self.font.render("DOMINUS STELLARUM", True, config.TEXT)
        self.screen.blit(title, (18, 12))
        status = self.small_font.render(f"{state}   Speed {speed:g}x   {self._fleet_order_label(player)}", True, config.MUTED_TEXT)
        self.screen.blit(status, (18, 39))
        player_systems = galaxy.empire_system_count(config.PLAYER_ID)
        player_ships = int(galaxy.empire_ship_count(config.PLAYER_ID))
        stats = self.small_font.render(f"Your systems: {player_systems}    Your ships: {player_ships}", True, galaxy.empires[config.PLAYER_ID].color)
        self.screen.blit(stats, stats.get_rect(midtop=(sw // 2, 14)))
        controls_text = "LMB: select   RMB: send   MMB drag: pan   MMB click: gathering point   Wheel: zoom   1-9: send N ships   F1-F10: send %   Space: pause   +/-: speed   F: fullscreen   R: new game"
        controls = self.tiny_font.render(controls_text, True, config.MUTED_TEXT)
        self.screen.blit(controls, controls.get_rect(midtop=(sw // 2, 40)))

    def _draw_bottom_bar(self, galaxy, player):
        sh = self.screen.get_height()
        sw = self.screen.get_width()
        bar_height = int(ui.bottom_bar_height)
        bottom_y = sh - bar_height

        pygame.draw.rect(self.screen, config.PANEL, (0, bottom_y, sw, bar_height))

        highlight = config.LANE_HIGHLIGHT if ui.bar_dragging else config.LANE_COLOR
        pygame.draw.line(self.screen, highlight, (0, bottom_y), (sw, bottom_y), 2)

        grip_w = 160
        grip_h = 12
        grip_rect = pygame.Rect(sw // 2 - grip_w // 2, bottom_y + 4, grip_w, grip_h)
        grip_color = config.LANE_HIGHLIGHT if ui.bar_dragging else (55, 68, 96)
        pygame.draw.rect(self.screen, grip_color, grip_rect, border_radius=6)
        ridge_color = config.PANEL_LIGHT if not ui.bar_dragging else config.BACKGROUND
        for ry in (grip_rect.y + 4, grip_rect.y + 6, grip_rect.y + 8):
            pygame.draw.line(self.screen, ridge_color, (grip_rect.x + 16, ry), (grip_rect.right - 16, ry), 1)

        pad_top = 20
        pad_bottom = 4
        available = bar_height - pad_top - pad_bottom

        empire_count = len(galaxy.empires)
        empire_row_h = max(8, available // (empire_count + 1))

        if self._bottom_font_key != (empire_row_h, empire_count):
            self._bottom_font_key = (empire_row_h, empire_count)
            self._empire_row_font = self._fit_font(empire_row_h, "1. Terran Union [YOU]  123 sys  99999 ships")
            self._empire_title_font = self._fit_font(empire_row_h, "GALACTIC POWERS")

        if player.message:
            message = self.small_font.render(player.message, True, config.SELECTION_COLOR)
            self.screen.blit(message, message.get_rect(midbottom=(sw // 2, bottom_y - 6)))

        self._draw_selection_panel(galaxy, player, bottom_y, pad_top, available)
        self._draw_empire_panel(galaxy, bottom_y, pad_top, empire_row_h, self._empire_title_font, self._empire_row_font)

    def _draw_selection_panel(self, galaxy, player, y, pad_top, available):
        selected_id = player.selected_system_id
        if selected_id is None:
            lines = ["No system selected", "Left-click one of your blue systems.", "Right-click a reachable system to send a fleet.", "Middle-click any system to toggle a gathering point."]
        else:
            system = galaxy.systems[selected_id]
            reachable = len(galaxy.reachable_system_ids(selected_id))
            lines = [system.name, f"Ships: {int(system.ships)}", f"Production: {system.production:.2f}/s", f"Gun range: {gun_range(system):.0f}", f"Hyperlanes: {len(galaxy.neighbors[system.id])}", f"Reachable systems: {reachable}", self._fleet_order_label(player)]

        row_height = max(10, available // len(lines))
        longest_line = max(lines, key=len)

        font_key = (row_height, longest_line)
        if self._selection_font_key != font_key:
            self._selection_font_key = font_key
            self._selection_body_font = self._fit_font(row_height, longest_line)
        body_font = self._selection_body_font

        cursor_y = y + pad_top
        for index, line in enumerate(lines):
            color = config.TEXT if index == 0 else config.MUTED_TEXT
            surface = body_font.render(line, True, color)
            self.screen.blit(surface, (18, cursor_y))
            cursor_y += row_height

    def _draw_empire_panel(self, galaxy, y, pad_top, row_height, title_font, row_font):
        sw = self.screen.get_width()
        right_margin = 18
        right_edge = sw - right_margin
        cursor_y = y + pad_top

        ranked = sorted(
            galaxy.empires,
            key=lambda empire: galaxy.empire_strength(empire.id),
            reverse=True,
        )

        heading = title_font.render("GALACTIC POWERS", True, config.TEXT)
        self.screen.blit(heading, heading.get_rect(right=right_edge, top=cursor_y))
        cursor_y += row_height

        for rank, empire in enumerate(ranked, start=1):
            systems = galaxy.empire_system_count(empire.id)
            ships = int(galaxy.empire_ship_count(empire.id))
            color = empire.color if empire.alive else config.MUTED_TEXT
            marker = "YOU" if empire.is_player else "AI"
            dead = "" if empire.alive else " (dead)"
            text = f"{rank}. {empire.name} [{marker}]  {systems} sys  {ships} ships{dead}"
            surface = row_font.render(text, True, color)
            self.screen.blit(surface, surface.get_rect(right=right_edge, top=cursor_y))
            cursor_y += row_height

    def _draw_camera_info(self, camera):
        bar_top = self.screen.get_height() - int(ui.bottom_bar_height)
        info_text = self.tiny_font.render(f"Zoom: {camera['zoom']:.2f}x", True, config.MUTED_TEXT)
        self.screen.blit(info_text, (self.screen.get_width() - info_text.get_width() - 18, bar_top - 24))

    def _draw_game_state(self, galaxy):
        winner = galaxy.winner()
        if galaxy.player_won():
            self._draw_end_screen("VICTORY", "You control the galaxy. Press R to start anew.")
        elif winner is not None:
            self._draw_end_screen("DEFEAT", f"The {winner.name} rules the galaxy. Press R to try again.")

    def _draw_end_screen(self, title, subtitle):
        overlay = pygame.Surface(
            (self.screen.get_width(), self.screen.get_height()),
            pygame.SRCALPHA,
        )
        overlay.fill((0, 0, 0, 160))
        self.screen.blit(overlay, (0, 0))

        title_surface = self.huge_font.render(title, True, config.SELECTION_COLOR)
        subtitle_surface = self.font.render(subtitle, True, config.TEXT)

        sw = self.screen.get_width()
        sh = self.screen.get_height()

        self.screen.blit(
            title_surface,
            title_surface.get_rect(center=(sw // 2, sh // 2 - 30)),
        )
        self.screen.blit(
            subtitle_surface,
            subtitle_surface.get_rect(center=(sw // 2, sh // 2 + 30)),
        )