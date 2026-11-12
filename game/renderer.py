import math
import random
import pygame

from . import config
from . import ui
from .combat import gun_range, escort_range
from .galaxy import Galaxy
from .player import PlayerController
from .popup import EmpirePopup

class Renderer:
    RANGE_CULL_MARGIN = 60

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
        self._escort_label_cache: dict[str, pygame.Surface] = {}
        self._missile_label = None
        self._missile_label_bg = None
        self._recache_fonts()
        self._bottom_font_key = None
        self._empire_row_font = None
        self._empire_title_font = None
        self._tooltip_font_key = None
        self._tooltip_font = None
        self._tooltip_label_font_key = None
        self._tooltip_label_font = None
        self._empire_row_rects: list[tuple[pygame.Rect, object]] = []
        self._empire_row_hit_width = 540
        self._reachable_galaxy: Galaxy | None = None
        self._reachable_counts: dict[int, int] = {}
        self.popup = EmpirePopup()
        self.shake_timer = 0.0
        self.shake_intensity = 0.0
        self.warn_flash_phase = 0.0
        self.alerts: list[str] = []
        self._space_background = None
        self._space_background_size = None

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
        self._missile_label = self.tiny_font.render("NUCLEAR", True, (255, 170, 125))
        self._missile_label_bg = pygame.Surface((self._missile_label.get_width() + 8, self._missile_label.get_height() + 6), pygame.SRCALPHA)
        self._missile_label_bg.fill((20, 7, 8, 205))
        self._ship_font_cache.clear()
        self._ship_label_cache.clear()
        self._fleet_label_cache.clear()
        self._escort_label_cache.clear()
        self._tooltip_font_key = None
        self._tooltip_label_font_key = None

    def update_shake(self, dt: float) -> None:
        self.shake_timer = max(0.0, self.shake_timer - dt)
        self.warn_flash_phase += dt

    def trigger_shake(self) -> None:
        self.shake_timer = config.SHAKE_DURATION
        self.shake_intensity = config.SHAKE_INTENSITY

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

    def draw(self, galaxy, player, paused, speed, camera, dt=0.016):
        self.galaxy = galaxy
        self._recache_fonts()
        self._update_shake_state(galaxy, dt)
        self._draw_space_background()
        shake_offset = self._compute_shake_offset()
        shake_camera = camera
        if shake_offset != (0, 0):
            shake_camera = {
                'zoom': camera['zoom'],
                'offset_x': camera['offset_x'] + shake_offset[0],
                'offset_y': camera['offset_y'] + shake_offset[1],
            }
        valid_targets = player.valid_target_ids()
        self._draw_hyperlanes(galaxy, player, shake_camera, valid_targets)
        self._draw_gun_ranges(galaxy, shake_camera)
        self._draw_escort_ranges(galaxy, shake_camera)
        self._draw_fleets(galaxy, shake_camera)
        self._draw_systems(galaxy, player, shake_camera, valid_targets)
        self._draw_command_ships(galaxy, player, shake_camera)
        self._draw_combat_shots(galaxy, shake_camera)
        self._draw_combat_impacts(galaxy, shake_camera)
        self._draw_explosions(galaxy, shake_camera)
        self._draw_missile_warnings(galaxy, shake_camera)
        self._draw_nuke_target_preview(galaxy, player, shake_camera)
        self._draw_top_bar(galaxy, player, paused, speed)
        self._draw_bottom_bar(galaxy, player)
        self._draw_hover_tooltip(galaxy, player)
        self._draw_camera_info(camera)
        self._draw_game_state(galaxy)
        self.popup.draw(self.screen)


    def _draw_space_background(self) -> None:
        size = self.screen.get_size()
        if self._space_background is None or self._space_background_size != size:
            width, height = size
            background = pygame.Surface(size).convert()
            background.fill(config.BACKGROUND)
            haze = pygame.Surface(size, pygame.SRCALPHA)
            rng = random.Random(73191)
            for _ in range(18):
                x = rng.randrange(width)
                y = rng.randrange(height)
                radius = rng.randint(max(35, min(width, height) // 14), max(60, min(width, height) // 5))
                tint = rng.choice(((30, 48, 92), (48, 35, 88), (22, 70, 92), (72, 42, 78)))
                pygame.draw.circle(haze, (*tint, rng.randint(5, 13)), (x, y), radius)
            haze = pygame.transform.smoothscale(haze, (max(1, width // 3), max(1, height // 3)))
            haze = pygame.transform.smoothscale(haze, size)
            background.blit(haze, (0, 0))
            stars = pygame.Surface(size, pygame.SRCALPHA)
            for _ in range(max(90, width * height // 8500)):
                x = rng.randrange(width)
                y = rng.randrange(height)
                radius = rng.choices((1, 2, 3), (82, 16, 2))[0]
                alpha = rng.randint(45, 155)
                pygame.draw.circle(stars, (155, 185, 235, alpha), (x, y), radius)
            background.blit(stars, (0, 0))
            self._space_background = background
            self._space_background_size = size
        self.screen.blit(self._space_background, (0, 0))

    def _update_shake_state(self, galaxy, dt: float) -> None:
        fresh = [
            explosion for explosion in galaxy.explosions
            if explosion.age < dt * 2.0 + 0.001
        ]
        if fresh:
            self.trigger_shake()
        self.shake_timer = max(0.0, self.shake_timer - dt)
        self.warn_flash_phase += dt

    def _compute_shake_offset(self) -> tuple[int, int]:
        if self.shake_timer <= 0.0:
            return (0, 0)
        progress = self.shake_timer / config.SHAKE_DURATION
        magnitude = self.shake_intensity * progress
        ticks = pygame.time.get_ticks()
        return (
            int(math.sin(ticks * 0.07) * magnitude),
            int(math.sin(ticks * 0.09) * magnitude),
        )

    def empire_at(self, pos):
        for rect, empire in self._empire_row_rects:
            if rect.collidepoint(pos):
                return empire
        return None

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
        zoom = camera['zoom']
        if self._range_cache_zoom != zoom:
            self._range_cache.clear()
            self._range_cache_zoom = zoom

        offset_x = camera['offset_x']
        offset_y = camera['offset_y']
        sw = self.screen.get_width()
        sh = self.screen.get_height()
        margin = self.RANGE_CULL_MARGIN * zoom

        entities = [
            (system.pos, system.owner_id, gun_range(system))
            for system in galaxy.systems
            if system.owner_id is not None
        ]
        entities.extend(
            (fleet.position, fleet.owner_id, gun_range(fleet))
            for fleet in galaxy.fleets
            if not fleet.is_missile
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

    def _draw_escort_ranges(self, galaxy, camera):
        entities = []
        for empire_id, ship in galaxy.command.ships.items():
            escorts = galaxy.empires[empire_id].escorts
            if escorts < 1.0:
                continue
            if empire_id != config.PLAYER_ID and not config.COMMAND_SHOW_ENEMY_CAPITALS:
                continue
            entities.append((ship.position, escorts))
        if not entities:
            return

        zoom = camera['zoom']
        offset_x = camera['offset_x']
        offset_y = camera['offset_y']
        sw = self.screen.get_width()
        sh = self.screen.get_height()
        margin = self.RANGE_CULL_MARGIN * zoom

        for position, escorts in entities:
            radius = escort_range(escorts) * zoom
            radius_i = int(radius)
            if radius_i < 3:
                continue

            screen_x = position.x * zoom + offset_x
            screen_y = position.y * zoom + offset_y
            if screen_x < -margin - radius or screen_x > sw + margin + radius:
                continue
            if screen_y < -margin - radius or screen_y > sh + margin + radius:
                continue

            surface = self._get_range_surface(radius_i, config.GATHERING_POINT_COLOR)
            topleft = (int(screen_x) - radius_i - 2, int(screen_y) - radius_i - 2)
            self.screen.blit(surface, topleft)

    def _draw_explosions(self, galaxy, camera):
        zoom = camera['zoom']
        offset_x = camera['offset_x']
        offset_y = camera['offset_y']
        sw = self.screen.get_width()
        sh = self.screen.get_height()

        for explosion in galaxy.explosions:
            progress = min(1.0, max(0.0, explosion.age / explosion.max_age))
            sx = int(explosion.pos.x * zoom + offset_x)
            sy = int(explosion.pos.y * zoom + offset_y)
            peak = max(4, int(explosion.peak_radius * zoom))
            if sx < -peak - 48 or sx > sw + peak + 48 or sy < -peak - 48 or sy > sh + peak + 48:
                continue
            seed = explosion.pos.x * 0.013 + explosion.pos.y * 0.017
            self._draw_nuclear_blast((sx, sy), peak, progress, explosion.age, seed, zoom)

    def _draw_nuclear_blast(self, center, peak: int, progress: float, age: float, seed: float, zoom: float) -> None:
        sx, sy = center
        scale = max(0.65, min(1.7, zoom))
        dark = config.BACKGROUND

        flash = max(0.0, 1.0 - progress / 0.055)
        if flash > 0.0:
            flash_radius = max(2, int(peak * (0.055 + 0.14 * (1.0 - flash))))
            pygame.draw.circle(self.screen, (255, 255, 245), center, flash_radius)
            pygame.draw.circle(self.screen, (255, 226, 170), center, max(2, int(flash_radius * 1.75)), max(1, int(3 * scale)))
            pygame.draw.circle(self.screen, (255, 130, 52), center, max(3, int(flash_radius * 2.25)), max(1, int(2 * scale)))

        for wave in range(3):
            delay = wave * 0.055
            wave_phase = min(1.0, max(0.0, (progress - delay) / 0.27))
            if wave_phase <= 0.0:
                continue
            ease = 1.0 - (1.0 - wave_phase) ** 2.8
            radius = max(2, int(peak * (0.035 + 0.96 * ease)))
            fade = min(1.0, max(0.0, (1.0 - wave_phase) * 1.9))
            fade *= min(1.0, max(0.0, (0.54 - progress + delay) * 3.2))
            if fade <= 0.0:
                continue
            width = max(1, int((8 - wave * 2) * scale * fade))
            red = (160, 34, 18)
            orange = (int(130 + 125 * fade), int(34 + 123 * fade), int(18 + 62 * fade))
            pale = (int(95 + 160 * fade), int(42 + 193 * fade), int(25 + 185 * fade))
            pygame.draw.circle(self.screen, red, center, radius, width + max(1, int(3 * scale)))
            pygame.draw.circle(self.screen, orange, center, radius, width)
            pygame.draw.circle(self.screen, pale, center, max(1, radius - max(1, width)), max(1, int(scale)))

        if progress < 0.78:
            expansion = min(1.0, progress / 0.22)
            if progress < 0.22:
                fireball = 0.075 + 0.275 * (1.0 - (1.0 - expansion) ** 1.5)
            else:
                contraction = min(1.0, (progress - 0.22) / 0.56)
                fireball = 0.35 * (1.0 - contraction) ** 1.35
            heat = max(0.0, 1.0 - max(0.0, progress - 0.18) / 0.6)
            outer_radius = max(2, int(peak * fireball))
            outer_color = tuple(int(dark[i] + ((115, 25, 12)[i] - dark[i]) * heat) for i in range(3))
            red_color = tuple(int(dark[i] + ((230, 55, 18)[i] - dark[i]) * heat) for i in range(3))
            orange_color = tuple(int(dark[i] + ((255, 132, 35)[i] - dark[i]) * heat) for i in range(3))
            gold_color = tuple(int(dark[i] + ((255, 211, 116)[i] - dark[i]) * heat) for i in range(3))
            core_color = tuple(int(dark[i] + ((255, 249, 225)[i] - dark[i]) * heat) for i in range(3))
            pygame.draw.circle(self.screen, outer_color, center, outer_radius)
            pygame.draw.circle(self.screen, red_color, center, max(1, int(outer_radius * 0.82)))
            pygame.draw.circle(self.screen, orange_color, center, max(1, int(outer_radius * 0.61)))
            pygame.draw.circle(self.screen, gold_color, center, max(1, int(outer_radius * 0.37)))
            pygame.draw.circle(self.screen, core_color, center, max(1, int(outer_radius * 0.17)))
            if heat > 0.35:
                pygame.draw.circle(self.screen, (255, 192, 92), center, outer_radius, max(1, int(3 * scale * heat)))

        if progress < 0.9:
            debris_phase = min(1.0, progress / 0.9)
            debris_ease = 1.0 - (1.0 - debris_phase) ** 1.7
            debris_fade = max(0.0, 1.0 - debris_phase ** 1.35)
            reach = peak * (0.11 + 0.88 * debris_ease)
            count = 24
            for index in range(count):
                angle = seed + index * (math.tau / count) + math.sin(age * 2.7 + index * 1.9) * 0.025
                variation = 0.78 + 0.22 * math.sin(index * 2.37 + seed * 3.0)
                distance = reach * variation
                px = int(sx + math.cos(angle) * distance)
                py = int(sy + math.sin(angle) * distance)
                trail_length = max(2, int(peak * (0.018 + 0.035 * (1.0 - debris_phase))))
                tx = int(px - math.cos(angle) * trail_length)
                ty = int(py - math.sin(angle) * trail_length)
                ember = (255, int(95 + 125 * debris_fade), int(32 + 95 * debris_fade))
                hot_ember = (255, int(175 + 70 * debris_fade), int(120 + 100 * debris_fade))
                pygame.draw.line(self.screen, (105, 34, 16), (tx, ty), (px, py), max(2, int(4 * scale * debris_fade)))
                pygame.draw.line(self.screen, ember, (tx, ty), (px, py), max(1, int(2 * scale * debris_fade)))
                pygame.draw.circle(self.screen, hot_ember, (px, py), max(1, int(1.7 * scale * debris_fade)))

        if progress > 0.16:
            afterglow = max(0.0, 1.0 - (progress - 0.16) / 0.84)
            afterglow_radius = max(2, int(peak * (0.18 + 0.78 * min(1.0, progress / 0.5))))
            after_color = (int(65 + 110 * afterglow), int(22 + 38 * afterglow), int(18 + 18 * afterglow))
            pygame.draw.circle(self.screen, after_color, center, afterglow_radius, max(1, int(2 * scale * afterglow)))

    def _draw_hyperlanes(self, galaxy, player, camera, valid_targets):
        selected = player.selected_system_id
        zoom = camera['zoom']
        offset_x = camera['offset_x']
        offset_y = camera['offset_y']
        sw = self.screen.get_width()
        sh = self.screen.get_height()
        line_width = max(1, int((4 if selected is not None else 3) * zoom))

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
            if highlighted:
                pygame.draw.line(self.screen, (35, 75, 90), (first_x, first_y), (second_x, second_y), line_width + 4)
            pygame.draw.line(self.screen, color, (first_x, first_y), (second_x, second_y), line_width)
            if highlighted:
                pygame.draw.line(self.screen, (190, 230, 215), (first_x, first_y), (second_x, second_y), 1)

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

            if fleet.is_missile:
                self._draw_missile(galaxy, fleet, sx, sy, zoom)
                continue

            if len(fleet.route) > 1 and fleet.route_index < len(fleet.route):
                current_node = galaxy.systems[fleet.route[fleet.route_index - 1]]
                next_node = galaxy.systems[fleet.route[fleet.route_index]]
                direction = next_node.pos - current_node.pos
            else:
                direction = galaxy.systems[fleet.target_id].pos - position

            fleet_size = max(1, int(fleet.ships))
            base_size = 1.4 * (fleet_size ** 0.35)
            shape_size = min(base_size * zoom, 36)

            if direction.length_squared() > 0:
                direction = direction.normalize()
                perp = pygame.Vector2(-direction.y, direction.x)

                head_len = shape_size * 1.2
                tail_len = shape_size * 0.6
                half_width = shape_size * 0.4
                notch_depth = shape_size * 0.5

                tip_x = position.x + direction.x * head_len
                tip_y = position.y + direction.y * head_len
                left_x = position.x - direction.x * tail_len - perp.x * half_width
                left_y = position.y - direction.y * tail_len - perp.y * half_width
                notch_x = position.x - direction.x * (tail_len - notch_depth)
                notch_y = position.y - direction.y * (tail_len - notch_depth)
                right_x = position.x - direction.x * tail_len + perp.x * half_width
                right_y = position.y - direction.y * tail_len + perp.y * half_width

                points = [
                    (int(tip_x * zoom + offset_x), int(tip_y * zoom + offset_y)),
                    (int(left_x * zoom + offset_x), int(left_y * zoom + offset_y)),
                    (int(notch_x * zoom + offset_x), int(notch_y * zoom + offset_y)),
                    (int(right_x * zoom + offset_x), int(right_y * zoom + offset_y)),
                ]

                pygame.draw.polygon(self.screen, color, points)
                outline_color = (
                    min(255, color[0] + 50),
                    min(255, color[1] + 50),
                    min(255, color[2] + 50),
                )
                pygame.draw.polygon(self.screen, outline_color, points, 1)
                engine_len = max(3, int(shape_size * 0.9))
                engine_end = (
                    int((position.x - direction.x * (tail_len + engine_len)) * zoom + offset_x),
                    int((position.y - direction.y * (tail_len + engine_len)) * zoom + offset_y),
                )
                engine_start = (
                    int((position.x - direction.x * tail_len) * zoom + offset_x),
                    int((position.y - direction.y * tail_len) * zoom + offset_y),
                )
                pygame.draw.line(self.screen, (70, 190, 255), engine_start, engine_end, max(2, int(shape_size * 0.32)))
                pygame.draw.line(self.screen, (205, 245, 255), engine_start, engine_end, max(1, int(shape_size * 0.12)))
                pygame.draw.circle(self.screen, (225, 245, 255), (sx, sy), max(1, int(shape_size * 0.13)))

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

    def _draw_command_ships(self, galaxy, player, camera):
        zoom = camera['zoom']
        for empire_id, ship in galaxy.command.ships.items():
            player_ship = empire_id == config.PLAYER_ID
            if not player_ship and not config.COMMAND_SHOW_ENEMY_CAPITALS:
                continue
            center = (
                int(ship.position.x * zoom + camera['offset_x']),
                int(ship.position.y * zoom + camera['offset_y']),
            )
            if not (-80 <= center[0] <= self.screen.get_width() + 80 and -80 <= center[1] <= self.screen.get_height() + 80):
                continue
            size = max(6, min(18, int(10 * zoom)))
            color = galaxy.empires[empire_id].color
            if sum(color) < 180:
                color = config.COMMAND_DARK_EMPIRE_MARKER_COLOR
            ring_radius = size + (8 if ship.system_id is not None else 4)
            pygame.draw.circle(self.screen, color, center, ring_radius, 2 if ship.system_id is not None else 1)
            points = [
                (center[0], center[1] - size),
                (center[0] + size, center[1]),
                (center[0], center[1] + size),
                (center[0] - size, center[1]),
            ]
            pygame.draw.polygon(self.screen, color, points)
            pygame.draw.polygon(self.screen, config.BACKGROUND, points, 2)
            if player_ship:
                escorts = galaxy.empires[empire_id].escorts
                if escorts >= 1.0:
                    self._draw_escort_badge(center, escorts, ring_radius, zoom)
            if config.COMMAND_SHOW_ENEMY_CAPITALS:
                label_text = "CAPITAL" if ship.system_id is not None else "COMMAND SHIP"
                label = self.small_font.render(label_text, True, color)
                label_pos = label.get_rect(midbottom=(center[0], center[1] - ring_radius - 5))
                panel = label_pos.inflate(8, 4)
                pygame.draw.rect(self.screen, config.PANEL, panel, border_radius=3)
                self.screen.blit(label, label_pos)

    def _draw_escort_badge(self, center, escorts: float, ring_radius: int, zoom: float) -> None:
        pulse = int(math.sin(self.warn_flash_phase * 4.0) * 2)
        shield_radius = ring_radius + max(4, int(4 * zoom)) + pulse
        pygame.draw.circle(self.screen, config.VALID_TARGET_COLOR, center, shield_radius, 2)

        label_text = f"ESC {escorts:.0f}"
        label = self._escort_label_cache.get(label_text)
        if label is None:
            label = self.small_font.render(label_text, True, config.TEXT)
            self._escort_label_cache[label_text] = label

        label_pos = label.get_rect(midbottom=(center[0], center[1] - shield_radius - 4))
        panel = label_pos.inflate(10, 5)
        panel_bg = pygame.Surface((panel.width, panel.height), pygame.SRCALPHA)
        panel_bg.fill((*config.PANEL, 210))
        pygame.draw.rect(panel_bg, (*config.VALID_TARGET_COLOR, 230), panel_bg.get_rect(), 1, border_radius=3)
        self.screen.blit(panel_bg, panel.topleft)
        self.screen.blit(label, label_pos)

    def _draw_missile(self, galaxy, fleet, sx: int, sy: int, zoom: float) -> None:
        pulse = (math.sin(self.warn_flash_phase * 12.0) + 1.0) * 0.5
        scale = max(0.7, min(1.7, zoom))
        direction = pygame.Vector2(1.0, 0.0)
        if len(fleet.route) > 1 and fleet.route_index < len(fleet.route):
            current_node = galaxy.systems[fleet.route[fleet.route_index - 1]]
            next_node = galaxy.systems[fleet.route[fleet.route_index]]
            direction = next_node.pos - current_node.pos
            if direction.length_squared() > 0.0:
                direction = direction.normalize()
        dx = direction.x
        dy = direction.y
        px = -dy
        py = dx
        trail_len = (34.0 + pulse * 10.0) * scale
        trail_start = (int(sx - dx * trail_len), int(sy - dy * trail_len))
        trail_end = (int(sx - dx * trail_len * 0.18), int(sy - dy * trail_len * 0.18))
        pygame.draw.line(self.screen, (65, 19, 18), trail_start, (sx, sy), max(7, int(10 * scale)))
        pygame.draw.line(self.screen, (175, 43, 19), trail_start, (sx, sy), max(5, int(7 * scale)))
        pygame.draw.line(self.screen, (255, 92, 27), trail_start, (sx, sy), max(3, int(4 * scale)))
        pygame.draw.line(self.screen, (255, 207, 126), trail_start, trail_end, max(1, int(2 * scale)))
        for index in range(3):
            offset = trail_len * (0.34 + index * 0.19)
            plume_center = (int(sx - dx * offset), int(sy - dy * offset))
            plume_radius = max(1, int((4 - index) * scale * (0.7 + pulse * 0.3)))
            pygame.draw.circle(self.screen, (255, 83 + index * 25, 25), plume_center, plume_radius)
        halo_radius = max(7, int((9 + pulse * 3) * scale))
        pygame.draw.circle(self.screen, (100, 25, 17), (sx, sy), halo_radius + 4)
        pygame.draw.circle(self.screen, (255, 72, 27), (sx, sy), halo_radius, max(1, int(2 * scale)))
        tip = (int(sx + dx * 7 * scale), int(sy + dy * 7 * scale))
        rear = (int(sx - dx * 6 * scale), int(sy - dy * 6 * scale))
        side_a = (int(sx + px * 4 * scale), int(sy + py * 4 * scale))
        side_b = (int(sx - px * 4 * scale), int(sy - py * 4 * scale))
        pygame.draw.polygon(self.screen, (255, 112, 42), (tip, side_a, rear, side_b))
        pygame.draw.polygon(self.screen, (255, 231, 178), (tip, (int(sx + px * 1.5 * scale), int(sy + py * 1.5 * scale)), rear, (int(sx - px * 1.5 * scale), int(sy - py * 1.5 * scale))))
        pygame.draw.circle(self.screen, (255, 255, 242), (sx, sy), max(2, int(2.5 * scale)))
        if self._missile_label is not None and self._missile_label_bg is not None:
            lx = sx - self._missile_label.get_width() // 2
            ly = sy + halo_radius + 5
            self.screen.blit(self._missile_label_bg, (lx - 4, ly - 3))
            self.screen.blit(self._missile_label, (lx, ly))

    def _draw_missile_warnings(self, galaxy, camera) -> None:
        missiles = [fleet for fleet in galaxy.fleets if fleet.is_missile]
        if not missiles:
            return

        zoom = camera['zoom']
        offset_x = camera['offset_x']
        offset_y = camera['offset_y']
        blink = (math.sin(self.warn_flash_phase * 8.0) + 1.0) * 0.5

        for missile in missiles:
            target = galaxy.systems[missile.target_id]
            target_x = target.pos.x * zoom + offset_x
            target_y = target.pos.y * zoom + offset_y
            ring_radius = int((30 + math.sin(self.warn_flash_phase * 5.0) * 6) * max(1.0, zoom * 0.5))
            pygame.draw.circle(self.screen, (255, 60, 40), (int(target_x), int(target_y)), ring_radius, 2)
            cross_half = ring_radius // 2
            tx = int(target_x)
            ty = int(target_y)
            pygame.draw.line(self.screen, (255, 60, 40), (tx - cross_half, ty - cross_half), (tx + cross_half, ty + cross_half), 2)
            pygame.draw.line(self.screen, (255, 60, 40), (tx - cross_half, ty + cross_half), (tx + cross_half, ty - cross_half), 2)

        sw = self.screen.get_width()
        flash = int(200 + 55 * blink)
        warn_color = (flash, int(60 * blink), int(40 * blink))
        first = missiles[0]
        launcher_name = galaxy.empires[first.owner_id].name
        target_name = galaxy.systems[first.target_id].name
        extra = f"  (+{len(missiles) - 1} more)" if len(missiles) > 1 else ""
        warn_text = f"NUCLEAR LAUNCH DETECTED: {launcher_name} targeting {target_name}{extra}"
        banner = self.font.render(warn_text, True, warn_color)
        bg_rect = banner.get_rect()
        bg_rect.centerx = sw // 2
        bg_rect.top = config.TOP_BAR_HEIGHT + 6
        bg = pygame.Surface((bg_rect.width + 24, bg_rect.height + 10), pygame.SRCALPHA)
        bg.fill((40, 0, 0, 200))
        self.screen.blit(bg, (bg_rect.x - 12, bg_rect.y - 5))
        self.screen.blit(banner, bg_rect)

    def _draw_nuke_target_preview(self, galaxy, player, camera) -> None:
        if not getattr(player, "nuke_targeting", False):
            return
        hovered_id = player.hovered_system_id
        if hovered_id is None:
            return
        system = galaxy.systems[hovered_id]

        zoom = camera['zoom']
        offset_x = camera['offset_x']
        offset_y = camera['offset_y']
        sx = int(system.pos.x * zoom + offset_x)
        sy = int(system.pos.y * zoom + offset_y)
        radius = int(config.NUCLEAR_EFFECT_RADIUS * zoom)

        pulse = (math.sin(self.warn_flash_phase * 6.0) + 1.0) * 0.5
        color = (255, 80 + int(60 * pulse), 60)

        sw = self.screen.get_width()
        sh = self.screen.get_height()
        if sx < -radius - 50 or sx > sw + radius + 50:
            return
        if sy < -radius - 50 or sy > sh + radius + 50:
            return

        if radius > 2:
            pygame.draw.circle(self.screen, color, (sx, sy), radius, 3)

            affected = sum(
                1
                for other in galaxy.systems
                if other.pos.distance_to(system.pos) < config.NUCLEAR_EFFECT_RADIUS
            )
            label = self.small_font.render(
                f"{affected} system{'s' if affected != 1 else ''} in blast",
                True,
                color,
            )
            bg = pygame.Surface((label.get_width() + 8, label.get_height() + 4), pygame.SRCALPHA)
            bg.fill((0, 0, 0, 170))
            ly = sy - radius - label.get_height() - 12
            if ly < config.TOP_BAR_HEIGHT + 4:
                ly = sy + radius + 8
            self.screen.blit(bg, (sx - label.get_width() // 2 - 4, ly - 2))
            self.screen.blit(label, (sx - label.get_width() // 2, ly))

    def _draw_combat_shots(self, galaxy, camera):
        zoom = camera['zoom']
        offset_x = camera['offset_x']
        offset_y = camera['offset_y']
        sw = self.screen.get_width()
        sh = self.screen.get_height()
        scale = max(0.65, min(1.7, zoom))
        tail_length_scale = max(0.85, min(1.3, zoom))

        for shot in galaxy.combat_shots:
            progress = 1.0 - shot.lifetime / shot.max_lifetime
            progress = min(1.0, max(0.0, progress))
            start_x = shot.start.x * zoom + offset_x
            start_y = shot.start.y * zoom + offset_y
            delta_x = (shot.end.x - shot.start.x) * zoom
            delta_y = (shot.end.y - shot.start.y) * zoom
            path_length = math.hypot(delta_x, delta_y)
            if path_length < 0.5:
                continue
            direction_x = delta_x / path_length
            direction_y = delta_y / path_length
            head_x = start_x + delta_x * progress
            head_y = start_y + delta_y * progress
            tail_length = min(38.0, max(14.0, path_length * 0.16)) * tail_length_scale
            tail_x = head_x - direction_x * tail_length
            tail_y = head_y - direction_y * tail_length
            if head_x < -tail_length - 24 or head_x > sw + tail_length + 24:
                continue
            if head_y < -tail_length - 24 or head_y > sh + tail_length + 24:
                continue

            fade = max(0.38, 1.0 - progress * 0.28)
            color = tuple(max(0, min(255, int(channel * fade))) for channel in shot.color)
            hot_color = tuple(max(0, min(255, int(channel * 0.58 + 255 * 0.42))) for channel in color)
            dark_color = tuple(max(0, min(255, int(channel * 0.34))) for channel in color)
            radius = max(1.5, 2.5 * scale)
            tail = (int(tail_x), int(tail_y))
            head = (int(head_x), int(head_y))
            pygame.draw.line(self.screen, dark_color, tail, head, max(4, int(7 * scale)))
            pygame.draw.line(self.screen, color, tail, head, max(2, int(4 * scale)))
            pygame.draw.line(self.screen, hot_color, tail, head, max(1, int(2 * scale)))
            pygame.draw.circle(self.screen, color, head, max(3, int(radius * 1.8)))
            pygame.draw.circle(self.screen, (255, 255, 245), head, max(1, int(radius * 0.68)))

            perpendicular_x = -direction_y
            perpendicular_y = direction_x
            nose = (int(head_x + direction_x * radius * 2.2), int(head_y + direction_y * radius * 2.2))
            rear = (int(head_x - direction_x * radius * 1.6), int(head_y - direction_y * radius * 1.6))
            wing_a = (int(head_x + perpendicular_x * radius * 1.05), int(head_y + perpendicular_y * radius * 1.05))
            wing_b = (int(head_x - perpendicular_x * radius * 1.05), int(head_y - perpendicular_y * radius * 1.05))
            pygame.draw.polygon(self.screen, hot_color, (nose, wing_a, rear, wing_b))
            inner_a = (int(head_x + perpendicular_x * radius * 0.42), int(head_y + perpendicular_y * radius * 0.42))
            inner_b = (int(head_x - perpendicular_x * radius * 0.42), int(head_y - perpendicular_y * radius * 0.42))
            pygame.draw.polygon(self.screen, (255, 255, 250), (nose, inner_a, rear, inner_b))

    def _draw_combat_impacts(self, galaxy, camera):
        zoom = camera['zoom']
        offset_x = camera['offset_x']
        offset_y = camera['offset_y']
        screen_width = self.screen.get_width()
        screen_height = self.screen.get_height()
        scale = max(0.65, min(1.7, zoom))
        background = config.BACKGROUND
        for impact in galaxy.combat_impacts:
            progress = min(1.0, max(0.0, impact.age / impact.max_age))
            fade = (1.0 - progress) ** 1.7
            if fade <= 0.0:
                continue
            sx = int(impact.pos.x * zoom + offset_x)
            sy = int(impact.pos.y * zoom + offset_y)
            if sx < -44 or sx > screen_width + 44 or sy < -44 or sy > screen_height + 44:
                continue
            ease = 1.0 - (1.0 - progress) ** 2.2
            radius = max(2, int((4.0 + 19.0 * ease) * scale))
            base = impact.color
            ring_color = tuple(
                max(0, min(255, int(background[channel] + (base[channel] - background[channel]) * fade)))
                for channel in range(3)
            )
            hot_color = tuple(
                max(0, min(255, int(background[channel] + ((base[channel] * 0.45 + 255 * 0.55) - background[channel]) * fade)))
                for channel in range(3)
            )
            core_fade = max(0.0, 1.0 - progress / 0.62)
            core_color = tuple(
                max(0, min(255, int(background[channel] + (255 - background[channel]) * core_fade)))
                for channel in range(3)
            )
            pygame.draw.circle(self.screen, ring_color, (sx, sy), radius, max(1, int(2.4 * scale * fade)))
            inner_radius = max(1, int(radius * 0.58))
            pygame.draw.circle(self.screen, hot_color, (sx, sy), inner_radius, max(1, int(1.5 * scale * fade)))
            if core_fade > 0.0:
                pygame.draw.circle(self.screen, hot_color, (sx, sy), max(2, int((5.0 - 2.5 * progress) * scale)))
                pygame.draw.circle(self.screen, core_color, (sx, sy), max(1, int(2.0 * scale * core_fade)))
            for ray in range(8):
                angle = ray * (math.tau / 8.0) + impact.age * (2.2 if ray % 2 else -1.7)
                length = (5.0 + (ray % 3) * 2.2) * scale * fade
                inner = max(1.0, radius * 0.34)
                x1 = int(sx + math.cos(angle) * inner)
                y1 = int(sy + math.sin(angle) * inner)
                x2 = int(sx + math.cos(angle) * (inner + length))
                y2 = int(sy + math.sin(angle) * (inner + length))
                pygame.draw.line(self.screen, ring_color, (x1, y1), (x2, y2), max(1, int(2.0 * scale * fade)))

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
            if player.command_mode and system.id in valid_targets:
                pygame.draw.circle(self.screen, config.COMMAND_SHIP_COLOR, (sx, sy), int(radius + 15 * zoom), 2)
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
            halo = max(dr + 3, int((dr + 7) * max(0.7, zoom)))
            pygame.draw.circle(self.screen, tuple(int(channel * 0.42) for channel in color), (sx, sy), halo, 1)
            pygame.draw.circle(self.screen, config.STAR_CORE_COLOR, (sx, sy), dr + int(2 * zoom))
            pygame.draw.circle(self.screen, color, (sx, sy), dr)
            label = self._get_ship_label(font_size, str(int(system.ships)))
            self.screen.blit(label, (sx + dr + 5, sy - 8))

    def _reachable_count(self, galaxy: Galaxy, system_id: int) -> int:
        if self._reachable_galaxy is not galaxy:
            self._reachable_galaxy = galaxy
            self._reachable_counts = {}
        count = self._reachable_counts.get(system_id)
        if count is None:
            count = len(galaxy.reachable_system_ids(system_id))
            self._reachable_counts[system_id] = count
        return count

    def _tooltip_lines(self, galaxy, system) -> list[str]:
        if system.owner_id is None:
            owner_name = "Unclaimed"
        else:
            owner_name = galaxy.empires[system.owner_id].name
        reachable = self._reachable_count(galaxy, system.id)
        lines = [
            system.name,
            f"Owner: {owner_name}",
            f"Ships: {int(system.ships)}",
            f"Production: {system.production:.2f}/s",
            f"Gun range: {gun_range(system):.0f}",
            f"Hyperlanes: {len(galaxy.neighbors[system.id])}",
            f"Reachable systems: {reachable}",
        ]
        if system.owner_id is not None and galaxy.command.capital(system.owner_id) == system.id:
            if system.owner_id == config.PLAYER_ID and not galaxy.player_succession_complete:
                lines.append("YOUR CAPITAL - Command ship docked")
            elif system.owner_id == config.PLAYER_ID:
                lines.append("FORMER CAPITAL - Command ship docked")
            elif config.COMMAND_SHOW_ENEMY_CAPITALS:
                lines.append("CAPITAL - Command ship docked (testing)")
        return lines

    def _draw_hover_tooltip(self, galaxy, player) -> None:
        hovered_id = player.hovered_system_id
        if hovered_id is None:
            return
        if self.popup.visible:
            return

        system = galaxy.systems[hovered_id]
        lines = self._tooltip_lines(galaxy, system)

        zoom = self.camera['zoom']
        offset_x = self.camera['offset_x']
        offset_y = self.camera['offset_y']
        anchor_x = int(system.pos.x * zoom + offset_x)
        anchor_y = int(system.pos.y * zoom + offset_y)

        sw = self.screen.get_width()
        sh = self.screen.get_height()
        bar_top = sh - int(ui.bottom_bar_height)

        if self._tooltip_label_font_key != self._font_size:
            self._tooltip_label_font_key = self._font_size
            self._tooltip_label_font = pygame.font.Font(None, self._font_size[0])
        if self._tooltip_font_key != self._font_size:
            self._tooltip_font_key = self._font_size
            self._tooltip_font = pygame.font.Font(None, self._font_size[1])

        title_font = self._tooltip_label_font
        body_font = self._tooltip_font

        surfaces = [
            title_font.render(lines[0], True, config.TEXT),
        ]
        surfaces.extend(
            body_font.render(line, True, config.MUTED_TEXT)
            for line in lines[1:]
        )

        pad = 10
        gap = 3
        width = max(surface.get_width() for surface in surfaces) + pad * 2
        height = sum(surface.get_height() for surface in surfaces) + gap * (len(surfaces) - 1) + pad * 2

        box_x = anchor_x + 18
        box_y = anchor_y - height // 2
        if box_x + width > sw - 8:
            box_x = anchor_x - 18 - width
        box_x = max(8, min(box_x, sw - width - 8))
        box_y = max(config.TOP_BAR_HEIGHT + 8, min(box_y, bar_top - height - 8))

        panel = pygame.Surface((width, height), pygame.SRCALPHA)
        panel.fill((*config.PANEL, 225))
        pygame.draw.rect(panel, (*config.LANE_HIGHLIGHT, 200), panel.get_rect(), 2, border_radius=8)
        self.screen.blit(panel, (box_x, box_y))

        cursor_y = box_y + pad
        for surface in surfaces:
            self.screen.blit(surface, (box_x + pad, cursor_y))
            cursor_y += surface.get_height() + gap

    def _fleet_order_label(self, player):
        if player.command_mode:
            return "L: COMMAND SHIP - right-click friendly system"
        if player.use_percent:
            return f"Fleet order: {player.send_percent}%"
        return (
            f"Fleet order: {player.send_count} ship"
            if player.send_count == 1
            else f"Fleet order: {player.send_count} ships"
        )

    def _happiness_label(self, happiness: float) -> tuple[str, tuple[int, int, int]]:
        if happiness >= 75.0:
            return ("joyful", (120, 230, 160))
        if happiness >= 60.0:
            return ("content", config.SELECTION_COLOR)
        if happiness >= config.HAPPINESS_REBELLION_THRESHOLD:
            return ("restless", (245, 185, 65))
        if happiness >= 20.0:
            return ("unrest", (245, 135, 70))
        return ("revolt imminent", (240, 80, 80))

    def _draw_top_bar(self, galaxy, player, paused, speed):
        sw = self.screen.get_width()
        pygame.draw.rect(self.screen, config.PANEL, (0, 0, sw, config.TOP_BAR_HEIGHT))
        pygame.draw.line(self.screen, config.LANE_COLOR, (0, config.TOP_BAR_HEIGHT - 1), (sw, config.TOP_BAR_HEIGHT - 1), 2)
        pygame.draw.line(self.screen, (35, 52, 82), (0, 1), (sw, 1), 1)
        state = "AI SPECTATOR" if galaxy.player_succession_complete else ("FLEETS: AI | COMMAND: YOU" if galaxy.autopilot else ("PAUSED" if paused or self.popup.visible else "RUNNING"))
        title = self.font.render("DOMINUS STELLARUM", True, config.TEXT)
        self.screen.blit(title, (18, 12))
        lockout = galaxy.empires[config.PLAYER_ID].command_lockout
        if lockout > 0.0:
            status_text = f"COMMAND DESTROYED - {lockout:.0f}s TO SUCCESSION - ORDERS DISABLED"
            status = self.small_font.render(status_text, True, (255, 120, 90))
        elif not galaxy.autopilot and getattr(player, "nuke_targeting", False):
            status_text = f"{state}   Speed {speed:g}x   NUCLEAR STRIKE ARMED — right-click target, N to disarm"
            status = self.small_font.render(status_text, True, (255, 120, 90))
        else:
            status = self.small_font.render(f"{state}   Speed {speed:g}x   {self._fleet_order_label(player)}", True, config.SELECTION_COLOR if galaxy.autopilot else config.MUTED_TEXT)
        self.screen.blit(status, (18, 39))
        player_empire = galaxy.empires[config.PLAYER_ID]
        player_systems = galaxy.empire_system_count(config.PLAYER_ID)
        player_ships = int(galaxy.empire_ship_count(config.PLAYER_ID))
        player_missiles = player_empire.missiles_remaining
        player_escorts = int(player_empire.escorts)
        mood, mood_color = self._happiness_label(player_empire.happiness)
        stats = self.small_font.render(
            f"{'Former empire' if galaxy.player_succession_complete else 'Your empire'}: {player_systems} systems    Ships: {player_ships}    Missiles: {player_missiles}    Escorts: {player_escorts}",
            True,
            player_empire.color,
        )
        self.screen.blit(stats, stats.get_rect(midtop=(sw // 2, 14)))
        mood_surface = self.small_font.render(
            f"Happiness: {int(player_empire.happiness)}% ({mood})",
            True,
            mood_color,
        )
        self.screen.blit(mood_surface, mood_surface.get_rect(midtop=(sw // 2, 40)))

    def _draw_bottom_bar(self, galaxy, player):
        sh = self.screen.get_height()
        sw = self.screen.get_width()
        bar_height = int(ui.bottom_bar_height)
        bottom_y = sh - bar_height

        pygame.draw.rect(self.screen, config.PANEL, (0, bottom_y, sw, bar_height))
        pygame.draw.line(self.screen, (35, 52, 82), (0, bottom_y + 1), (sw, bottom_y + 1), 1)

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

        empire_count = sum(1 for empire in galaxy.empires if empire.alive)
        empire_row_h = max(8, available // (empire_count + 1))

        if self._bottom_font_key != (empire_row_h, empire_count):
            self._bottom_font_key = (empire_row_h, empire_count)
            self._empire_row_font = self._fit_font(empire_row_h, "1. Terran Union [YOU]  123 sys  99999 ships")
            self._empire_title_font = self._fit_font(empire_row_h, "GALACTIC POWERS")

        if player.message:
            message = self.small_font.render(player.message, True, config.SELECTION_COLOR)
            self.screen.blit(message, message.get_rect(midbottom=(sw // 2, bottom_y - 6)))

        self._draw_empire_panel(galaxy, bottom_y, pad_top, empire_row_h, self._empire_title_font, self._empire_row_font)

    def _draw_empire_panel(self, galaxy, y, pad_top, row_height, title_font, row_font):
        left_margin = 18
        cursor_y = y + pad_top

        ranked = sorted(
            (empire for empire in galaxy.empires if empire.alive),
            key=lambda empire: galaxy.empire_strength(empire.id),
            reverse=True,
        )

        heading = title_font.render("GALACTIC POWERS", True, config.TEXT)
        self.screen.blit(heading, heading.get_rect(midleft=(left_margin, cursor_y)))
        cursor_y += row_height

        self._empire_row_rects = []
        hit_width = min(self._empire_row_hit_width, self.screen.get_width() - left_margin - 36)

        for rank, empire in enumerate(ranked, start=1):
            systems = galaxy.empire_system_count(empire.id)
            ships = int(galaxy.empire_ship_count(empire.id))
            color = empire.color
            marker = "YOU" if empire.is_player else "AI"
            if empire.command_lockout > 0.0:
                marker += " DISABLED"
            autopilot_tag = " [AUTO]" if empire.is_player and galaxy.autopilot else ""
            text = f"{rank}. {empire.name} [{marker}]{autopilot_tag}  {systems} sys  {ships} ships"
            surface = row_font.render(text, True, color)
            self.screen.blit(surface, surface.get_rect(midleft=(left_margin, cursor_y)))
            row_rect = pygame.Rect(left_margin, cursor_y, hit_width, row_height)
            self._empire_row_rects.append((row_rect, empire))
            cursor_y += row_height

    def _draw_camera_info(self, camera):
        bar_top = self.screen.get_height() - int(ui.bottom_bar_height)
        info_text = self.tiny_font.render(f"Zoom: {camera['zoom']:.2f}x", True, config.MUTED_TEXT)
        self.screen.blit(info_text, (self.screen.get_width() - info_text.get_width() - 18, bar_top - 24))

    def _draw_game_state(self, galaxy):
        winner = galaxy.winner()
        if winner is not None and winner.command_lockout > 0.0:
            return
        if galaxy.player_won():
            self._draw_end_screen("VICTORY", "You control the galaxy. Press R to start anew.")
        elif winner is not None and winner.id == config.PLAYER_ID and galaxy.player_succession_complete:
            self._draw_end_screen("YOU LOST!", "You died! Your empire conquered the galaxy without you. Press R to try again.")
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
