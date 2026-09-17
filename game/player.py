import pygame

from . import config
from .galaxy import Galaxy


class PlayerController:
    def __init__(
        self,
        galaxy: Galaxy,
    ):
        self.galaxy = galaxy

        self.selected_system_id: int | None = (
            None
        )

        self.hovered_system_id: int | None = (
            None
        )

        self.send_percent = (
            config.DEFAULT_SEND_PERCENT
        )

        self.message = ""
        self.message_timer = 0.0

    def set_galaxy(
        self,
        galaxy: Galaxy,
    ) -> None:
        self.galaxy = galaxy

        self.selected_system_id = None
        self.hovered_system_id = None

        self.send_percent = (
            config.DEFAULT_SEND_PERCENT
        )

        self.message = ""
        self.message_timer = 0.0

    def update(
        self,
        dt: float,
    ) -> None:
        mouse_position = (
            pygame.mouse.get_pos()
        )

        hovered = self.galaxy.system_at(
            mouse_position
        )

        if hovered is None:
            self.hovered_system_id = None
        else:
            self.hovered_system_id = (
                hovered.id
            )

        if self.message_timer > 0:
            self.message_timer -= dt

            if self.message_timer <= 0:
                self.message = ""

        self._validate_selection()

    def handle_event(
        self,
        event: pygame.event.Event,
    ) -> None:
        if (
            event.type
            == pygame.MOUSEBUTTONDOWN
        ):
            if event.button == 1:
                self._left_click(
                    event.pos
                )

            elif event.button == 3:
                self._right_click(
                    event.pos
                )

            elif event.button == 4:
                self.increase_send_percent()

            elif event.button == 5:
                self.decrease_send_percent()

        elif event.type == pygame.MOUSEWHEEL:
            if event.y > 0:
                self.increase_send_percent()

            elif event.y < 0:
                self.decrease_send_percent()

    def _left_click(
        self,
        position: tuple[int, int],
    ) -> None:
        system = self.galaxy.system_at(
            position
        )

        if system is None:
            self.selected_system_id = None
            return

        if (
            system.owner_id
            == config.PLAYER_ID
        ):
            self.selected_system_id = (
                system.id
            )

            self._set_message(
                f"Selected {system.name}"
            )
        else:
            self._set_message(
                "You can only select "
                "your own systems."
            )

    def _right_click(
        self,
        position: tuple[int, int],
    ) -> None:
        if (
            self.selected_system_id
            is None
        ):
            self._set_message(
                "Select one of your "
                "systems first."
            )
            return

        target = self.galaxy.system_at(
            position
        )

        if target is None:
            return

        source = self.galaxy.get_system(
            self.selected_system_id
        )

        if (
            source.owner_id
            != config.PLAYER_ID
        ):
            self.selected_system_id = None

            self._set_message(
                "That system is no "
                "longer yours."
            )
            return

        if target.id == source.id:
            return

        if not self.galaxy.is_neighbor(
            source.id,
            target.id,
        ):
            self._set_message(
                "Fleets can only travel "
                "along hyperlanes."
            )
            return

        launched = (
            self.galaxy.launch_fleet(
                source.id,
                target.id,
                self.send_percent,
            )
        )

        if not launched:
            self._set_message(
                "Not enough ships."
            )
            return

        if (
            target.owner_id
            == config.PLAYER_ID
        ):
            action = "Reinforcing"
        else:
            action = "Fleet sent to"

        self._set_message(
            f"{action} {target.name}"
        )

    def increase_send_percent(
        self,
    ) -> None:
        self.send_percent = min(
            config.MAX_SEND_PERCENT,
            self.send_percent
            + config.SEND_PERCENT_STEP,
        )

    def decrease_send_percent(
        self,
    ) -> None:
        self.send_percent = max(
            config.MIN_SEND_PERCENT,
            self.send_percent
            - config.SEND_PERCENT_STEP,
        )

    def _validate_selection(
        self,
    ) -> None:
        if (
            self.selected_system_id
            is None
        ):
            return

        system = self.galaxy.get_system(
            self.selected_system_id
        )

        if (
            system.owner_id
            != config.PLAYER_ID
        ):
            self.selected_system_id = None

    def _set_message(
        self,
        message: str,
    ) -> None:
        self.message = message
        self.message_timer = 2.5

    def valid_target_ids(
        self,
    ) -> set[int]:
        if (
            self.selected_system_id
            is None
        ):
            return set()

        return set(
            self.galaxy.neighbors[
                self.selected_system_id
            ]
        )