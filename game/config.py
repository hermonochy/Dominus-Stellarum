# Stores all pre defined constants

WIDTH = 1280
HEIGHT = 800
FPS = 30

CAMERA_ZOOM_MIN = 0.05
CAMERA_ZOOM_MAX = 10.0
CAMERA_ZOOM_SENSITIVITY = 0.15
CAMERA_PAN_SENSITIVITY = 0.5

BOTTOM_BAR_MIN_HEIGHT = 96
BAR_DRAG_TOLERANCE = 25

POPUP_WIDTH_RATIO = 0.62
POPUP_HEIGHT_RATIO = 0.70

FONT_PATH = None

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

STAR_COUNT = 150
EMPIRE_COUNT = 5

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

GALAXY_ARM_COUNT = 4
GALAXY_ARM_PITCH = 0.42
GALAXY_ARM_WIND = 0.30
GALAXY_CORE_RATIO = 0.18
GALAXY_CORE_RADIUS = 150.0
GALAXY_BRANCH_RATIO = 0.15

MIN_STAR_DISTANCE = 50

EDGE_MIN_LENGTH = 40
EDGE_MAX_LENGTH = 90

LANE_BRIDGE_MAX = 200.0

ARM_OUTWARD_STEP_MIN = 42.0
ARM_OUTWARD_STEP_MAX = 58.0

STAR_RADIUS = 5
OWNED_STAR_RADIUS = 6

ARM_MAX_RADIUS = 720

BRANCH_CHANCE = 0.28
BRANCH_ANGLE_MIN = 0.30
BRANCH_ANGLE_MAX = 0.70

STARTING_SHIPS = 35.0

NEUTRAL_SHIPS_MIN = 0
NEUTRAL_SHIPS_MAX = 0

PRODUCTION_MIN = 0.45
PRODUCTION_MAX = 1.25

PRODUCTION_A = -2.5
PRODUCTION_B = 1.75
PRODUCTION_C = 0.75

FLEET_SPEED = 10.0

GATHERING_POINT_COLOR = (255, 160, 40)
SHIP_DISPATCH_THRESHOLD = 1.0
GATHER_HOP_WEIGHT = 2.0
GATHER_SHIP_WEIGHT = 1.0

COMBAT_MIN_SHIPS = 0.5
COMBAT_RANGE = 80.0
HIT_K = 10.0
COMBAT_JITTER_MIN = 0.55
COMBAT_JITTER_MAX = 1.45

DEFENDER_BONUS = 1.1
ATTACKER_DAMAGE_PER_SHIP = 0.5
DEFENDER_DAMAGE_PER_SHIP = 0.75
ATTACKER_SHOTS_PER_SECOND = 5.0
DEFENDER_SHOTS_PER_SECOND = 8.0

SYSTEM_VS_SYSTEM_PER_SHIP = 0.06
FLEET_VS_FLEET_PER_SHIP = 0.12

SHOT_LIFETIME = 0.16
MAX_VISIBLE_SHOTS = 500

GUN_RANGE_BASE = 50.0
GUN_RANGE_EXPONENT = 0.1505
FLEET_GUN_RANGE_MULT = 0.5

GUN_RANGE_FILL_ALPHA = 18
GUN_RANGE_RING_ALPHA = 70

AI_THINK_INTERVAL = 1.0
AI_ATTACK_THRESHOLD = 20.0
AI_RESERVE_SHIPS = 1.0
AI_REAR_GUARD_MAX = 10
AI_FRONT_LINE_RESERVE = 15
AI_MIN_ATTACK_RATIO = 1.35
AI_BOLDNESS_FACTOR = 0.1
AI_COOLDOWN = 10.0
AI_MAX_EXPANSIONS_PER_TICK = 3
AI_NEUTRAL_PRIORITY_BONUS = 2.0
AI_BLITZ_POWER_RATIO = 1.8
AI_BLITZ_WAVE_SIZE = 3
AI_BLITZ_LOCAL_RATIO = 1.2
AI_BLITZ_COOLDOWN = 4.0
AI_DEFENSE_STRONGPOINTS = 4
AI_REAR_RELEASE_MULTIPLIER = 1.5
AI_REAR_SEND_PERCENT = 60
AI_MAX_REAR_DISPATCHES = 3
AI_BREAKTHROUGH_CONCENTRATION = 0.25
AI_BREAKTHROUGH_MIN_SURPLUS = 100
AI_BREAKTHROUGH_FOCUS_DURATION = 15.0
AI_BREAKTHROUGH_EXTRA_AGGRESSIVE = 2.0

DEFAULT_SEND_PERCENT = 50
SEND_PERCENT_STEP = 10
MIN_SEND_PERCENT = 10
MAX_SEND_PERCENT = 100

SIM_SPEEDS = [0.25, 0.5, 1.0, 2.0, 4.0, 8.0]
DEFAULT_SPEED_INDEX = SIM_SPEEDS.index(1.0)

