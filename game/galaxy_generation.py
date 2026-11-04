from __future__ import annotations

if __name__ == "__main__" and not __package__:
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    __package__ = "game"

import math
import random
import shlex
from dataclasses import dataclass, field
from pathlib import Path

import pygame

from . import config
from .models import StarSystem

GALAXY_DIRECTORY = Path(__file__).resolve().parent.parent / "galaxies"
DEFAULT_PRODUCTION = (config.PRODUCTION_MIN + config.PRODUCTION_MAX) / 2


NAME_PREFIXES = ["Al", "An", "Ar", "Aus", "Bel", "Bor", "Ca", "Cal", "Cor", "Cry", "Del", "Dor", "Dra", "Er", "Ere", "Fal", "Fer", "Gal", "Gar", "Hal", "Hel", "Hor", "Io", "Ir", "Jan", "Kel", "Kor", "Lan", "Lor", "Lu", "Mar", "Mor", "Nab", "Nor", "Ny", "Ob", "Or", "Pal", "Pra", "Qua", "Ral", "Ren", "Rho", "Sol", "Tal", "Tar", "Tha", "Tor", "Ur", "Val", "Vel", "Vor", "Wex", "Xan", "Yar", "Zen", "Zeph"]
NAME_SUFFIXES = ["a", "ac", "ae", "al", "an", "ar", "ath", "ea", "ek", "en", "er", "era", "es", "ia", "ion", "ir", "is", "ix", "o", "on", "or", "os", "ox", "um", "ur", "us", "yn", "yr", "zar"]
NAME_MODIFIERS = ["", " Prime", " Minor", " Secundus", " Tertius", " II", " III", " IV", " IX"]


def generate_system_name(rng: random.Random, used_names: set[str]) -> str:
    capacity = len(NAME_PREFIXES) * len(NAME_SUFFIXES)
    for _ in range(capacity):
        name = rng.choice(NAME_PREFIXES) + rng.choice(NAME_SUFFIXES)
        if name not in used_names:
            used_names.add(name)
            return name
    for _ in range(capacity * len(NAME_MODIFIERS) * 2):
        name = rng.choice(NAME_PREFIXES) + rng.choice(NAME_SUFFIXES) + rng.choice(NAME_MODIFIERS[1:])
        if name not in used_names:
            used_names.add(name)
            return name
    number = len(used_names)
    while f"Sys{number}" in used_names:
        number += 1
    name = f"Sys{number}"
    used_names.add(name)
    return name


def segments_overlap(a, b, c, d) -> bool:
    def cross(p, q, r):
        return (q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0])

    def sign(value):
        if value > 1e-8:
            return 1
        if value < -1e-8:
            return -1
        return 0

    ab_c = sign(cross(a, b, c))
    ab_d = sign(cross(a, b, d))
    cd_a = sign(cross(c, d, a))
    cd_b = sign(cross(c, d, b))
    if ab_c == ab_d == cd_a == cd_b == 0:
        axis = 0 if abs(a[0] - b[0]) >= abs(a[1] - b[1]) else 1
        left = max(min(a[axis], b[axis]), min(c[axis], d[axis]))
        right = min(max(a[axis], b[axis]), max(c[axis], d[axis]))
        return right - left > 1e-8
    if ab_c * ab_d < 0 and cd_a * cd_b < 0:
        return True

    def on_segment(p, q, r):
        return (min(p[0], q[0]) - 1e-8 <= r[0] <= max(p[0], q[0]) + 1e-8
                and min(p[1], q[1]) - 1e-8 <= r[1] <= max(p[1], q[1]) + 1e-8)

    return (ab_c == 0 and on_segment(a, b, c)
            or ab_d == 0 and on_segment(a, b, d)
            or cd_a == 0 and on_segment(c, d, a)
            or cd_b == 0 and on_segment(c, d, b))


@dataclass
class SystemSpec:
    id: int
    x: float
    y: float
    name: str = ""
    production: float | None = None

    @property
    def display_name(self) -> str:
        return self.name.strip() or generate_system_name(random.Random(142857 + self.id), set())

    @property
    def effective_production(self) -> float:
        return DEFAULT_PRODUCTION if self.production is None else self.production


