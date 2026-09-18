import math

import pygame

from . import config
from .galaxy import Galaxy
from .player import PlayerController


class Renderer:
    def __init__(
        self,
        screen: pygame.Surface,
    ):
        self.screen = screen

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

    def draw(
        self,
        galaxy: Galaxy,
        player: PlayerController,
        paused: bool,
        speed: float,
    ) -> None:
        self.screen.fill(
            config.BACKGROUND
        )

        self._draw_background_stars(
            galaxy
        )

        self._draw_hyperlanes(
            galaxy,
            player,
        )

        self._draw_defender_orbits(
            galaxy
        )

        self._draw_fleets(
            galaxy
        )

        self._draw_combat_shots(
            galaxy
        )

        self._draw_systems(
            galaxy,
            player,
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

        self._draw_game_state(
            galaxy
        )

    def _draw_background_stars(
        self,
        galaxy: Galaxy,
    ) -> None:
        rng = galaxy.rng
        state = rng.getstate()
        rng.seed(12345)

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
    ) -> None:
        selected = player.selected_system_id
        valid_targets = player.valid_target_ids()

        for first_id, second_id in galaxy.edges:
            first = galaxy.systems[first_id]
            second = galaxy.systems[second_id]

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
                first.pos,
                second.pos,
                3 if highlighted else 1,
            )

    def _draw_defender_orbits(
        self,
        galaxy: Galaxy,
    ) -> None:
        current_time = (
            pygame.time.get_ticks()
            / 1000.0
        )

        for system in galaxy.systems:
            if system.owner_id is None:
                continue

            empire = galaxy.empires[
                system.owner_id
            ]

            orbit_color = (
                empire.color[0] // 3,
                empire.color[1] // 3,
                empire.color[2] // 3,
            )

            pygame.draw.circle(
                self.screen,
                orbit_color,
                system.pos,
                int(
                    config.DEFENDER_ORBIT_RADIUS
                ),
                1,
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

                pygame.draw.circle(
                    self.screen,
                    empire.color,
                    position,
                    3,
                )

                pygame.draw.circle(
                    self.screen,
                    config.STAR_CORE_COLOR,
                    position,
                    4,
                    1,
                )

    def _draw_fleets(self, galaxy: Galaxy) -> None:
        for fleet in galaxy.fleets:
            position = fleet.position
            target = galaxy.systems[fleet.target_id]
            color = galaxy.empires[fleet.owner_id].color
            
            # Draw trailing effect
            trail_length = min(15, int(fleet.ships))
            for i in range(trail_length):
                alpha = (255 - i * 15) // max(1, trail_length)
                trail_pos = position.lerp(
                    target.pos,
                    min(1.0, (i + fleet.segment_progress) / max(1, trail_length + 1))
                )
                
                faded_color = tuple(
                    min(255, c + (255 - c) * (alpha / 255))
                    for c in color
                )
                
                trail_radius = max(2, 5 - i // 4)
                pygame.draw.circle(
                    self.screen,
                    faded_color,
                    trail_pos,
                    trail_radius,
                )
            
            # Main fleet ship
            pygame.draw.circle(
                self.screen,
                color,
                position,
                6,
            )
            
            # Direction indicator
            direction = target.pos - position
            
            if direction.length_squared() > 0:
                direction = direction.normalize()
                perpendicular = pygame.Vector2(-direction.y, direction.x)
                
                tip = position + direction * 12
                left = position - direction * 6 + perpendicular * 6
                right = position - direction * 6 - perpendicular * 6
                
                pygame.draw.polygon(
                    self.screen,
                    color,
                    [tip, left, right],
                )
            
            # Ship count on fleet
            label = self.tiny_font.render(
                str(int(fleet.ships)),
                True,
                config.TEXT,
            )
            
            self.screen.blit(
                label,
                (position.x + 10, position.y - 10),
            )

    def _draw_combat_shots(
        self,
        galaxy: Galaxy,
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

            pygame.draw.line(
                self.screen,
                color,
                shot.start,
                shot.end,
                3,
            )

            pygame.draw.circle(
                self.screen,
                config.STAR_CORE_COLOR,
                shot.end,
                3,
            )

    def _draw_systems(self, galaxy: Galaxy, player: PlayerController) -> None:
        valid_targets = player.valid_target_ids()
        
        # Pulsing effect timing
        pulse_phase = pygame.time.get_ticks() / 500.0
        
        for system in galaxy.systems:
            if system.owner_id is None:
                color = config.NEUTRAL_COLOR
                radius = config.STAR_RADIUS
            else:
                color = galaxy.empires[system.owner_id].color
                radius = config.OWNED_STAR_RADIUS
            
            # Pulse effect for owned systems
            if system.owner_id is not None:
                pulse_offset = int(math.sin(pulse_phase + system.id) * 2)
                display_radius = radius + pulse_offset
            else:
                display_radius = radius
            
            # Valid target indicator
            if system.id in valid_targets:
                glow_radius = radius + 10 + int(math.sin(pulse_phase * 2) * 3)
                pygame.draw.circle(
                    self.screen,
                    config.VALID_TARGET_COLOR,
                    system.pos,
                    glow_radius,
                    2,
                )
            
            # Hover highlight
            if system.id == player.hovered_system_id:
                pygame.draw.circle(
                    self.screen,
                    (190, 200, 220),
                    system.pos,
                    radius + 6,
                    2,
                )
            
            # Selection ring with animation
            if system.id == player.selected_system_id:
                selection_size = radius + 12 + int(math.sin(pulse_phase * 1.5) * 2)
                pygame.draw.circle(
                    self.screen,
                    config.SELECTION_COLOR,
                    system.pos,
                    selection_size,
                    3,
                )
            
            # Star core
            pygame.draw.circle(
                self.screen,
                config.STAR_CORE_COLOR,
                system.pos,
                display_radius + 2,
            )
            
            # Main system body
            pygame.draw.circle(
                self.screen,
                color,
                system.pos,
                display_radius,
            )
            
            # Ship count label
            ship_text = self.small_font.render(
                str(int(system.ships)),
                True,
                config.TEXT,
            )
            
            self.screen.blit(
                ship_text,
                (
                    system.pos.x + display_radius + 5,
                    system.pos.y - 8,
                ),
            )

    def _draw_top_bar(
        self,
        galaxy: Galaxy,
        player: PlayerController,
        paused: bool,
        speed: float,
    ) -> None:
        pygame.draw.rect(
            self.screen,
            config.PANEL,
            (
                0,
                0,
                config.WIDTH,
                config.TOP_BAR_HEIGHT,
            ),
        )

        state = (
            "PAUSED"
            if paused
            else "RUNNING"
        )

        title = self.font.render(
            "DOMINUS STELLARUM",
            True,
            config.TEXT,
        )

        self.screen.blit(
            title,
            (18, 12),
        )

        status = self.small_font.render(
            (
                f"{state}   "
                f"Speed {speed:g}x   "
                f"Send {player.send_percent}%"
            ),
            True,
            config.MUTED_TEXT,
        )

        self.screen.blit(
            status,
            (18, 39),
        )

        player_systems = (
            galaxy.empire_system_count(
                config.PLAYER_ID
            )
        )

        player_ships = int(
            galaxy.empire_ship_count(
                config.PLAYER_ID
            )
        )

        stats = self.small_font.render(
            (
                f"Your systems: "
                f"{player_systems}    "
                f"Your ships: "
                f"{player_ships}"
            ),
            True,
            galaxy.empires[
                config.PLAYER_ID
            ].color,
        )

        self.screen.blit(
            stats,
            stats.get_rect(
                midtop=(
                    config.WIDTH // 2,
                    14,
                )
            ),
        )

        controls = self.tiny_font.render(
            (
                "Left click: select   "
                "Right click: send along hyperlanes   "
                "Wheel: fleet %   "
                "Space: pause   "
                "+/-: speed   "
                "R: new game"
            ),
            True,
            config.MUTED_TEXT,
        )

        self.screen.blit(
            controls,
            controls.get_rect(
                midtop=(
                    config.WIDTH // 2,
                    40,
                )
            ),
        )

    def _draw_bottom_bar(
        self,
        galaxy: Galaxy,
        player: PlayerController,
    ) -> None:
        y = (
            config.HEIGHT
            - config.BOTTOM_BAR_HEIGHT
        )

        pygame.draw.rect(
            self.screen,
            config.PANEL,
            (
                0,
                y,
                config.WIDTH,
                config.BOTTOM_BAR_HEIGHT,
            ),
        )

        pygame.draw.line(
            self.screen,
            config.LANE_COLOR,
            (0, y),
            (config.WIDTH, y),
            2,
        )

        self._draw_selection_panel(
            galaxy,
            player,
            y,
        )

        self._draw_empire_panel(
            galaxy,
            y,
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
                        config.WIDTH // 2,
                        config.HEIGHT - 8,
                    )
                ),
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
        x = config.WIDTH - 320

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
                config.WIDTH,
                config.HEIGHT,
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
                    config.WIDTH // 2,
                    config.HEIGHT // 2 - 35,
                )
            ),
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
                    config.WIDTH // 2,
                    config.HEIGHT // 2 + 20,
                )
            ),
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
                    config.WIDTH // 2,
                    config.HEIGHT // 2 + 55,
                )
            ),
        )