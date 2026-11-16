from __future__ import annotations

import ast
import re
import shlex
from pathlib import Path

import pygame

from . import config
from .galaxy import Galaxy
from .galaxy_generation import GalaxyLayout, SystemSpec
from .models import CombatImpact, Empire, Explosion, Fleet, StarSystem, CommandShip

SAVE_DIRECTORY = Path(__file__).resolve().parent.parent / "saves"


def list_save_files() -> list[Path]:
    def sort_key(path: Path):
        return tuple((1, int(part)) if part.isdigit() else (0, part.casefold()) for part in re.split(r"(\d+)", path.name))

    if not SAVE_DIRECTORY.exists():
        return []
    paths = [path for path in SAVE_DIRECTORY.iterdir() if path.is_file() and path.suffix.casefold() == ".galaxy"]
    return sorted(paths, key=sort_key)


def next_save_path() -> Path:
    existing = {path.name.casefold() for path in list_save_files()}
    number = 1
    while f"save{number}.galaxy" in existing:
        number += 1
    return SAVE_DIRECTORY / f"save{number}.galaxy"


def resolve_save_path(name: str) -> Path:
    filename = name.strip()
    if not filename or Path(filename).name != filename or "/" in filename or "\\" in filename:
        raise ValueError("Enter a valid save name.")
    if not filename.casefold().endswith(".galaxy"):
        if Path(filename).suffix:
            raise ValueError("Save files must use the .galaxy extension.")
        filename = f"{filename}.galaxy"
    else:
        filename = f"{filename[:-7]}.galaxy"
    stem = filename[:-7]
    if not stem or stem in {".", ".."} or re.search(r'[<>:"|?*\x00-\x1f]', stem):
        raise ValueError("That save name contains invalid characters.")
    if stem.endswith((".", " ")):
        raise ValueError("Save names cannot end with a dot or space.")
    return SAVE_DIRECTORY / filename


def _managed_save_path(path: str | Path) -> Path:
    source = Path(path)
    if source.suffix.casefold() != ".galaxy":
        raise ValueError("Only .galaxy save files can be changed.")
    save_directory = SAVE_DIRECTORY.resolve()
    if source.resolve().parent != save_directory or not source.is_file():
        raise ValueError("That save file is not available in the saves folder.")
    return source


def rename_save_file(path: str | Path, new_name: str) -> Path:
    source = _managed_save_path(path)
    destination = resolve_save_path(new_name)
    if destination.exists() and destination.resolve() != source.resolve():
        raise FileExistsError("A save with that name already exists.")
    if destination.resolve() == source.resolve():
        return source
    source.rename(destination)
    return destination


def delete_save_file(path: str | Path) -> None:
    source = _managed_save_path(path)
    source.unlink()


def _vector(value: pygame.Vector2) -> tuple[float, float]:
    return float(value.x), float(value.y)


def _section(lines: list[str], name: str, values: dict) -> None:
    lines.append(name)
    for key, value in values.items():
        lines.append(f"    {key} {value!r}")
    lines.append("")


def _read_save(path: str | Path) -> dict:
    source = Path(path)
    sections = {}
    current = None
    seen_header = False

    for line_number, raw in enumerate(source.read_text(encoding="utf-8").splitlines(), 1):
        if not raw.strip():
            continue
        if raw.lstrip().startswith("#"):
            continue
        if raw[0].isspace():
            if current is None:
                raise ValueError(f"{source.name}:{line_number}: property without a section")
            parts = raw.strip().split(None, 1)
            if len(parts) != 2:
                raise ValueError(f"{source.name}:{line_number}: malformed property")
            key, literal = parts
            try:
                sections[current][key] = ast.literal_eval(literal)
            except (SyntaxError, ValueError) as exc:
                raise ValueError(f"{source.name}:{line_number}: invalid value for {key}") from exc
            continue

        try:
            parts = shlex.split(raw, comments=True)
        except ValueError as exc:
            raise ValueError(f"{source.name}:{line_number}: {exc}") from exc
        if not parts:
            continue
        kind, *args = parts
        if kind == "save" and args == ["1"] and not seen_header:
            seen_header = True
            current = None
            continue
        if not seen_header:
            raise ValueError("Invalid save file: expected 'save 1'")
        if kind in {"galaxy", "ai", "player", "camera", "app"} and not args:
            key = (kind,)
        elif kind in {"empire", "system", "fleet", "command_ship", "explosion", "impact"} and len(args) == 1:
            try:
                key = (kind, int(args[0]))
            except ValueError as exc:
                raise ValueError(f"{source.name}:{line_number}: invalid {kind} id") from exc
        else:
            raise ValueError(f"{source.name}:{line_number}: unknown or malformed section {kind}")
        if key in sections:
            raise ValueError(f"{source.name}:{line_number}: duplicate section {kind}")
        sections[key] = {}
        current = key

    if not seen_header:
        raise ValueError("Invalid save file: expected 'save 1'")
    for required in (("galaxy",), ("ai",), ("player",), ("camera",), ("app",)):
        if required not in sections:
            raise ValueError(f"Invalid save file: missing {required[0]} section")

    return {
        "galaxy": sections[("galaxy",)],
        "ai": sections[("ai",)],
        "player": sections[("player",)],
        "camera": sections[("camera",)],
        "app": sections[("app",)],
        "empires": [(key[1], value) for key, value in sections.items() if key[0] == "empire"],
        "systems": [(key[1], value) for key, value in sections.items() if key[0] == "system"],
        "fleets": [(key[1], value) for key, value in sections.items() if key[0] == "fleet"],
        "command_ships": [(key[1], value) for key, value in sections.items() if key[0] == "command_ship"],
        "explosions": [(key[1], value) for key, value in sections.items() if key[0] == "explosion"],
        "impacts": [(key[1], value) for key, value in sections.items() if key[0] == "impact"],
    }