@dataclass
class GalaxyLayout:
    systems: list[SystemSpec] = field(default_factory=list)
    edges: set[tuple[int, int]] = field(default_factory=set)
    starts: dict[int, int] = field(default_factory=dict)
    _name_cache: tuple[tuple[tuple[int, str], ...], dict[int, str]] | None = field(default=None, init=False, repr=False)

    def validate(self, playable: bool = False, empire_indices: list[int] | None = None) -> None:
        ids = [system.id for system in self.systems]
        if len(ids) != len(set(ids)) or any(sid < 0 for sid in ids):
            raise ValueError("System IDs must be unique, nonnegative integers")
        known = set(ids)
        for system in self.systems:
            if not math.isfinite(system.x) or not math.isfinite(system.y):
                raise ValueError(f"System {system.id} has invalid coordinates")
            if system.production is not None and (not math.isfinite(system.production) or system.production < 0):
                raise ValueError(f"System {system.id} has invalid production")
            if "\n" in system.name or "\r" in system.name:
                raise ValueError(f"System {system.id} name must be on one line")
        for first, second in self.edges:
            if first not in known or second not in known or first == second:
                raise ValueError(f"Invalid hyperlane {first} - {second}")
        positions = {system.id: (system.x, system.y) for system in self.systems}
        for first, second in self.edges:
            if self.lane_crosses(first, second, positions=positions, ignore=(first, second)):
                raise ValueError(f"Hyperlane {first} - {second} overlaps another hyperlane")
        for empire, sid in self.starts.items():
            if empire not in range(len(config.EMPIRES)) or sid not in known:
                raise ValueError("Empire start points must reference valid empires and systems")
        if len(set(self.starts.values())) != len(self.starts):
            raise ValueError("Each empire must have a different starting system")
        if playable:
            if not self.systems:
                raise ValueError("A playable galaxy needs at least one system")
            if empire_indices is not None and len(empire_indices) > len(self.systems):
                raise ValueError("Not enough systems for the selected number of empires")

    def resolved_names(self) -> dict[int, str]:
        key = tuple((system.id, system.name) for system in self.systems)
        if self._name_cache is not None and self._name_cache[0] == key:
            return self._name_cache[1]
        used = {system.name.strip() for system in self.systems if system.name.strip()}
        names = {}
        for system in sorted(self.systems, key=lambda item: item.id):
            names[system.id] = system.name.strip() or generate_system_name(random.Random(142857 + system.id), used)
        self._name_cache = (key, names)
        return names

    def system_name(self, system: SystemSpec) -> str:
        return self.resolved_names()[system.id]

    def add_system(self, x: float, y: float) -> SystemSpec:
        sid = max((system.id for system in self.systems), default=-1) + 1
        system = SystemSpec(sid, float(x), float(y))
        self.systems.append(system)
        return system

    def remove_system(self, system_id: int) -> None:
        self.systems = [system for system in self.systems if system.id != system_id]
        self.edges = {edge for edge in self.edges if system_id not in edge}
        self.starts = {empire: sid for empire, sid in self.starts.items() if sid != system_id}

    def lane_crosses(self, first: int, second: int, positions=None, ignore=None) -> bool:
        if positions is None:
            positions = {system.id: (system.x, system.y) for system in self.systems}
        if first not in positions or second not in positions:
            raise ValueError("Hyperlane endpoints must be existing systems")
        a, b = positions[first], positions[second]
        if a == b:
            return True
        ignored = tuple(sorted(ignore)) if ignore is not None else None
        for one, two in self.edges:
            if (one, two) == ignored:
                continue
            c, d = positions[one], positions[two]
            if first in (one, two) or second in (one, two):
                if segments_overlap(a, b, c, d):
                    common = set((first, second)) & set((one, two))
                    if len(common) != 1:
                        return True
                    shared = positions[next(iter(common))]
                    other_a = b if a == shared else a
                    other_b = d if c == shared else c
                    vector_a = (other_a[0] - shared[0], other_a[1] - shared[1])
                    vector_b = (other_b[0] - shared[0], other_b[1] - shared[1])
                    if abs(vector_a[0] * vector_b[1] - vector_a[1] * vector_b[0]) <= 1e-8 and vector_a[0] * vector_b[0] + vector_a[1] * vector_b[1] > 0:
                        return True
                continue
            if segments_overlap(a, b, c, d):
                return True
        return False

    def move_system(self, system_id: int, x: float, y: float) -> bool:
        positions = {system.id: (system.x, system.y) for system in self.systems}
        if system_id not in positions:
            return False
        positions[system_id] = (float(x), float(y))
        for first, second in self.edges:
            if system_id in (first, second) and self.lane_crosses(first, second, positions=positions, ignore=(first, second)):
                return False
        system = next(system for system in self.systems if system.id == system_id)
        system.x, system.y = positions[system_id]
        return True

    def toggle_lane(self, first: int, second: int) -> bool:
        if first == second:
            raise ValueError("A hyperlane needs two different systems")
        edge = tuple(sorted((first, second)))
        if edge in self.edges:
            self.edges.remove(edge)
            return False
        if self.lane_crosses(first, second):
            raise ValueError("Hyperlane would overlap or cross an existing hyperlane")
        self.edges.add(edge)
        return True


