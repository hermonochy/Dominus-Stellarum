![](./screenshots/icon1.png)


# Dominus Stellarum

A real-time 4X space strategy game built with Python and pygame. Expand your empire across a procedurally generated galaxy, send fleets along hyperlanes, defeat rival empires, and become the last surviving power.

![](./screenshots/screenshot1.png)

## Requirements

- Python 3.10 or newer recommended
- pygame

## Installation

Clone the repository and enter the project directory:

```bash
git clone https://github.com/hermonochy/Dominus-Stellarum.git
cd Dominus-Stellarum
```

Create and activate a virtual environment:

### Windows

```bash
python -m venv .venv
.venv\Scripts\activate
```

### macOS/Linux

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Install the dependencies:

```bash
pip install -r requirements.txt
```

## Running the game

Start the game with:

```bash
python main.py
```

On systems where Python is invoked as `python3`, use:

```bash
python3 main.py
```

## How to play

You begin with one controlled star system. Owned systems continuously produce ships. Use those ships to reinforce your territory or attack neighboring systems.

### Fleet orders

1. **Left-click** one of your systems to select it.
2. **Right-click** a different system to send a fleet.
3. Fleets can only travel along displayed hyperlanes.
4. Capturing all rival territory makes you the winner.

### Gathering points

**Middle-click** any system (yours, neutral, or enemy) to toggle it as a gathering point, marked with an orange reticle. Your systems automatically send newly produced ships to gathering points, choosing the best one based on:

- **Distance** — closer gathering points are preferred.
- **Vulnerability** — thinly defended gathering points receive priority over ones already well stocked.
- **Safe passage** — routes that would cross enemy territory are avoided. If a gathering point cannot be reached without passing through hostile space, your ships stay home rather than fly to their deaths.

Gathering points persist even if the system changes hands — place one deep in enemy space to stage an invasion, or hold a contested chokepoint.

### Controls

| Action | Control |
| --- | --- |
| Select one of your systems | Left mouse button |
| Send a fleet to a system | Right mouse button |
| Pan the view | Drag with middle mouse button |
| Toggle a gathering point | Click planet with middle mouse button |
| Zoom in / out | Mouse wheel |
| Pan the view | Arrow keys |
| Set fleet size to 20% | `1` |
| Set fleet size to 40% | `2` |
| Set fleet size to 60% | `3` |
| Set fleet size to 80% | `4` |
| Set fleet size to 100% | `5` |
| Pause or resume the simulation | `Space` |
| Increase simulation speed | `+` or `=` |
| Decrease simulation speed | `-` |
| Toggle fullscreen | `F` |
| Exit fullscreen (or quit the game) | `Esc` |
| Start a new game | `R` |

## Configuration

Gameplay and display settings can be adjusted in [`game/config.py`](game/config.py), including:

- Frame rate
- Number of star systems and empires
- Star spacing and hyperlane generation
- Starting ship counts
- Production rates
- Fleet speed
- AI decision intervals and attack thresholds
- Simulation speed options
- Empire names and colors

## Future Work

- Alliances
- Storyline
- Power boosts
- Better balance
- Different empire personalities
- Cleaner galaxy generation