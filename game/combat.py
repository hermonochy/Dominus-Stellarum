from . import config
from .models import Fleet, StarSystem


def resolve_fleet_arrival(
    fleet: Fleet,
    target: StarSystem,
) -> None:
    if target.owner_id == fleet.owner_id:
        target.ships += fleet.ships
        return

    attacking_ships = fleet.ships
    defending_ships = target.ships

    attacker_losses = (
        defending_ships
        * config.DEFENDER_FIREPOWER
    )

    defender_losses = (
        attacking_ships
        * config.ATTACKER_FIREPOWER
    )

    attacking_remaining = max(
        0.0,
        attacking_ships - attacker_losses,
    )

    defending_remaining = max(
        0.0,
        defending_ships - defender_losses,
    )

    # The system changes ownership only when the defenders
    # have been destroyed and the attackers have survivors.
    if (
        defending_remaining <= 0.01
        and attacking_remaining > 0.01
    ):
        target.owner_id = fleet.owner_id
        target.ships = attacking_remaining
        return

    # The defender keeps the system if both sides survive.
    target.ships = defending_remaining