def active_empire_indices(count: int, player_index: int) -> list[int]:
    if not 1 <= count <= len(config.EMPIRES):
        raise ValueError(f"Choose between 1 and {len(config.EMPIRES)} empires")
    player = player_index % len(config.EMPIRES)
    indices = list(range(count))
    if player not in indices:
        indices[-1] = player
    return indices


def resolve_empire_starts(layout: GalaxyLayout, empire_indices: list[int]) -> dict[int, int]:
    layout.validate(playable=True, empire_indices=empire_indices)
    if len(empire_indices) != len(set(empire_indices)):
        raise ValueError("Empire selection must not contain duplicates")
    if any(index not in range(len(config.EMPIRES)) for index in empire_indices):
        raise ValueError("Unknown empire selected")
    systems = {system.id: system for system in layout.systems}
    result = {index: layout.starts[index] for index in empire_indices if index in layout.starts}
    occupied = set(result.values())
    center_x = sum(system.x for system in layout.systems) / len(layout.systems)
    center_y = sum(system.y for system in layout.systems) / len(layout.systems)
    for empire in empire_indices:
        if empire in result:
            continue
        candidates = [system for system in layout.systems if system.id not in occupied]
        if not candidates:
            raise ValueError("Not enough unused starting systems")

        def score(system: SystemSpec) -> tuple[float, float, int]:
            distance_center = (system.x - center_x) ** 2 + (system.y - center_y) ** 2
            if not occupied:
                return (distance_center, 0.0, -system.id)
            separation = min(
                (system.x - systems[sid].x) ** 2 + (system.y - systems[sid].y) ** 2
                for sid in occupied
            )
            return (separation, distance_center, -system.id)

        selected = max(candidates, key=score)
        result[empire] = selected.id
        occupied.add(selected.id)
    return result


def save_galaxy(layout: GalaxyLayout, path: str | Path) -> Path:
    layout.validate()
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    lines = ["galaxy 1", ""]
    for system in sorted(layout.systems, key=lambda item: item.id):
        lines.append(f"system {system.id} {system.x:g} {system.y:g}")
        if system.name.strip():
            lines.append(f"    name {shlex.quote(system.name)}")
        if system.production is not None:
            lines.append(f"    production {system.production:.9g}")
        lines.append("")
    for first, second in sorted(layout.edges):
        lines.append(f"lane {first} {second}")
    if layout.edges:
        lines.append("")
    for empire, sid in sorted(layout.starts.items()):
        lines.append(f"start {shlex.quote(config.EMPIRES[empire][0])} {sid}")
    destination.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return destination