def save_game(
    galaxy: Galaxy,
    ai,
    player,
    camera: dict,
    speed_index: int,
    paused: bool,
    path: str | Path | None = None,
) -> Path:
    destination = next_save_path() if path is None else Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    lines = ["save 1", ""]

    galaxy_state = {
        "empire_count": galaxy.empire_count,
        "active_empire_indices": list(galaxy._active_empire_indices),
        "player_id": config.PLAYER_ID,
        "next_fleet_id": galaxy.next_fleet_id,
        "next_empire_id": galaxy.next_empire_id,
        "gathering_points": sorted(galaxy.gathering_points),
        "new_ship_accum": galaxy.new_ship_accum,
        "accum_owner": galaxy._accum_owner,
        "active_combat": galaxy.active_combat,
        "autopilot": galaxy.autopilot,
        "player_succession_complete": galaxy.player_succession_complete,
        "nuclear_cooldown": galaxy.nuclear_cooldown,
        "nuked_grace": galaxy.nuked_grace,
        "pending_messages": galaxy.pending_messages,
        "rebellion_timer": galaxy.rebellion_timer,
        "casualty_accum": galaxy._casualty_accum,
        "prev_owners": galaxy._prev_owners,
        "sim_time": galaxy.sim_time,
        "colonization_history": galaxy.colonization_history,
        "colonization_start": galaxy.colonization_start,
        "colonization_delay": galaxy.colonization_delay,
        "colonization_origin": {key: sorted(value) for key, value in galaxy.colonization_origin.items()},
        "combat_tick_accum": galaxy._combat_tick_accum,
        "combat_tick_visual_accum": galaxy._combat_tick_visual_accum,
        "gather_dispatch_timers": galaxy._gather_dispatch_timers,
        "shot_stream_elapsed": galaxy._shot_stream_elapsed,
        "active_shot_streams": sorted(galaxy._active_shot_streams),
        "grid_cell_size": galaxy.grid_cell_size,
        "rng_state": galaxy.rng.getstate(),
        "visual_rng_state": galaxy.visual_rng.getstate(),
        "source_layout": None if galaxy.layout is None else {
            "systems": [
                (spec.id, spec.x, spec.y, spec.name, spec.production)
                for spec in sorted(galaxy.layout.systems, key=lambda item: item.id)
            ],
            "edges": sorted(galaxy.layout.edges),
            "starts": galaxy.layout.starts,
        },
        "edges": sorted(galaxy.edges),
        "command_ai_relocation_cooldowns": galaxy.command.ai_relocation_cooldowns,
        "config_values": {
            key: value
            for key, value in vars(config).items()
            if key.isupper() and isinstance(value, (str, int, float, bool, tuple, list, dict, type(None)))
        },
    }
    _section(lines, "galaxy", galaxy_state)

    ai_state = {
        "think_timer": ai.think_timer,
        "attack_cooldowns": ai.attack_cooldowns,
        "blitz_target": ai.blitz_target,
        "breakthrough_focus": ai.breakthrough_focus,
        "breakthrough_timer": ai.breakthrough_timer,
        "massing_focus": ai.massing_focus,
        "massing_stage_point": ai.massing_stage_point,
        "massing_timer": ai.massing_timer,
        "nuclear_lockouts": ai.nuclear_lockouts,
        "dominance_detected": ai.dominance_detected,
        "spite_detectors": ai.spite_detectors,
        "rng_state": ai.rng.getstate(),
    }
    _section(lines, "ai", ai_state)

    player_state = {
        "selected_system_id": player.selected_system_id,
        "hovered_system_id": player.hovered_system_id,
        "send_percent": player.send_percent,
        "send_count": player.send_count,
        "use_percent": player.use_percent,
        "nuke_targeting": player.nuke_targeting,
        "command_mode": player.command_mode,
        "message": player.message,
        "message_timer": player.message_timer,
    }
    _section(lines, "player", player_state)
    _section(lines, "camera", camera)
    _section(lines, "app", {"speed_index": speed_index, "paused": paused})

    for empire in galaxy.empires:
        _section(lines, f"empire {empire.id}", {
            "id": empire.id,
            "name": empire.name,
            "color": empire.color,
            "is_player": empire.is_player,
            "alive": empire.alive,
            "missiles_remaining": empire.missiles_remaining,
            "happiness": empire.happiness,
            "unrest_tolerance": empire.unrest_tolerance,
            "is_rebel": empire.is_rebel,
            "command_lockout": empire.command_lockout,
            "command_losses": empire.command_losses,
            "escorts": empire.escorts,
        })

    for system in galaxy.systems:
        _section(lines, f"system {system.id}", {
            "id": system.id,
            "name": system.name,
            "x": float(system.pos.x),
            "y": float(system.pos.y),
            "production": system.production,
            "ships": system.ships,
            "owner_id": system.owner_id,
            "hidden_nukes": system.hidden_nukes,
        })

    for fleet in galaxy.fleets:
        _section(lines, f"fleet {fleet.id}", {
            "id": fleet.id,
            "owner_id": fleet.owner_id,
            "source_id": fleet.source_id,
            "target_id": fleet.target_id,
            "ships": fleet.ships,
            "progress": fleet.progress,
            "segment_progress": fleet.segment_progress,
            "route": fleet.route,
            "route_index": fleet.route_index,
            "position": _vector(fleet.position),
            "siege_target_id": fleet.siege_target_id,
            "is_missile": fleet.is_missile,
        })

    for empire_id, ship in sorted(galaxy.command.ships.items()):
        _section(lines, f"command_ship {empire_id}", {
            "owner_id": ship.owner_id,
            "system_id": ship.system_id,
            "position": _vector(ship.position),
            "hull": ship.hull,
            "route": ship.route,
            "route_index": ship.route_index,
            "segment_progress": ship.segment_progress,
            "destination_id": ship.destination_id,
        })

    for index, explosion in enumerate(galaxy.explosions):
        _section(lines, f"explosion {index}", {
            "position": _vector(explosion.pos),
            "age": explosion.age,
            "max_age": explosion.max_age,
            "peak_radius": explosion.peak_radius,
        })

    for index, impact in enumerate(galaxy.combat_impacts):
        _section(lines, f"impact {index}", {
            "position": _vector(impact.pos),
            "color": impact.color,
            "age": impact.age,
            "max_age": impact.max_age,
        })

    temporary = destination.with_suffix(destination.suffix + ".tmp")
    temporary.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    temporary.replace(destination)
    return destination


