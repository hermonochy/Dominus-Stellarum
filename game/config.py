WIDTH = 1280
HEIGHT = 800
FPS = 60

TOP_BAR_HEIGHT = 72
BOTTOM_BAR_HEIGHT = 130

BACKGROUND = (7, 10, 20)
PANEL = (15, 20, 34)
PANEL_LIGHT = (23, 30, 48)

TEXT = (230, 235, 245)
MUTED_TEXT = (145, 155, 175)

LANE_COLOR = (42, 50, 70)
LANE_HIGHLIGHT = (125, 150, 190)

NEUTRAL_COLOR = (115, 120, 130)
STAR_CORE_COLOR = (245, 248, 255)

SELECTION_COLOR = (255, 240, 120)
VALID_TARGET_COLOR = (120, 230, 160)

PLAYER_ID = 0

STAR_COUNT = 100
EMPIRE_COUNT = 6

MIN_STAR_DISTANCE = 58
GALAXY_CENTER_X = WIDTH // 2
GALAXY_CENTER_Y = (
    TOP_BAR_HEIGHT
    + (
        HEIGHT
        - TOP_BAR_HEIGHT
        - BOTTOM_BAR_HEIGHT
    )
    // 2
)

GALAXY_RADIUS_X = 500
GALAXY_RADIUS_Y = 270
GALAXY_ARMS = 3
GALAXY_ARM_TWIST = 1.8
GALAXY_POSITION_JITTER = 42

# Every system is intended to have between one and three links.
MIN_CONNECTIONS = 1
MAX_CONNECTIONS = 3

# Prevent visually crossing hyperlanes.
LANE_CROSSING_PADDING = 12.0

STAR_RADIUS = 7
OWNED_STAR_RADIUS = 10

STARTING_SHIPS = 35.0

NEUTRAL_SHIPS_MIN = 3
NEUTRAL_SHIPS_MAX = 14

PRODUCTION_MIN = 0.45
PRODUCTION_MAX = 1.25

# Slower fleets give defensive systems time to fire.
FLEET_SPEED = 38.0

# Combat begins before a fleet reaches the destination system.
COMBAT_RANGE = 125.0

# Damage is applied per ship per second.
ATTACKER_DAMAGE_PER_SHIP = 0.12
DEFENDER_DAMAGE_PER_SHIP = 0.20

# More bullets are emitted than strictly required for the damage model.
ATTACKER_SHOTS_PER_SECOND = 8.0
DEFENDER_SHOTS_PER_SECOND = 12.0

SHOT_LIFETIME = 0.16
MAX_VISIBLE_SHOTS = 300

DEFENDER_ORBIT_RADIUS = 26.0
DEFENDER_ORBIT_SPEED = 1.5
DEFENDER_COUNT = 6

# Production is divided among an empire's systems.
# This keeps total production approximately stable as territory grows.
PRODUCTION_CONCENTRATION = 1.0

AI_THINK_INTERVAL = 0.7
AI_ATTACK_THRESHOLD = 20.0
AI_RESERVE_SHIPS = 8.0
AI_MIN_ATTACK_RATIO = 1.35
AI_FRONTIER_REINFORCE_CHANCE = 0.25
AI_COOLDOWN = 3.0  # Seconds before same attack possible
AI_CONSOLIDATION_CHANCE = 0.15
AI_RETROGRADE_PERCENT = 25
AI_BOLDNESS_FACTOR = 0.08

DEFENDER_BONUS = 1.15  # Systems get 15% defensive bonus

DEFAULT_SEND_PERCENT = 50
SEND_PERCENT_STEP = 10
MIN_SEND_PERCENT = 10
MAX_SEND_PERCENT = 100

SIM_SPEEDS = [
    0.5,
    1.0,
    2.0,
    4.0,
]

DEFAULT_SPEED_INDEX = 1

EMPIRE_COLORS = [
    (70, 170, 255),
    (240, 80, 80),
    (90, 215, 125),
    (245, 185, 65),
    (185, 105, 245),
    (240, 110, 200),
    (80, 220, 215),
    (245, 135, 70),
]

EMPIRE_NAMES = [
    "Terran Union",
    "Crimson Dominion",
    "Verdant Compact",
    "Solar Ascendancy",
    "Violet Directorate",
    "Orchid Republic",
    "Cyan League",
    "Ember Coalition",
]