def load_galaxy(path: str | Path) -> GalaxyLayout:
    source = Path(path)
    layout = GalaxyLayout()
    current: SystemSpec | None = None
    seen_header = False
    for line_number, raw in enumerate(source.read_text(encoding="utf-8").splitlines(), 1):
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        try:
            parts = shlex.split(raw, comments=True)
            if not parts:
                continue
            kind, *args = parts
            if kind == "galaxy" and args == ["1"] and not seen_header:
                seen_header = True
            elif kind == "empires" and len(args) == 1:
                int(args[0])
                current = None
            elif kind == "system" and len(args) == 3:
                current = SystemSpec(int(args[0]), float(args[1]), float(args[2]))
                layout.systems.append(current)
            elif kind == "name" and len(args) == 1 and current is not None:
                current.name = args[0]
            elif kind == "production" and len(args) == 1 and current is not None:
                current.production = float(args[0])
            elif kind == "lane" and len(args) == 2:
                first, second = int(args[0]), int(args[1])
                if first == second:
                    raise ValueError("A lane cannot connect a system to itself")
                layout.edges.add(tuple(sorted((first, second))))
                current = None
            elif kind == "start" and len(args) == 2:
                if args[0].isdigit():
                    empire = int(args[0]) - 1
                else:
                    empire = next((index for index, entry in enumerate(config.EMPIRES) if entry[0] == args[0]), -1)
                if empire not in range(len(config.EMPIRES)):
                    raise ValueError(f"Unknown empire {args[0]}")
                if empire in layout.starts:
                    raise ValueError(f"Empire {args[0]} has two starts")
                layout.starts[empire] = int(args[1])
                current = None
            else:
                raise ValueError(f"Unknown or malformed directive: {kind}")
        except (ValueError, IndexError) as exc:
            raise ValueError(f"{source.name}:{line_number}: {exc}") from exc
    if not seen_header:
        raise ValueError("Invalid galaxy file: expected 'galaxy 1'")
    layout.validate()
    return layout