def load_game(path: str | Path) -> dict:
    return _read_save(path)


def restore_galaxy(snapshot: dict) -> Galaxy:
    state = snapshot["galaxy"]
    empire_entries = sorted(snapshot["empires"], key=lambda item: item[0])
    system_entries = sorted(snapshot["systems"], key=lambda item: item[0])
    if not system_entries or not empire_entries:
        raise ValueError("Save file does not contain a playable galaxy")
    if [entry_id for entry_id, _ in system_entries] != list(range(len(system_entries))):
        raise ValueError("Save file contains invalid system IDs")
    if [entry_id for entry_id, _ in empire_entries] != list(range(len(empire_entries))):
        raise ValueError("Save file contains invalid empire IDs")

    for key, value in state.get("config_values", {}).items():
        if key.isupper():
            setattr(config, key, value)

    active_empire_indices = list(state["active_empire_indices"])
    player_id = int(state["player_id"])
    if (
        not active_empire_indices
        or len(active_empire_indices) != len(set(active_empire_indices))
        or any(index not in range(len(config.EMPIRES)) for index in active_empire_indices)
        or player_id not in range(len(active_empire_indices))
    ):
        raise ValueError("Save file contains invalid player empire data")
    if len(system_entries) < len(active_empire_indices):
        raise ValueError("Save file has fewer systems than starting empires")

    specs = []
    systems_by_id = {}
    for system_id, entry in system_entries:
        sid = int(entry["id"])
        if sid != system_id:
            raise ValueError("Save file contains mismatched system IDs")
        spec = SystemSpec(sid, float(entry["x"]), float(entry["y"]), str(entry["name"]), float(entry["production"]))
        specs.append(spec)
        systems_by_id[sid] = entry

    edges = set()
    for entry in state.get("edges", []):
        first, second = sorted((int(entry[0]), int(entry[1])))
        if first == second or first not in systems_by_id or second not in systems_by_id:
            raise ValueError("Save file contains an invalid hyperlane")
        edges.add((first, second))

    runtime_layout = GalaxyLayout(specs, edges)
    runtime_layout.validate(playable=True, empire_indices=active_empire_indices)

    layout_data = state.get("source_layout")
    saved_layout = None
    if layout_data is not None:
        layout_specs = [SystemSpec(int(sid), float(x), float(y), str(name), production) for sid, x, y, name, production in layout_data["systems"]]
        layout_edges = {tuple(sorted((int(first), int(second)))) for first, second in layout_data["edges"]}
        layout_starts = {int(key): int(value) for key, value in layout_data["starts"].items()}
        saved_layout = GalaxyLayout(layout_specs, layout_edges, layout_starts)
        saved_layout.validate()

    config.EMPIRE_COUNT = len(active_empire_indices)
    config.PLAYER_EMPIRE_INDEX = active_empire_indices[player_id]
    config.PLAYER_ID = player_id

    dummy_starts = {empire: system_id for empire, system_id in zip(active_empire_indices, sorted(systems_by_id))}
    construction_layout = GalaxyLayout(specs, edges, dummy_starts)
    galaxy = Galaxy(layout=construction_layout)
    galaxy.layout = saved_layout
    galaxy.empire_count = int(state["empire_count"])
    galaxy._active_empire_indices = active_empire_indices
    if saved_layout is None:
        galaxy._layout_index = {spec.id: index for index, spec in enumerate(sorted(specs, key=lambda item: item.id))}
    else:
        galaxy._layout_index = {spec.id: index for index, spec in enumerate(sorted(saved_layout.systems, key=lambda item: item.id))}

    galaxy.systems = [
        StarSystem(
            id=int(entry["id"]),
            name=str(entry["name"]),
            pos=pygame.Vector2(float(entry["x"]), float(entry["y"])),
            production=float(entry["production"]),
            ships=float(entry["ships"]),
            owner_id=entry["owner_id"],
            hidden_nukes=int(entry["hidden_nukes"]),
        )
        for _, entry in system_entries
    ]
    galaxy.empires = [
        Empire(
            id=int(entry["id"]),
            name=str(entry["name"]),
            color=tuple(entry["color"]),
            is_player=bool(entry["is_player"]),
            alive=bool(entry["alive"]),
            missiles_remaining=int(entry["missiles_remaining"]),
            happiness=float(entry["happiness"]),
            unrest_tolerance=float(entry["unrest_tolerance"]),
            is_rebel=bool(entry["is_rebel"]),
            command_lockout=float(entry["command_lockout"]),
            command_losses=int(entry["command_losses"]),
            escorts=float(entry["escorts"]),
        )
        for _, entry in empire_entries
    ]
    galaxy.fleets = [
        Fleet(
            id=int(entry["id"]),
            owner_id=int(entry["owner_id"]),
            source_id=int(entry["source_id"]),
            target_id=int(entry["target_id"]),
            ships=float(entry["ships"]),
            progress=float(entry["progress"]),
            segment_progress=float(entry["segment_progress"]),
            route=tuple(entry["route"]),
            route_index=int(entry["route_index"]),
            position=pygame.Vector2(entry["position"]),
            siege_target_id=entry["siege_target_id"],
            is_missile=bool(entry["is_missile"]),
        )
        for _, entry in sorted(snapshot["fleets"], key=lambda item: item[0])
    ]
    galaxy.command.ships = {
        int(owner_id): CommandShip(
            owner_id=int(entry["owner_id"]),
            system_id=entry["system_id"],
            position=pygame.Vector2(entry["position"]),
            hull=float(entry["hull"]),
            route=tuple(entry["route"]),
            route_index=int(entry["route_index"]),
            segment_progress=float(entry["segment_progress"]),
            destination_id=entry["destination_id"],
        )
        for owner_id, entry in snapshot["command_ships"]
    }

    galaxy.edges = edges
    galaxy.command.ai_relocation_cooldowns = dict(state["command_ai_relocation_cooldowns"])
    galaxy.neighbors = {system.id: set() for system in galaxy.systems}
    for first, second in edges:
        galaxy.neighbors[first].add(second)
        galaxy.neighbors[second].add(first)

    galaxy.next_fleet_id = int(state["next_fleet_id"])
    galaxy.next_empire_id = int(state["next_empire_id"])
    galaxy.gathering_points = set(state["gathering_points"])
    galaxy.new_ship_accum = dict(state["new_ship_accum"])
    galaxy._accum_owner = dict(state["accum_owner"])
    galaxy.active_combat = dict(state["active_combat"])
    galaxy.autopilot = bool(state["autopilot"])
    galaxy.player_succession_complete = bool(state["player_succession_complete"])
    galaxy.nuclear_cooldown = float(state["nuclear_cooldown"])
    galaxy.nuked_grace = dict(state["nuked_grace"])
    galaxy.pending_messages = list(state["pending_messages"])
    galaxy.rebellion_timer = float(state["rebellion_timer"])
    galaxy._casualty_accum = dict(state["casualty_accum"])
    galaxy._prev_owners = dict(state["prev_owners"])
    galaxy.sim_time = float(state["sim_time"])
    galaxy.colonization_history = {int(key): list(value) for key, value in state["colonization_history"].items()}
    galaxy.colonization_start = dict(state["colonization_start"])
    galaxy.colonization_delay = dict(state["colonization_delay"])
    galaxy.colonization_origin = {int(key): set(value) for key, value in state["colonization_origin"].items()}
    galaxy._combat_tick_accum = float(state["combat_tick_accum"])
    galaxy._combat_tick_visual_accum = float(state["combat_tick_visual_accum"])
    galaxy._gather_dispatch_timers = dict(state["gather_dispatch_timers"])
    galaxy._shot_stream_elapsed = dict(state["shot_stream_elapsed"])
    galaxy._active_shot_streams = set(tuple(value) for value in state["active_shot_streams"])
    galaxy.grid_cell_size = float(state["grid_cell_size"])
    galaxy.rng.setstate(state["rng_state"])
    galaxy.visual_rng.setstate(state["visual_rng_state"])
    galaxy.combat_shots = []
    galaxy.combat_impacts = [
        CombatImpact(
            pos=pygame.Vector2(entry["position"]),
            color=tuple(entry["color"]),
            age=float(entry["age"]),
            max_age=float(entry["max_age"]),
        )
        for _, entry in sorted(snapshot["impacts"], key=lambda item: item[0])
    ]
    galaxy.explosions = [
        Explosion(
            pos=pygame.Vector2(entry["position"]),
            age=float(entry["age"]),
            max_age=float(entry["max_age"]),
            peak_radius=float(entry["peak_radius"]),
        )
        for _, entry in sorted(snapshot["explosions"], key=lambda item: item[0])
    ]
    galaxy.path_cache = {}
    galaxy._ship_count_cache = None
    galaxy.spatial_grid = {}
    galaxy._build_spatial_grid()
    config.PLAYER_ID = player_id
    return galaxy


