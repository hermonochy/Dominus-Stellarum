import math
import pygame

from . import config
from . import ui
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
        self._recache_fonts()

    def _recache_fonts(self):
        w = self.screen.get_width()
        h = self.screen.get_height()
        scale_x = w / self.base_width
        scale_y = h / self.base_height
        scale = min(scale_x, scale_y, 1.5)
        self.font = pygame.font.Font(None, int(22 * scale))
        self.small_font = pygame.font.Font(None, int(18 * scale))
        self.tiny_font = pygame.font.Font(None, int(14 * scale))
        self.huge_font = pygame.font.Font(None, int(64 * scale))

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
        self._draw_hyperlanes(galaxy, player, camera)
        self._draw_gun_ranges(galaxy, camera)
        self._draw_fleets(galaxy, camera)
        self._draw_combat_shots(galaxy, camera)
        self._draw_systems(galaxy, player, camera)
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

    def _gun_range(self, system) -> float:
        ships = min(system.ships, config.GUN_RANGE_MAX_SHIPS)
        factor = math.log(1.0 + ships) / math.log(1.0 + config.GUN_RANGE_MAX_SHIPS)
        return config.GUN_RANGE_MIN + (config.GUN_RANGE_MAX - config.GUN_RANGE_MIN) * factor

    def _fleet_range(self, fleet) -> float:
        ships = min(fleet.ships, config.GUN_RANGE_MAX_SHIPS)
        factor = math.log(1.0 + ships) / math.log(1.0 + config.GUN_RANGE_MAX_SHIPS)
        return config.GUN_RANGE_MIN + (config.GUN_RANGE_MAX - config.GUN_RANGE_MIN) * factor

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

        entities = [
            (self.world_to_screen(system.pos), self._gun_range(system), system.owner_id)
            for system in galaxy.systems
            if system.owner_id is not None
        ]
        entities.extend(
            (self.world_to_screen(fleet.position), self._fleet_range(fleet), fleet.owner_id)
            for fleet in galaxy.fleets
        )

        for center, world_radius, owner_id in entities:
            radius = world_radius * camera['zoom']
            radius_i = int(radius)
            if radius_i < 3:
                continue

            color = galaxy.empires[owner_id].color
            surface = self._get_range_surface(radius_i, color)

            topleft = (int(center.x) - radius_i - 2, int(center.y) - radius_i - 2)
            self.screen.blit(surface, topleft)

    def _draw_hyperlanes(self, galaxy, player, camera):
        selected = player.selected_system_id
        valid_targets = player.valid_target_ids()
        for first_id, second_id in galaxy.edges:
            first = galaxy.systems[first_id]
            second = galaxy.systems[second_id]
            first_screen = self.world_to_screen(first.pos)
            second_screen = self.world_to_screen(second.pos)
            highlighted = selected is not None and (
                (first_id == selected and second_id in valid_targets) or
                (second_id == selected and first_id in valid_targets)
            )
            width = int(max(2, 3 if highlighted else 2) * camera['zoom'])
            color = config.LANE_HIGHLIGHT if highlighted else config.LANE_COLOR
            pygame.draw.line(self.screen, color, (first_screen.x, first_screen.y), (second_screen.x, second_screen.y), width)

    def _draw_fleets(self, galaxy, camera):
        for fleet in galaxy.fleets:
            position = fleet.position
            target = galaxy.systems[fleet.target_id]
            color = galaxy.empires[fleet.owner_id].color
            position_screen = self.world_to_screen(position)

            if len(fleet.route) > 1 and fleet.route_index < len(fleet.route):
                current_node_id = fleet.route[fleet.route_index - 1]
                next_node_id = fleet.route[fleet.route_index]
                current_node = galaxy.systems[current_node_id]
                next_node = galaxy.systems[next_node_id]
                direction = next_node.pos - current_node.pos
            else:
                direction = target.pos - position

            fleet_size = max(1, int(fleet.ships))
            base_size = 3 + fleet_size * 0.15
            shape_size = min(base_size * camera['zoom'], 18)

            if direction.length_squared() > 0:
                direction = direction.normalize()
                perp = pygame.Vector2(-direction.y, direction.x)

                head_len = shape_size * 1.2
                tail_len = shape_size * 0.6
                half_width = shape_size * 0.4

                tip = position + direction * head_len
                left_wing = position - direction * tail_len + perp * half_width
                right_wing = position - direction * tail_len - perp * half_width

                points = [
                    (int(self.world_to_screen(tip).x), int(self.world_to_screen(tip).y)),
                    (int(self.world_to_screen(left_wing).x), int(self.world_to_screen(left_wing).y)),
                    (int(self.world_to_screen(right_wing).x), int(self.world_to_screen(right_wing).y))
                ]

                pygame.draw.polygon(self.screen, color, points)
                outline_color = tuple(min(255, c + 50) for c in color)
                pygame.draw.polygon(self.screen, outline_color, points, 1)

            label = self.small_font.render(str(int(fleet.ships)), True, config.TEXT)
            label_bg = pygame.Surface((label.get_width() + 4, label.get_height() + 2), pygame.SRCALPHA)
            label_bg.fill((0, 0, 0, 160))
            self.screen.blit(label_bg, (int(position_screen.x) - label_bg.get_width() // 2, int(position_screen.y) - int(shape_size) - 8))
            self.screen.blit(label, (int(position_screen.x) - label.get_width() // 2 + 2, int(position_screen.y) - int(shape_size) - 7))

    def _draw_combat_shots(self, galaxy, camera):
        for shot in galaxy.combat_shots:
            ratio = max(0.0, min(1.0, shot.lifetime / shot.max_lifetime))
            color = tuple(int(channel * ratio) for channel in shot.color)
            start_screen = self.world_to_screen(shot.start)
            end_screen = self.world_to_screen(shot.end)
            thickness = int(max(1, 3 * camera['zoom']))
            pygame.draw.line(self.screen, color, (start_screen.x, start_screen.y), (end_screen.x, end_screen.y), thickness)
            pygame.draw.circle(self.screen, config.STAR_CORE_COLOR, (int(end_screen.x), int(end_screen.y)), int(max(1, 3 * camera['zoom'])))

    def _draw_systems(self, galaxy, player, camera):
        valid_targets = player.valid_target_ids()
        pulse_phase = pygame.time.get_ticks() / 500.0
        base_star_radius = config.STAR_RADIUS * camera['zoom']
        base_owned_radius = config.OWNED_STAR_RADIUS * camera['zoom']
        for system in galaxy.systems:
            system_screen = self.world_to_screen(system.pos)
            if system.owner_id is None:
                color = config.NEUTRAL_COLOR
                radius = base_star_radius
            else:
                color = galaxy.empires[system.owner_id].color
                radius = base_owned_radius
            if system.owner_id is not None:
                pulse_offset = int(math.sin(pulse_phase + system.id) * 2 * camera['zoom'])
                display_radius = radius + pulse_offset
            else:
                display_radius = radius
            if system.id in valid_targets:
                glow_radius = radius + 10 * camera['zoom'] + int(math.sin(pulse_phase * 2) * 3 * camera['zoom'])
                pygame.draw.circle(self.screen, config.VALID_TARGET_COLOR, (int(system_screen.x), int(system_screen.y)), int(glow_radius), 2)
            if system.id == player.hovered_system_id:
                pygame.draw.circle(self.screen, (190, 200, 220), (int(system_screen.x), int(system_screen.y)), int(radius + 6 * camera['zoom']), 2)
            if system.id == player.selected_system_id:
                selection_size = radius + 12 * camera['zoom'] + int(math.sin(pulse_phase * 1.5) * 2 * camera['zoom'])
                pygame.draw.circle(self.screen, config.SELECTION_COLOR, (int(system_screen.x), int(system_screen.y)), int(selection_size), 3)
            if system.id in galaxy.gathering_points:
                gr = radius + 16 * camera['zoom'] + int(math.sin(pulse_phase * 2.0 + system.id) * 3 * camera['zoom'])
                gx, gy = int(system_screen.x), int(system_screen.y)
                c = config.GATHERING_POINT_COLOR
                pygame.draw.circle(self.screen, c, (gx, gy), int(gr), 2)
                arm = int(6 * camera['zoom'])
                corner = int(gr * 0.7)
                for dx, dy in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
                    cx = gx + dx * corner
                    cy = gy + dy * corner
                    pygame.draw.line(self.screen, c, (cx - dx * arm, cy), (cx + dx * arm, cy), 2)
                    pygame.draw.line(self.screen, c, (cx, cy - dy * arm), (cx, cy + dy * arm), 2)
            pygame.draw.circle(self.screen, config.STAR_CORE_COLOR, (int(system_screen.x), int(system_screen.y)), int(display_radius + 2 * camera['zoom']))
            pygame.draw.circle(self.screen, color, (int(system_screen.x), int(system_screen.y)), int(display_radius))
            font_scale = max(1, int(camera['zoom']))
            ship_font = pygame.font.Font(None, int(18 * font_scale))
            ship_text = ship_font.render(str(int(system.ships)), True, config.TEXT)
            self.screen.blit(ship_text, (int(system_screen.x) + int(display_radius) + 5, int(system_screen.y) - 8))

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

        sample_row = "1. Terran Union [YOU]  123 sys  99999 ships"
        empire_row_font = self._fit_font(empire_row_h, sample_row)
        empire_title_font = self._fit_font(empire_row_h, "GALACTIC POWERS")

        if player.message:
            message = self.small_font.render(player.message, True, config.SELECTION_COLOR)
            self.screen.blit(message, message.get_rect(midbottom=(sw // 2, bottom_y - 6)))

        self._draw_selection_panel(galaxy, player, bottom_y, pad_top, available)
        self._draw_empire_panel(galaxy, bottom_y, pad_top, empire_row_h, empire_title_font, empire_row_font)

    def _draw_selection_panel(self, galaxy, player, y, pad_top, available):
        selected_id = player.selected_system_id
        if selected_id is None:
            lines = ["No system selected", "Left-click one of your blue systems.", "Right-click a reachable system to send a fleet.", "Middle-click any system to toggle a gathering point."]
        else:
            system = galaxy.systems[selected_id]
            reachable = len(galaxy.reachable_system_ids(selected_id))
            gun_range = self._gun_range(system)
            lines = [system.name, f"Ships: {int(system.ships)}", f"Production: {system.production:.2f}/s", f"Gun range: {gun_range:.0f}", f"Hyperlanes: {len(galaxy.neighbors[system.id])}", f"Reachable systems: {reachable}", self._fleet_order_label(player)]

        row_height = max(10, available // len(lines))
        longest_line = max(lines, key=len)
        body_font = self._fit_font(row_height, longest_line)

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