class GalaxyGenerator:
    def __init__(self, star_count: int, arm_count: int, rng: random.Random):
        self.star_count = max(2, int(star_count))
        self.arm_count = max(1, int(arm_count))
        self.rng = rng
        self.systems: list[StarSystem] = []
        self.edges: set[tuple[int, int]] = set()
        self.neighbors: dict[int, set[int]] = {}
        self.system_arms: list[int | None] = []
        self.starts: dict[int, int] = {}

    def create(self) -> GalaxyLayout:
        self._create_systems()
        self._place_empires()
        layout = GalaxyLayout(
            systems=[SystemSpec(system.id, system.pos.x, system.pos.y, system.name, system.production) for system in self.systems],
            edges=self.edges.copy(),
            starts=self.starts.copy(),
        )
        layout.validate(playable=True)
        return layout

    def _create_systems(self) -> None:
        center = pygame.Vector2(config.GALAXY_CENTER_X, config.GALAXY_CENTER_Y)
        num_arms = self.arm_count
        target_count = self.star_count

        used_names: set[str] = set()
        positions: list[pygame.Vector2] = []
        system_data: list[tuple[str, float]] = []
        arm_tags: list[Optional[int]] = []

        cell_size = config.MIN_STAR_DISTANCE
        spawn_grid: dict[tuple[int, int], list[pygame.Vector2]] = {}

        def record_position(pos: pygame.Vector2) -> None:
            key = (int(pos.x // cell_size), int(pos.y // cell_size))
            bucket = spawn_grid.get(key)
            if bucket is None:
                spawn_grid[key] = [pos]
            else:
                bucket.append(pos)

        def too_close(pos: pygame.Vector2, min_dist: float) -> bool:
            col = int(pos.x // cell_size)
            row = int(pos.y // cell_size)
            for dc in (-1, 0, 1):
                for dr in (-1, 0, 1):
                    for other in spawn_grid.get((col + dc, row + dr), ()):
                        if pos.distance_to(other) < min_dist:
                            return True
            return False

        def add_star(pos: pygame.Vector2, production: float, arm_idx: Optional[int]) -> None:
            positions.append(pos)
            system_data.append((generate_system_name(self.rng, used_names), production))
            arm_tags.append(arm_idx)
            record_position(pos)

        def arm_spawn(base_angle: float) -> tuple[pygame.Vector2, float]:
            arm_start_radius = config.GALAXY_CORE_RADIUS + 25.0
            t = self.rng.random()
            r = arm_start_radius * (config.ARM_MAX_RADIUS / arm_start_radius) ** t
            theta = (
                base_angle
                + t * math.pi * config.GALAXY_ARM_PITCH
                + self.rng.gauss(0.0, config.GALAXY_ARM_WIND * 0.35)
            )
            r += self.rng.gauss(0.0, config.MIN_STAR_DISTANCE * 0.25)
            r = max(config.GALAXY_CORE_RADIUS + 10.0, r)
            pos = center + pygame.Vector2(math.cos(theta) * r, math.sin(theta) * r)
            production_multiplier = 1.0 - (r / config.ARM_MAX_RADIUS) * 0.35
            production = self.rng.uniform(
                config.PRODUCTION_MIN * production_multiplier,
                config.PRODUCTION_MAX * production_multiplier,
            )
            return pos, production

        def branch_spawn() -> tuple[pygame.Vector2, float, int]:
            parent_index = self.rng.randrange(core_star_end, len(positions))
            parent_rel = positions[parent_index] - center
            parent_theta = math.atan2(parent_rel.y, parent_rel.x)
            branch_angle = parent_theta + self.rng.choice([-1, 1]) * self.rng.uniform(0.5, 1.0)
            branch_radius = parent_rel.length() + self.rng.uniform(35, 55)
            pos = center + pygame.Vector2(
                math.cos(branch_angle) * branch_radius,
                math.sin(branch_angle) * branch_radius,
            )
            production = self.rng.uniform(config.PRODUCTION_MIN, config.PRODUCTION_MAX)
            arm_idx = arm_tags[parent_index]
            return pos, production, arm_idx if arm_idx is not None else 0

        core_target = max(2, int(target_count * config.GALAXY_CORE_RATIO))
        attempts = core_target * 40
        while len(positions) < core_target and attempts > 0:
            attempts -= 1
            r = config.GALAXY_CORE_RADIUS * math.sqrt(self.rng.random())
            theta = self.rng.random() * math.tau
            pos = center + pygame.Vector2(math.cos(theta) * r, math.sin(theta) * r)
            if too_close(pos, config.MIN_STAR_DISTANCE * 0.55):
                continue
            production = self.rng.uniform(config.PRODUCTION_MIN * 1.1, config.PRODUCTION_MAX * 1.1)
            add_star(pos, production, None)

        core_star_end = len(positions)

        base_angles = [
            (math.tau / num_arms) * arm_idx + self.rng.uniform(-0.1, 0.1)
            for arm_idx in range(num_arms)
        ]

        arm_budget = max(0, target_count - len(positions))
        base_quota = arm_budget // num_arms
        remainder = arm_budget - base_quota * num_arms

        for arm_idx in range(num_arms):
            quota = base_quota + (1 if arm_idx < remainder else 0)
            attempts = quota * 5 + 50
            while quota > 0 and attempts > 0:
                attempts -= 1
                pos, production = arm_spawn(base_angles[arm_idx])
                if too_close(pos, config.MIN_STAR_DISTANCE * 0.75):
                    continue
                add_star(pos, production, arm_idx)
                quota -= 1

        deficit = target_count - len(positions)
        attempts = deficit * 30
        relax = 0.75
        miss_streak = 0

        while len(positions) < target_count and attempts > 0:
            attempts -= 1
            if (
                len(positions) > core_star_end
                and self.rng.random() < config.GALAXY_BRANCH_RATIO
            ):
                pos, production, spawn_arm_idx = branch_spawn()
            else:
                spawn_arm_idx = self.rng.randrange(num_arms)
                pos, production = arm_spawn(base_angles[spawn_arm_idx])

            if too_close(pos, config.MIN_STAR_DISTANCE * relax):
                miss_streak += 1
                if miss_streak % 200 == 0:
                    relax = max(0.15, relax - 0.05)
                continue

            miss_streak = 0
            add_star(pos, production, spawn_arm_idx)

        self.system_arms = arm_tags
        for i, (pos, (name, prod)) in enumerate(zip(positions, system_data)):
            ships = float(self.rng.randint(config.NEUTRAL_SHIPS_MIN, config.NEUTRAL_SHIPS_MAX))
            self.systems.append(StarSystem(id=i, name=name, pos=pos, production=prod, ships=ships))
            self.neighbors[i] = set()

        self._build_lanes(positions)

    def _build_lanes(self, positions: list[pygame.Vector2]) -> None:
        n = len(positions)
        parent = list(range(n))

        def find(x: int) -> int:
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x

        def union(a: int, b: int) -> bool:
            ra, rb = find(a), find(b)
            if ra == rb:
                return False
            parent[ra] = rb
            return True

        def crosses_existing(a: int, b: int) -> bool:
            pa, pb = positions[a], positions[b]
            first = (pa.x, pa.y)
            second = (pb.x, pb.y)
            for e1, e2 in self.edges:
                p, q = positions[e1], positions[e2]
                if a in (e1, e2) or b in (e1, e2):
                    shared = next(iter(set((a, b)) & set((e1, e2))))
                    origin = positions[shared]
                    opposite_a = positions[b if a == shared else a] - origin
                    opposite_b = positions[e2 if e1 == shared else e1] - origin
                    cross = opposite_a.x * opposite_b.y - opposite_a.y * opposite_b.x
                    if abs(cross) <= 1e-8 and opposite_a.x * opposite_b.x + opposite_a.y * opposite_b.y > 0:
                        return True
                    continue
                if segments_overlap(first, second, (p.x, p.y), (q.x, q.y)):
                    return True
            return False

        def add_lane(a: int, b: int) -> bool:
            if union(a, b):
                lane = (min(a, b), max(a, b))
                self.edges.add(lane)
                self.neighbors[a].add(b)
                self.neighbors[b].add(a)
                return True
            return False

        candidates: list[tuple[float, int, int]] = []
        for i in range(n):
            for j in range(i + 1, n):
                distance = positions[i].distance_to(positions[j])
                if config.EDGE_MIN_LENGTH <= distance <= config.EDGE_MAX_LENGTH:
                    candidates.append((distance, i, j))
        candidates.sort()

        for distance, i, j in candidates:
            if find(i) == find(j):
                continue
            if crosses_existing(i, j):
                continue
            add_lane(i, j)

        bridges = 0
        while bridges < n:
            groups: dict[int, list[int]] = {}
            for i in range(n):
                groups.setdefault(find(i), []).append(i)
            if len(groups) <= 1:
                break
            roots = list(groups)
            bridge_candidates: list[tuple[float, int, int]] = []
            for a_idx in range(len(roots)):
                for b_idx in range(a_idx + 1, len(roots)):
                    for a in groups[roots[a_idx]]:
                        for b in groups[roots[b_idx]]:
                            distance = positions[a].distance_to(positions[b])
                            if distance <= config.LANE_BRIDGE_MAX:
                                bridge_candidates.append((distance, a, b))
            if not bridge_candidates:
                best = None
                for a_idx in range(len(roots)):
                    for b_idx in range(a_idx + 1, len(roots)):
                        for a in groups[roots[a_idx]]:
                            for b in groups[roots[b_idx]]:
                                distance = positions[a].distance_to(positions[b])
                                if (best is None or distance < best[0]) and not crosses_existing(a, b):
                                    best = (distance, a, b)
                if best is None:
                    break
                distance, a, b = best
                add_lane(a, b)
                bridges += 1
                continue
            bridge_candidates.sort()
            added = False
            for distance, a, b in bridge_candidates:
                if find(a) == find(b):
                    continue
                if crosses_existing(a, b):
                    continue
                add_lane(a, b)
                added = True
                bridges += 1
                break
            if not added:
                remaining = sorted(
                    (positions[a].distance_to(positions[b]), a, b)
                    for a in range(n) for b in range(a + 1, n)
                    if find(a) != find(b)
                )
                for distance, a, b in remaining:
                    if not crosses_existing(a, b) and add_lane(a, b):
                        bridges += 1
                        added = True
                        break
                if not added:
                    break

    @staticmethod
    def _segments_intersect(first: pygame.Vector2, second: pygame.Vector2, third: pygame.Vector2, fourth: pygame.Vector2) -> bool:
        def orientation(a: pygame.Vector2, b: pygame.Vector2, c: pygame.Vector2) -> float:
            return (b.x - a.x) * (c.y - a.y) - (b.y - a.y) * (c.x - a.x)
        first_orientation = orientation(first, second, third)
        second_orientation = orientation(first, second, fourth)
        third_orientation = orientation(third, fourth, first)
        fourth_orientation = orientation(third, fourth, second)
        return first_orientation * second_orientation < 0 and third_orientation * fourth_orientation < 0

    def _spiral_deviation(self, system: StarSystem, arm_idx: int, center: pygame.Vector2) -> tuple[float, float]:
        rel = system.pos - center
        radius = max(rel.length(), config.GALAXY_CORE_RADIUS + 21.0)
        arm_start_radius = config.GALAXY_CORE_RADIUS + 20.0
        log_span = math.log(config.ARM_MAX_RADIUS / arm_start_radius)
        t = min(1.0, max(0.0, math.log(radius / arm_start_radius) / log_span))
        ideal_angle = (math.tau / self.arm_count) * arm_idx + t * math.pi * config.GALAXY_ARM_PITCH
        actual_angle = math.atan2(rel.y, rel.x)
        delta = (actual_angle - ideal_angle + math.pi) % math.tau - math.pi
        return abs(delta), radius

    def _place_empires(self) -> None:
        center = pygame.Vector2(config.GALAXY_CENTER_X, config.GALAXY_CENTER_Y)
        num_arms = self.arm_count
        num_empires = min(len(self.systems), len(config.EMPIRES))

        arm_systems: list[list[StarSystem]] = [[] for _ in range(num_arms)]
        for system, arm_idx in zip(self.systems, self.system_arms):
            if arm_idx is not None:
                arm_systems[arm_idx].append(system)

        chosen: list[int] = []

        def place(system: StarSystem, empire_id: int) -> None:
            self.starts[empire_id] = system.id
            chosen.append(system.id)

        def min_dist_to_placed(system: StarSystem) -> float:
            if not chosen:
                return math.inf
            return min(
                system.pos.distance_to(self.systems[cid].pos)
                for cid in chosen
            )

        empire_id = 0


        for arm_idx in range(num_arms):
            if empire_id >= num_empires:
                break
            candidates = [
                s for s in arm_systems[arm_idx]
                if s.pos.distance_to(center) > config.GALAXY_CORE_RADIUS
            ]
            if not candidates:
                continue
            best: tuple[tuple[int, float, float], StarSystem] | None = None
            for system in candidates:
                deviation, radius = self._spiral_deviation(system, arm_idx, center)
                key = (1 if deviation > 0.5 else 0, -radius, deviation)
                if best is None or key < best[0]:
                    best = (key, system)
            if best is not None:
                place(best[1], empire_id)
                empire_id += 1


        pool = [
            system for system in self.systems
            if system.id not in chosen
            and system.pos.distance_to(center) <= config.EMPIRE_CORE_PLACEMENT_RADIUS
        ]

        spacing = config.EMPIRE_CORE_MIN_SPACING
        while empire_id < num_empires and pool:
            eligible = [
                system for system in pool
                if min_dist_to_placed(system) >= spacing
            ]
            if not eligible:
                if spacing <= 20.0:
                    eligible = pool
                else:
                    spacing = max(20.0, spacing * 0.7)
                    continue
            best = max(eligible, key=min_dist_to_placed)
            pool.remove(best)
            place(best, empire_id)
            empire_id += 1


        while empire_id < num_empires:
            candidates = [s for s in self.systems if s.id not in chosen]
            if not candidates:
                break
            best = max(candidates, key=min_dist_to_placed)
            place(best, empire_id)
            empire_id += 1

def generate_random_galaxy(star_count: int | None = None, arm_count: int | None = None, seed: int | None = None, rng: random.Random | None = None) -> GalaxyLayout:
    count = config.STAR_COUNT if star_count is None else star_count
    arms = config.GALAXY_ARM_COUNT if arm_count is None else arm_count
    if not 2 <= count <= 1000:
        raise ValueError("System count must be between 2 and 1000")
    if not 1 <= arms <= 24:
        raise ValueError("Arm count must be between 1 and 24")
    return GalaxyGenerator(count, arms, rng if rng is not None else random.Random(seed)).create()


if __name__ == "__main__":
    from .galaxy_editor import main

    main()
