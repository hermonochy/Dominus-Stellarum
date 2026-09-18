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

        self.large_font = pygame.font.Font(
            None,
            44,
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

            brightness = rng.randint(
                35,
                90,
            )

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
        selected = (
            player.selected_system_id
        )

        valid_targets = (
            player.valid_target_ids()
        )

        for first_id, second_id in galaxy.edges:
            first = galaxy.systems[
                first_id
            ]

            second = galaxy.systems[
                second_id
            ]

            highlighted = (
                selected is not None
                and (
                    (
                        first_id == selected
                        and second_id
                        in valid_targets
                    )
                    or (
                        second_id == selected
                        and first_id
                        in valid_targets
                    )
                )
            )

            color = (
                config.LANE_HIGHLIGHT
                if highlighted
                else config.LANE_COLOR
            )

            width = 3 if highlighted else 1

            pygame.draw.line(
                self.screen,
                color,
                first.pos,
                second.pos,
                width,
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
                max(0, empire.color[0] // 3),
                max(0, empire.color[1] // 3),
                max(0, empire.color[2] // 3),
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

                defender_position = (
                    system.pos
                    + pygame.Vector2(
                        math.cos(angle),
                        math.sin(angle),
                    )
                    * config.DEFENDER_ORBIT_RADIUS
                )

                pygame.draw.circle(
                    self.screen,
                    empire.color,
                    defender_position,
                    3,
                )

                pygame.draw.circle(
                    self.screen,
                    config.STAR_CORE_COLOR,
                    defender_position,
                    4,
                    1,
                )

    def _draw_fleets(
        self,
        galaxy: Galaxy,
    ) -> None:
        for fleet in galaxy.fleets:
            position = galaxy.fleet_position(
                fleet
            )

            target = galaxy.systems[
                fleet.target_id
            ]

            empire = galaxy.empires[
                fleet.owner_id
            ]

            pygame.draw.circle(
                self.screen,
                empire.color,
                position,
                5,
            )

            direction = target.pos - position

            if direction.length_squared() > 0:
                direction = direction.normalize()

                perpendicular = pygame.Vector2(
                    -direction.y,
                    direction.x,
                )

                tip = (
                    position
                    + direction * 9
                )

                left = (
                    position
                    - direction * 5
                    + perpendicular * 5
                )

                right = (
                    position
                    - direction * 5
                    - perpendicular * 5
                )

                pygame.draw.polygon(
                    self.screen,
                    empire.color,
                    [
                        tip,
                        left,
                        right,
                    ],
                )

            label = self.tiny_font.render(
                str(int(fleet.ships)),
                True,
                config.TEXT,
            )

            self.screen.blit(
                label,
                (
                    position.x + 8,
                    position.y - 8,
                ),
            )

    def _draw_combat_shots(
        self,
        galaxy: Galaxy,
    ) -> None:
        for shot in galaxy.combat_shots:
            alpha_ratio = (
                shot.lifetime
                / shot.max_lifetime
            )

            alpha_ratio = max(
                0.0,
                min(1.0, alpha_ratio),
            )

            color = tuple(
                int(channel * alpha_ratio)
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

    def _draw_systems(
        self,
        galaxy: Galaxy,
        player: PlayerController,
    ) -> None:
        valid_targets = (
            player.valid_target_ids()
        )

        for system in galaxy.systems:
            if system.owner_id is None:
                color = config.NEUTRAL_COLOR
                radius = config.STAR_RADIUS
            else:
                empire = galaxy.empires[
                    system.owner_id
                ]

                color = empire.color
                radius = config.OWNED_STAR_RADIUS

            if system.id in valid_targets:
                pygame.draw.circle(
                    self.screen,
                    config.VALID_TARGET_COLOR,
                    system.pos,
                    radius + 8,
                    1,
                )

            if (
                system.id
                == player.hovered_system_id
            ):
                pygame.draw.circle(
                    self.screen,
                    (190, 200, 220),
                    system.pos,
                    radius + 5,
                    1,
                )

            if (
                system.id
                == player.selected_system_id
            ):
                pygame.draw.circle(
                    self.screen,
                    config.SELECTION_COLOR,
                    system.pos,
                    radius + 10,
                    3,
                )

            pygame.draw.circle(
                self.screen,
                config.STAR_CORE_COLOR,
                system.pos,
                radius + 2,
            )

            pygame.draw.circle(
                self.screen,
                color,
                system.pos,
                radius,
            )

            ship_text = self.small_font.render(
                str(int(system.ships)),
                True,
                config.TEXT,
            )

            self.screen.blit(
                ship_text,
                (
                    system.pos.x + radius + 5,
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
            "HYPERLANE WARS",
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

        stats_rect = stats.get_rect(
            midtop=(
                config.WIDTH // 2,
                14,
            )
        )

        self.screen.blit(
            stats,
            stats_rect,
        )

        controls = self.tiny_font.render(
            (
                "Left click: select   "
                "Right click: send to any reachable system   "
                "Wheel: fleet %   "
                "Space: pause   "
                "+/-: speed   "
                "R: new game"
            ),
            True,
            config.MUTED_TEXT,
        )

        controls_rect = controls.get_rect(
            midtop=(
                config.WIDTH // 2,
                40,
            )
        )

        self.screen.blit(
            controls,
            controls_rect,
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

            rectangle = message.get_rect(
                midbottom=(
                    config.WIDTH // 2,
                    config.HEIGHT - 8,
                )
            )

            self.screen.blit(
                message,
                rectangle,
            )

    def _draw_selection_panel(
        self,
        galaxy: Galaxy,
        player: PlayerController,
        y: int,
    ) -> None:
        selected_id = (
            player.selected_system_id
        )

        if selected_id is None:
            lines = [
                "No system selected",
                (
                    "Left-click one of "
                    "your blue systems."
                ),
                (
                    "Right-click any reachable "
                    "system to send a fleet."
                ),
            ]
        else:
            system = galaxy.systems[
                selected_id
            ]

            reachable = len(
                galaxy.reachable_system_ids(
                    selected_id
                )
            )

            lines = [
                system.name,
                (
                    f"Ships: "
                    f"{int(system.ships)}"
                ),
                (
                    f"Production: "
                    f"{system.production:.2f}/s"
                ),
                (
                    f"Connections: "
                    f"{len(galaxy.neighbors[system.id])}"
                ),
                (
                    f"Reachable systems: "
                    f"{reachable}"
                ),
                (
                    f"Fleet order: "
                    f"{player.send_percent}%"
                ),
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
            (
                x,
                y + 12,
            ),
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

        title_rect = title.get_rect(
            center=(
                config.WIDTH // 2,
                config.HEIGHT // 2 - 35,
            )
        )

        self.screen.blit(
            title,
            title_rect,
        )

        description = self.font.render(
            subtitle,
            True,
            config.TEXT,
        )

        description_rect = description.get_rect(
            center=(
                config.WIDTH // 2,
                config.HEIGHT // 2 + 20,
            )
        )

        self.screen.blit(
            description,
            description_rect,
        )

        restart = self.small_font.render(
            "Press R to start a new galaxy.",
            True,
            config.MUTED_TEXT,
        )

        restart_rect = restart.get_rect(
            center=(
                config.WIDTH // 2,
                config.HEIGHT // 2 + 55,
            )
        )

        self.screen.blit(
            restart,
            restart_rect,
        )