def restore_ai(ai, state: dict) -> None:
    ai.think_timer = float(state["think_timer"])
    ai.attack_cooldowns = dict(state["attack_cooldowns"])
    ai.blitz_target = dict(state["blitz_target"])
    ai.breakthrough_focus = dict(state["breakthrough_focus"])
    ai.breakthrough_timer = dict(state["breakthrough_timer"])
    ai.massing_focus = dict(state["massing_focus"])
    ai.massing_stage_point = dict(state["massing_stage_point"])
    ai.massing_timer = dict(state["massing_timer"])
    ai.nuclear_lockouts = dict(state["nuclear_lockouts"])
    ai.dominance_detected = dict(state["dominance_detected"])
    ai.spite_detectors = dict(state["spite_detectors"])
    ai.rng.setstate(state["rng_state"])


def restore_player(player, state: dict) -> None:
    player.selected_system_id = state["selected_system_id"]
    player.hovered_system_id = state["hovered_system_id"]
    player.send_percent = int(state["send_percent"])
    player.send_count = int(state["send_count"])
    player.use_percent = bool(state["use_percent"])
    player.nuke_targeting = bool(state["nuke_targeting"])
    player.command_mode = bool(state["command_mode"])
    player.message = str(state["message"])
    player.message_timer = float(state["message_timer"])
