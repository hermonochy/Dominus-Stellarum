from .models import Fleet, StarSystem


def resolve_fleet_arrival(
    fleet: Fleet,
    target: StarSystem,
) -> None:
    if target.owner_id == fleet.owner_id:
        target.ships += fleet.ships
        return

    if fleet.ships > target.ships:
        remaining = fleet.ships - target.ships

        target.owner_id = fleet.owner_id
        target.ships = remaining
        return

    target.ships -= fleet.ships

    if target.ships <= 0.01:
        target.ships = 0.0