DIFFICULTY_PRESETS = {
    "Easy": {
        "AI_THINK_INTERVAL": 2.0,
        "AI_BOLDNESS_FACTOR": 0.05,
        "AI_MIN_ATTACK_RATIO": 1.8,
        "AI_BLITZ_POWER_RATIO": 2.4,
        "AI_COOLDOWN": 15.0,
        "AI_MAX_EXPANSIONS_PER_TICK": 1,
        "AI_REAR_GUARD_MAX": 15,
        "AI_FRONT_LINE_RESERVE": 20,
        "AI_BREAKTHROUGH_CONCENTRATION": 0.15,
    },
    "Normal": {
        "AI_THINK_INTERVAL": 1.0,
        "AI_BOLDNESS_FACTOR": 0.1,
        "AI_MIN_ATTACK_RATIO": 1.35,
        "AI_BLITZ_POWER_RATIO": 1.8,
        "AI_COOLDOWN": 10.0,
        "AI_MAX_EXPANSIONS_PER_TICK": 2,
        "AI_REAR_GUARD_MAX": 10,
        "AI_FRONT_LINE_RESERVE": 15,
        "AI_BREAKTHROUGH_CONCENTRATION": 0.25,
    },
    "Hard": {
        "AI_THINK_INTERVAL": 0.75,
        "AI_BOLDNESS_FACTOR": 0.18,
        "AI_MIN_ATTACK_RATIO": 1.2,
        "AI_BLITZ_POWER_RATIO": 1.55,
        "AI_COOLDOWN": 7.0,
        "AI_MAX_EXPANSIONS_PER_TICK": 3,
        "AI_REAR_GUARD_MAX": 8,
        "AI_FRONT_LINE_RESERVE": 12,
        "AI_BREAKTHROUGH_CONCENTRATION": 0.35,
    },
    "Brutal": {
        "AI_THINK_INTERVAL": 0.5,
        "AI_BOLDNESS_FACTOR": 0.3,
        "AI_MIN_ATTACK_RATIO": 1.1,
        "AI_BLITZ_POWER_RATIO": 1.35,
        "AI_COOLDOWN": 5.0,
        "AI_MAX_EXPANSIONS_PER_TICK": 5,
        "AI_REAR_GUARD_MAX": 5,
        "AI_FRONT_LINE_RESERVE": 10,
        "AI_BREAKTHROUGH_CONCENTRATION": 0.5,
    },
}

DEFAULT_DIFFICULTY_INDEX = 1

EMPIRES = [
    ["Terran Empire", (70, 170, 255)],
    ["Crimson Dominion", (240, 80, 80)],
    ["Emerald Empire", (90, 215, 125)],
    ["Hand of the Void", (0, 0, 0)],
    ["Solar Ascendancy", (245, 185, 65)],
    ["Violet Directorate", (185, 105, 245)],
    ["Rose Republic", (240, 110, 200)],
    ["Cyan League", (80, 220, 220)],
    ["Ember Coalition", (245, 135, 70)],
    ["Sons of Purity", (255, 255, 255)],
]

EMPIRE_LORE = {
    "Terran Empire": "Heirs of a Concord frontier depot, the Terrans descend from the clerks and archivists who fled the burning core carrying the last copy of the Concord Charter. Pragmatic and adaptable, they fight to unify a galaxy they alone still remember how to govern.",
    "Crimson Dominion": "Descended from the Concord's soldier-caste, marooned on rimward martial citadels when the fleets withdrew. Centuries of uninterrupted frontier war have made the Dominion the galaxy's most fearsome close-quarters fighters. They hold hesitation to be the one unforgivable sin.",
    "Emerald Empire": "Plant-humanoid symbiotes seeded from a forgotten quarantine world and botanical archive. The Emerald Empire spreads slowly, in tendrils, taking root in worlds no one else wants. They strike rarely — but a world they hold is a world grown over, and they are immovable once rooted.",
    "Hand of the Void": "Something fled outward past the rim when the starburners fell, and something came back. The Hand moves among the far fringe's oldest wrecks like librarians among shelves, and may be the only power alive that knows who fired the starburners. They do not expand. They do not explain. When they move, they move coreward.",
    "Solar Ascendancy": "Silicon minds uploaded into crystalline lattices by the organics who built them. The Ignis watched their makers go to war over a symbol and concluded that biology itself was the flaw. They harbor no hatred for the other empires — they simply intend to administrate them out of existence.",
    "Violet Directorate": "A distributed consciousness wearing millions of bodies. The Vex see the Regency Crisis as proof that many wills sharing one galaxy is a design error, and they fight on every front simultaneously as if they were one. They do not conquer the galaxy — they complete it, and consider it a gift.",
    "Rose Republic": "The Concord's diplomatic corps, inheritor of its corpse — legally speaking. A fractious democracy surrounded by militarists, the Lumin have become the core's most formidable defensive power precisely because they cannot decide, on schedule, to do anything else. They still propose a restored Concord. With elections.",
    "Cyan League": "Cartel-smugglers and freebooters who ran the blockades of the succession war, selling to all sides from berths no chart admitted existed. Centuries in the cracks of the core's fortresses made them its finest cartographers. They fight opportunistically, avoid fair fights, and hold that the galaxy needs open lanes, not emperors.",
    "Ember Coalition": "Volcanic-world laborers written off by the Concord as an economic loss — and lucky for it, for while their masters burned, the forgotten inherited the neighborhood. The Coalition raises leaders only to overthrow them, and its soldiers fight gloriously by the battalion. You cannot decapitate what has no permanent head.",
    "Sons of Purity": "Human purists who sealed themselves inside their fortress-district before the starburners fell, and emerged believing the fire had cleansed the galaxy for the faithful. The rimborn Terrans fled the burning with the law; the Sons hid from it in the light. Distant kin to the player — and their most devoted enemy. Fanatical, patient, never yielding consecrated ground.",
}