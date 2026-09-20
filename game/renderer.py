import math

import pygame

from . import config
from .galaxy import Galaxy
from .player import PlayerController


class Renderer:
    def __init__(
        self,
        screen: pygame.Surface,
        camera: dict,
    ):
        self.screen = screen
        self.camera = camera

        self.font = pygame.font.Font(
            None,
            22,
        )

        self.small_font = pygame.font.Font(
            None,
            18,
        )

        self.tiny_font = pygame.font.Font(
            None,
            16,
        )

        self.huge_font = pygame.font.Font(
            None,
            64,
        )

    def world_to_screen(
        self,
        world_pos: pygame.Vector2,
    ) -> pygame.Vector2:
        """Convert world coordinates to screen coordinates."""
        return pygame.Vector2(
            world_pos.x * self.camera['zoom'] + self.camera['offset_x'],
            world_pos.y * self.camera['zoom'] + self.camera['offset_y'],
        )

    def screen_to_world(
        self,
        screen_pos: tuple[int, int],
    ) -> pygame.Vector2:
        """Convert screen coordinates to world coordinates."""
        return pygame.Vector2(
            (screen_pos[0] - self.camera['offset_x']) / self.camera['zoom'],
            (screen_pos[1] - self.camera['offset_y']) / self.camera['zoom'],
        )

    def draw(
        self,
        galaxy: Galaxy,
        player: PlayerController,
        paused: bool,
        speed: float,
        camera: dict,
    ) -> None:
        self.screen.fill(
            config.BACKGROUND
        )

        # Draw visible area border (optional indicator)
        self._draw_visible_area_border(camera)

        self._draw_background_stars(
            galaxy,
            camera
        )

        self._draw_hyperlanes(
            galaxy,
            player,
            camera
        )

        self._draw_defender_orbits(
            galaxy,
            camera
        )

        self._draw_fleets(
            galaxy,
            camera
        )

        self._draw_combat_shots(
            galaxy,
            camera
        )

        self._draw_systems(
            galaxy,
            player,
            camera
        )

        self._draw_top_bar(
            galaxy,
            player,
            paused,
            speed,
        )

        self._draw_bottom_bar(
            galaxy,
            player,
        )

        self._draw_camera_info(camera)

        self._draw_game_state(
            galaxy
        )

    def _draw_visible_area_border(
        self,
        camera: dict,
    ) -> None:
        """Draw a subtle border indicating visible viewport."""
        # This is optional - shows where screen edges are relative to galaxy
        width = self.screen.get_width()
        height = self.screen.get_height()
        
        # Only draw if zoomed in significantly
        if camera['zoom'] < 0.5:
            pygame.draw.rect(
                self.screen,
                (30, 40, 60),
                (0, config.TOP_BAR_HEIGHT, width, height - config.TOP_BAR_HEIGHT - config.BOTTOM_BAR_HEIGHT),
                1,
            )

    def _draw_background_stars(
        self,
        galaxy: Galaxy,
        camera: dict,
    ) -> None:
        rng = galaxy.rng
        state = rng.getstate()
        rng.seed(12345)

        # Only draw stars in visible area when zoomed in
        for _ in range(160):
            x = rng.randint(
                0,
                config.WIDTH - 1,
            )

            y = rng.randint(
                config.TOP_BAR_HEIGHT,
                config.HEIGHT
                - config.BOTTOM_BAR_HEIGHT,
            )

            brightness = rng.randint(35, 90)

            pygame.draw.circle(
                self.screen,
                (
                    brightness,
                    brightness,
                    brightness + 15,
                ),
                (x, y),
                1,
            )

        rng.setstate(state)

    def _draw_hyperlanes(
        self,
        galaxy: Galaxy,
        player: PlayerController,
        camera: dict,
    ) -> None:
        selected = player.selected_system_id
        valid_targets = player.valid_target_ids()

        for first_id, second_id in galaxy.edges:
            first = galaxy.systems[first_id]
            second = galaxy.systems[second_id]

            # Transform to screen coordinates
            first_screen = self.world_to_screen(first.pos)
            second_screen = self.world_to_screen(second.pos)

            highlighted = (
                selected is not None
                and (
                    (
                        first_id == selected
                        and second_id in valid_targets
                    )
                    or (
                        second_id == selected
                        and first_id in valid_targets
                    )
                )
            )

            pygame.draw.line(
                self.screen,
                (
                    config.LANE_HIGHLIGHT
                    if highlighted
                    else config.LANE_COLOR
                ),
                (first_screen.x, first_screen.y),
                (second_screen.x, second_screen.y),
                int(max(1, 3 if highlighted else 1)),
            )

    def _draw_defender_orbits(
        self,
        galaxy: Galaxy,
        camera: dict,
    ) -> None:
        current_time = (
            pygame.time.get_ticks()
            / 1000.0
        )

        # Scale orbit radius with zoom
        scaled_orbit_radius = config.DEFENDER_ORBIT_RADIUS * camera['zoom']

        for system in galaxy.systems:
            if system.owner_id is None:
                continue

            empire = galaxy.empires[
                system.owner_id
            ]

            system_screen = self.world_to_screen(system.pos)

            orbit_color = (
                empire.color[0] // 3,
                empire.color[1] // 3,
                empire.color[2] // 3,
            )

            pygame.draw.circle(
                self.screen,
                orbit_color,
                (int(system_screen.x), int(system_screen.y)),
                int(scaled_orbit_radius),
                int(max(1, 1)),
            )

            for index in range(
                config.DEFENDER_COUNT
            ):
                angle = (
                    current_time
                    * config.DEFENDER_ORBIT_SPEED
                    + (
                        index
                        * math.tau
                        / config.DEFENDER_COUNT
                    )
                )

                position = system.pos + pygame.Vector2(
                    math.cos(angle),
                    math.sin(angle),
                ) * config.DEFENDER_ORBIT_RADIUS

                position_screen = self.world_to_screen(position)

                pygame.draw.circle(
                    self.screen,
                    empire.color,
                    (int(position_screen.x), int(position_screen.y)),
                    int(max(2, 3 * camera['zoom'])),
                )

                pygame.draw.circle(
                    self.screen,
                    config.STAR_CORE_COLOR,
                    (int(position_screen.x), int(position_screen.y)),
                    int(max(2, 4 * camera['zoom'])),
                    int(max(1, 1)),
                )

    def _draw_fleets(
        self,
        galaxy: Galaxy,
        camera: dict,
    ) -> None:
        for fleet in galaxy.fleets:
            position = fleet.position
            target = galaxy.systems[fleet.target_id]
            color = galaxy.empires[fleet.owner_id].color
            
            position_screen = self.world_to_screen(position)
            target_screen = self.world_to_screen(target.pos)
            
            # Draw trailing effect
            trail_length = min(15, int(fleet.ships))
            for i in range(trail_length):
                alpha = (255 - i * 15) // max(1, trail_length)
                trail_pos = position.lerp(
                    target.pos,
                    min(1.0, (i + fleet.segment_progress) / max(1, trail_length + 1))
                )
                trail_pos_screen = self.world_to_screen(trail_pos)
                
                faded_color = tuple(
                    min(255, c + (255 - c) * (alpha / 255))
                    for c in color
                )
                
                trail_radius = max(2, int((5 - i // 4) * camera['zoom']))
                pygame.draw.circle(
                    self.screen,
                    faded_color,
                    (int(trail_pos_screen.x), int(trail_pos_screen.y)),
                    trail_radius,
                )
            
            # Main fleet ship
            pygame.draw.circle(
                self.screen,
                color,
                (int(position_screen.x), int(position_screen.y)),
                int(max(2, 6 * camera['zoom'])),
            )
            
            # Direction indicator
            direction = target.pos - position
            
            if direction.length_squared() > 0:
                direction = direction.normalize()
                perpendicular = pygame.Vector2(-direction.y, direction.x)
                
                tip = position + direction * 12
                left = position - direction * 6 + perpendicular * 6
                right = position - direction * 6 - perpendicular * 6
                
                tip_screen = self.world_to_screen(tip)
                left_screen = self.world_to_screen(left)
                right_screen = self.world_to_screen(right)
                
                pygame.draw.polygon(
                    self.screen,
                    color,
                    [
                        (int(tip_screen.x), int(tip_screen.y)),
                        (int(left_screen.x), int(left_screen.y)),
                        (int(right_screen.x), int(right_screen.y)),
                    ],
                )
            
            # Ship count on fleet
            label = self.tiny_font.render(
                str(int(fleet.ships)),
                True,
                config.TEXT,
            )
            
            self.screen.blit(
                label,
                (int(position_screen.x) + 10, int(position_screen.y) - 10),
            )

    def _draw_combat_shots(
        self,
        galaxy: Galaxy,
        camera: dict,
    ) -> None:
        for shot in galaxy.combat_shots:
            ratio = (
                shot.lifetime
                / shot.max_lifetime
            )

            ratio = max(
                0.0,
                min(1.0, ratio),
            )

            color = tuple(
                int(channel * ratio)
                for channel in shot.color
            )

            start_screen = self.world_to_screen(shot.start)
            end_screen = self.world_to_screen(shot.end)

            pygame.draw.line(
                self.screen,
                color,
                (start_screen.x, start_screen.y),
                (end_screen.x, end_screen.y),
                int(max(1, 3 * camera['zoom'])),
            )

            pygame.draw.circle(
                self.screen,
                config.STAR_CORE_COLOR,
                (int(end_screen.x), int(end_screen.y)),
                int(max(1, 3 * camera['zoom'])),
            )

    def _draw_systems(
        self,
        galaxy: Galaxy,
        player: PlayerController,
        camera: dict,
    ) -> None:
        valid_targets = player.valid_target_ids()
        
        # Pulsing effect timing
        pulse_phase = pygame.time.get_ticks() / 500.0
        
        # Scale radii with zoom
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
            
            # Pulse effect for owned systems
            if system.owner_id is not None:
                pulse_offset = int(math.sin(pulse_phase + system.id) * 2 * camera['zoom'])
                display_radius = radius + pulse_offset
            else:
                display_radius = radius
            
            # Valid target indicator
            if system.id in valid_targets:
                glow_radius = radius + 10 * camera['zoom'] + int(math.sin(pulse_phase * 2) * 3 * camera['zoom'])
                pygame.draw.circle(
                    self.screen,
                    config.VALID_TARGET_COLOR,
                    (int(system_screen.x), int(system_screen.y)),
                    int(glow_radius),
                    int(max(1, 2)),
                )
            
            # Hover highlight
            if system.id == player.hovered_system_id:
                pygame.draw.circle(
                    self.screen,
                    (190, 200, 220),
                    (int(system_screen.x), int(system_screen.y)),
                    int(radius + 6 * camera['zoom']),
                    int(max(1, 2)),
                )
            
            # Selection ring with animation
            if system.id == player.selected_system_id:
                selection_size = radius + 12 * camera['zoom'] + int(math.sin(pulse_phase * 1.5) * 2 * camera['zoom'])
                pygame.draw.circle(
                    self.screen,
                    config.SELECTION_COLOR,
                    (int(system_screen.x), int(system_screen.y)),
                    int(selection_size),
                    int(max(1, 3)),
                )
            
            # Star core
            pygame.draw.circle(
                self.screen,
                config.STAR_CORE_COLOR,
                (int(system_screen.x), int(system_screen.y)),
                int(display_radius + 2 * camera['zoom']),
            )
            
            # Main system body
            pygame.draw.circle(
                self.screen,
                color,
                (int(system_screen.x), int(system_screen.y)),
                int(display_radius),
            )
            
            # Ship count label (scale font size with zoom)
            font_scale = max(1, int(camera['zoom']))
            ship_text_font = pygame.font.Font(None, 18 * font_scale)
            ship_text = ship_text_font.render(
                str(int(system.ships)),
                True,
                config.TEXT,
            )
            
            self.screen.blit(
                ship_text,
                (
                    int(system_screen.x) + int(display_radius) + 5,
                    int(system_screen.y) - 8,
                ),
            )

    def _draw_top_bar(
        self,
        galaxy: Galaxy,
        player: PlayerController,
        paused: bool,
        speed: float,
    ) -> None:
        # Get actual screen dimensions (not hardcoded config)
        screen_width = self.screen.get_width()
        
        # Always drawn in screen coordinates
        pygame.draw.rect(
            self.screen,
            config.PANEL,
            (0, 0, screen_width, config.TOP_BAR_HEIGHT),
        )

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
        self.screen.blit(
            stats,
            stats.get_rect(midtop=(screen_width // 2, 14)),
        )

        controls_text = (
            "Left click: select   Right click: send   Wheel: zoom   "
            "MMB drag / Arrows: pan   Space: pause   +/-: speed   "
            "F: fullscreen   R: new game"
        )
        controls = self.tiny_font.render(controls_text, True, config.MUTED_TEXT)
        self.screen.blit(
            controls,
            controls.get_rect(midtop=(screen_width // 2, 40)),
        )

    def _draw_bottom_bar(
        self,
        galaxy: Galaxy,
        player: PlayerController,
    ) -> None:
        # Always drawn in screen coordinates (not affected by camera)
        screen_height = self.screen.get_height()
        bottom_y = screen_height - config.BOTTOM_BAR_HEIGHT

        pygame.draw.rect(
            self.screen,
            config.PANEL,
            (
                0,
                bottom_y,
                self.screen.get_width(),
                config.BOTTOM_BAR_HEIGHT,
            ),
        )

        pygame.draw.line(
            self.screen,
            config.LANE_COLOR,
            (0, bottom_y),
            (self.screen.get_width(), bottom_y),
            2,
        )

        self._draw_selection_panel(
            galaxy,
            player,
            bottom_y,
        )

        self._draw_empire_panel(
            galaxy,
            bottom_y,
        )

        if player.message:
            message = self.small_font.render(
                player.message,
                True,
                config.SELECTION_COLOR,
            )

            self.screen.blit(
                message,
                message.get_rect(
                    midbottom=(
                        self.screen.get_width() // 2,
                        screen_height - 8,
                    )
                )
            )

    def _draw_selection_panel(
        self,
        galaxy: Galaxy,
        player: PlayerController,
        y: int,
    ) -> None:
        selected_id = player.selected_system_id

        if selected_id is None:
            lines = [
                "No system selected",
                "Left-click one of your blue systems.",
                "Right-click a reachable system to send a fleet.",
            ]
        else:
            system = galaxy.systems[selected_id]

            reachable = len(
                galaxy.reachable_system_ids(
                    selected_id
                )
            )

            lines = [
                system.name,
                f"Ships: {int(system.ships)}",
                f"Production: {system.production:.2f}/s",
                (
                    f"Hyperlanes: "
                    f"{len(galaxy.neighbors[system.id])}"
                ),
                f"Reachable systems: {reachable}",
                f"Fleet order: {player.send_percent}%",
            ]

        for index, line in enumerate(lines):
            color = (
                config.TEXT
                if index == 0
                else config.MUTED_TEXT
            )

            font = (
                self.font
                if index == 0
                else self.small_font
            )

            surface = font.render(
                line,
                True,
                color,
            )

            self.screen.blit(
                surface,
                (
                    18,
                    y + 10 + index * 19,
                ),
            )

    def _draw_empire_panel(
        self,
        galaxy: Galaxy,
        y: int,
    ) -> None:
        x = self.screen.get_width() - 320

        heading = self.font.render(
            "GALACTIC POWERS",
            True,
            config.TEXT,
        )

        self.screen.blit(
            heading,
            (x, y + 12),
        )

        for index, empire in enumerate(
            galaxy.empires
        ):
            systems = (
                galaxy.empire_system_count(
                    empire.id
                )
            )

            ships = int(
                galaxy.empire_ship_count(
                    empire.id
                )
            )

            color = (
                empire.color
                if empire.alive
                else config.MUTED_TEXT
            )

            marker = (
                "YOU"
                if empire.is_player
                else "AI"
            )

            text = (
                f"{empire.name} [{marker}]  "
                f"{systems} systems  "
                f"{ships} ships"
            )

            surface = self.tiny_font.render(
                text,
                True,
                color,
            )

            self.screen.blit(
                surface,
                (
                    x,
                    y + 38 + index * 14,
                ),
            )

    def _draw_camera_info(
        self,
        camera: dict,
    ) -> None:
        """Display current camera position and zoom level."""
        info_text = self.tiny_font.render(
            f"Zoom: {camera['zoom']:.2f}x  |  Offset: ({int(camera['offset_x'])}, {int(camera['offset_y'])})",
            True,
            config.MUTED_TEXT,
        )

        self.screen.blit(
            info_text,
            (
                self.screen.get_width() - info_text.get_width() - 18,
                config.HEIGHT - config.BOTTOM_BAR_HEIGHT - 24,
            ),
        )

    def _draw_game_state(
        self,
        galaxy: Galaxy,
    ) -> None:
        if galaxy.player_won():
            self._draw_end_screen(
                "VICTORY",
                "You control the galaxy.",
                galaxy.empires[
                    config.PLAYER_ID
                ].color,
            )

        elif galaxy.player_defeated():
            self._draw_end_screen(
                "DEFEAT",
                "Your empire has fallen.",
                (230, 90, 90),
            )

    def _draw_end_screen(
        self,
        heading: str,
        subtitle: str,
        color: tuple[int, int, int],
    ) -> None:
        overlay = pygame.Surface(
            (
                self.screen.get_width(),
                self.screen.get_height(),
            ),
            pygame.SRCALPHA,
        )

        overlay.fill(
            (0, 0, 0, 175)
        )

        self.screen.blit(
            overlay,
            (0, 0),
        )

        title = self.huge_font.render(
            heading,
            True,
            color,
        )

        self.screen.blit(
            title,
            title.get_rect(
                center=(
                    self.screen.get_width() // 2,
                    self.screen.get_height() // 2 - 35,
                )
            )
        )

        description = self.font.render(
            subtitle,
            True,
            config.TEXT,
        )

        self.screen.blit(
            description,
            description.get_rect(
                center=(
                    self.screen.get_width() // 2,
                    self.screen.get_height() // 2 + 20,
                )
            )
        )

        restart = self.small_font.render(
            "Press R to start a new galaxy.",
            True,
            config.MUTED_TEXT,
        )

        self.screen.blit(
            restart,
            restart.get_rect(
                center=(
                    self.screen.get_width() // 2,
                    self.screen.get_height() // 2 + 55,
                )
            )
        )