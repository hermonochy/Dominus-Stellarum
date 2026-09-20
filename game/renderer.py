# renderer.py
import math
import pygame

from . import config
from .galaxy import Galaxy
from .player import PlayerController

class Renderer:
    def __init__(self, screen, camera):
        self.screen = screen
        self.camera = camera
        self.base_width = 1280
        self.base_height = 800
        self._recache_fonts()

    def _recache_fonts(self):
        w = self.screen.get_width()
        h = self.screen.get_height()
        scale_x = w / self.base_width
        scale_y = h / self.base_height
        scale = min(scale_x, scale_y, 1.5)

        base_size = 22
        self.font = pygame.font.Font(None, int(base_size * scale))
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
        self._draw_defender_orbits(galaxy, camera)
        self._draw_fleets(galaxy, camera)
        self._draw_combat_shots(galaxy, camera)
        self._draw_systems(galaxy, player, camera)
        self._draw_top_bar(galaxy, player, paused, speed)
        self._draw_bottom_bar(galaxy, player)
        self._draw_camera_info(camera)
        self._draw_game_state(galaxy)

    def _draw_hyperlanes(self, galaxy, player, camera):
        selected = player.selected_system_id
        valid_targets = player.valid_target_ids()

        for first_id, second_id in galaxy.edges:
            first = galaxy.systems[first_id]
            second = galaxy.systems[second_id]

            first_screen = self.world_to_screen(first.pos)
            second_screen = self.world_to_screen(second.pos)

            highlighted = (
                selected is not None
                and (
                    (first_id == selected and second_id in valid_targets)
                    or (second_id == selected and first_id in valid_targets)
                )
            )

            width = int(max(1, 3 if highlighted else 1))
            color = config.LANE_HIGHLIGHT if highlighted else config.LANE_COLOR
            pygame.draw.line(
                self.screen,
                color,
                (first_screen.x, first_screen.y),
                (second_screen.x, second_screen.y),
                width,
            )

    def _draw_defender_orbits(self, galaxy, camera):
        current_time = pygame.time.get_ticks() / 1000.0
        scaled_radius = config.DEFENDER_ORBIT_RADIUS * camera['zoom']

        for system in galaxy.systems:
            if system.owner_id is None:
                continue

            empire = galaxy.empires[system.owner_id]
            system_screen = self.world_to_screen(system.pos)
            orbit_color = tuple(c // 3 for c in empire.color)

            pygame.draw.circle(
                self.screen,
                orbit_color,
                (int(system_screen.x), int(system_screen.y)),
                int(scaled_radius),
                1,
            )

            for index in range(config.DEFENDER_COUNT):
                angle = (
                    current_time * config.DEFENDER_ORBIT_SPEED
                    + index * math.tau / config.DEFENDER_COUNT
                )

                position = system.pos + pygame.Vector2(
                    math.cos(angle),
                    math.sin(angle),
                ) * config.DEFENDER_ORBIT_RADIUS

                pos_screen = self.world_to_screen(position)
                dot_size = max(2, int(3 * camera['zoom']))

                pygame.draw.circle(
                    self.screen,
                    empire.color,
                    (int(pos_screen.x), int(pos_screen.y)),
                    dot_size,
                )
                pygame.draw.circle(
                    self.screen,
                    config.STAR_CORE_COLOR,
                    (int(pos_screen.x), int(pos_screen.y)),
                    dot_size + 1,
                    1,
                )

    def _draw_fleets(self, galaxy, camera):
        for fleet in galaxy.fleets:
            position = fleet.position
            target = galaxy.systems[fleet.target_id]
            color = galaxy.empires[fleet.owner_id].color

            position_screen = self.world_to_screen(position)
            target_screen = self.world_to_screen(target.pos)

            trail_length = min(15, int(fleet.ships))
            for i in range(trail_length):
                alpha = (255 - i * 15) // max(1, trail_length)
                trail_pos = position.lerp(
                    target.pos,
                    min(1.0, (i + fleet.segment_progress) / max(1, trail_length + 1))
                )
                trail_screen = self.world_to_screen(trail_pos)

                faded_color = tuple(min(255, c + (255 - c) * (alpha / 255)) for c in color)
                trail_radius = max(2, int((5 - i // 4) * camera['zoom']))
                pygame.draw.circle(
                    self.screen,
                    faded_color,
                    (int(trail_screen.x), int(trail_screen.y)),
                    trail_radius,
                )

            pygame.draw.circle(
                self.screen,
                color,
                (int(position_screen.x), int(position_screen.y)),
                int(max(2, 6 * camera['zoom'])),
            )

            direction = target.pos - position
            if direction.length_squared() > 0:
                direction = direction.normalize()
                perpendicular = pygame.Vector2(-direction.y, direction.x)

                tip = position + direction * 12
                left = position - direction * 6 + perpendicular * 6
                right = position - direction * 6 - perpendicular * 6

                tip_s = self.world_to_screen(tip)
                left_s = self.world_to_screen(left)
                right_s = self.world_to_screen(right)

                pygame.draw.polygon(
                    self.screen,
                    color,
                    [(tip_s.x, tip_s.y), (left_s.x, left_s.y), (right_s.x, right_s.y)],
                )

            label = self.tiny_font.render(str(int(fleet.ships)), True, config.TEXT)
            self.screen.blit(
                label,
                (int(position_screen.x) + 10, int(position_screen.y) - 10),
            )

    def _draw_combat_shots(self, galaxy, camera):
        for shot in galaxy.combat_shots:
            ratio = max(0.0, min(1.0, shot.lifetime / shot.max_lifetime))
            color = tuple(int(channel * ratio) for channel in shot.color)

            start_screen = self.world_to_screen(shot.start)
            end_screen = self.world_to_screen(shot.end)
            thickness = int(max(1, 3 * camera['zoom']))

            pygame.draw.line(
                self.screen,
                color,
                (start_screen.x, start_screen.y),
                (end_screen.x, end_screen.y),
                thickness,
            )
            pygame.draw.circle(
                self.screen,
                config.STAR_CORE_COLOR,
                (int(end_screen.x), int(end_screen.y)),
                int(max(1, 3 * camera['zoom'])),
            )

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
                pygame.draw.circle(
                    self.screen,
                    config.VALID_TARGET_COLOR,
                    (int(system_screen.x), int(system_screen.y)),
                    int(glow_radius),
                    2,
                )

            if system.id == player.hovered_system_id:
                pygame.draw.circle(
                    self.screen,
                    (190, 200, 220),
                    (int(system_screen.x), int(system_screen.y)),
                    int(radius + 6 * camera['zoom']),
                    2,
                )

            if system.id == player.selected_system_id:
                selection_size = radius + 12 * camera['zoom'] + int(math.sin(pulse_phase * 1.5) * 2 * camera['zoom'])
                pygame.draw.circle(
                    self.screen,
                    config.SELECTION_COLOR,
                    (int(system_screen.x), int(system_screen.y)),
                    int(selection_size),
                    3,
                )

            pygame.draw.circle(
                self.screen,
                config.STAR_CORE_COLOR,
                (int(system_screen.x), int(system_screen.y)),
                int(display_radius + 2 * camera['zoom']),
            )
            pygame.draw.circle(
                self.screen,
                color,
                (int(system_screen.x), int(system_screen.y)),
                int(display_radius),
            )

            font_scale = max(1, int(camera['zoom']))
            ship_font = pygame.font.Font(None, int(18 * font_scale))
            ship_text = ship_font.render(str(int(system.ships)), True, config.TEXT)
            self.screen.blit(
                ship_text,
                (int(system_screen.x) + int(display_radius) + 5, int(system_screen.y) - 8),
            )

    def _draw_top_bar(self, galaxy, player, paused, speed):
        sw = self.screen.get_width()

        pygame.draw.rect(self.screen, config.PANEL, (0, 0, sw, config.TOP_BAR_HEIGHT))
        state = "PAUSED" if paused else "RUNNING"

        title = self.font.render("DOMINUS STELLARUM", True, config.TEXT)
        self.screen.blit(title, (18, 12))

        status = self.small_font.render(
            f"{state}   Speed {speed:g}x   Send {player.send_percent}%",
            True, config.MUTED_TEXT,
        )
        self.screen.blit(status, (18, 39))

        player_systems = galaxy.empire_system_count(config.PLAYER_ID)
        player_ships = int(galaxy.empire_ship_count(config.PLAYER_ID))

        stats = self.small_font.render(
            f"Your systems: {player_systems}    Your ships: {player_ships}",
            True, galaxy.empires[config.PLAYER_ID].color,
        )
        self.screen.blit(stats, stats.get_rect(midtop=(sw // 2, 14)))

        controls_text = (
            "Left click: select   Right click: send   Wheel: zoom   "
            "MMB drag / Arrows: pan   Space: pause   +/-: speed   "
            "F: fullscreen   R: new game"
        )
        controls = self.tiny_font.render(controls_text, True, config.MUTED_TEXT)
        self.screen.blit(controls, controls.get_rect(midtop=(sw // 2, 40)))

    def _draw_bottom_bar(self, galaxy, player):
        sh = self.screen.get_height()
        bottom_y = sh - config.BOTTOM_BAR_HEIGHT

        pygame.draw.rect(self.screen, config.PANEL, (0, bottom_y, self.screen.get_width(), config.BOTTOM_BAR_HEIGHT))
        pygame.draw.line(self.screen, config.LANE_COLOR, (0, bottom_y), (self.screen.get_width(), bottom_y), 2)

        self._draw_selection_panel(galaxy, player, bottom_y)
        self._draw_empire_panel(galaxy, bottom_y)

        if player.message:
            message = self.small_font.render(player.message, True, config.SELECTION_COLOR)
            self.screen.blit(message, message.get_rect(midbottom=(self.screen.get_width() // 2, sh - 8)))

    def _draw_selection_panel(self, galaxy, player, y):
        selected_id = player.selected_system_id

        if selected_id is None:
            lines = [
                "No system selected",
                "Left-click one of your blue systems.",
                "Right-click a reachable system to send a fleet.",
            ]
        else:
            system = galaxy.systems[selected_id]
            reachable = len(galaxy.reachable_system_ids(selected_id))

            lines = [
                system.name,
                f"Ships: {int(system.ships)}",
                f"Production: {system.production:.2f}/s",
                f"Hyperlanes: {len(galaxy.neighbors[system.id])}",
                f"Reachable systems: {reachable}",
                f"Fleet order: {player.send_percent}%",
            ]

        for index, line in enumerate(lines):
            color = config.TEXT if index == 0 else config.MUTED_TEXT
            font = self.font if index == 0 else self.small_font
            surface = font.render(line, True, color)
            self.screen.blit(surface, (18, y + 10 + index * 19))

    def _draw_empire_panel(self, galaxy, y):
        sw = self.screen.get_width()
        x = sw - 320

        heading = self.font.render("GALACTIC POWERS", True, config.TEXT)
        self.screen.blit(heading, (x, y + 12))

        for index, empire in enumerate(galaxy.empires):
            systems = galaxy.empire_system_count(empire.id)
            ships = int(galaxy.empire_ship_count(empire.id))

            color = empire.color if empire.alive else config.MUTED_TEXT
            marker = "YOU" if empire.is_player else "AI"
            text = f"{empire.name} [{marker}]  {systems} systems  {ships} ships"

            surface = self.tiny_font.render(text, True, color)
            self.screen.blit(surface, (x, y + 38 + index * 14))

    def _draw_camera_info(self, camera):
        info_text = self.tiny_font.render(
            f"Zoom: {camera['zoom']:.2f}x",
            True, config.MUTED_TEXT,
        )
        self.screen.blit(
            info_text,
            (self.screen.get_width() - info_text.get_width() - 18, config.HEIGHT - config.BOTTOM_BAR_HEIGHT - 24),
        )

    def _draw_game_state(self, galaxy):
        if galaxy.player_won():
            self._draw_end_screen("VICTORY", "You control the galaxy.", galaxy.empires[config.PLAYER_ID].color)
        elif galaxy.player_defeated():
            self._draw_end_screen("DEFEAT", "Your empire has fallen.", (230, 90, 90))

    def _draw_end_screen(self, heading, subtitle, color):
        overlay = pygame.Surface((self.screen.get_width(), self.screen.get_height()), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 175))
        self.screen.blit(overlay, (0, 0))

        title = self.huge_font.render(heading, True, color)
        self.screen.blit(title, title.get_rect(center=(self.screen.get_width() // 2, self.screen.get_height() // 2 - 35)))

        description = self.font.render(subtitle, True, config.TEXT)
        self.screen.blit(description, description.get_rect(center=(self.screen.get_width() // 2, self.screen.get_height() // 2 + 20)))

        restart = self.small_font.render("Press R to start a new galaxy.", True, config.MUTED_TEXT)
        self.screen.blit(restart, restart.get_rect(center=(self.screen.get_width() // 2, self.screen.get_height() // 2 + 55)))