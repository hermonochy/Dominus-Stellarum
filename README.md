![](./screenshots/icon1.png)


# Dominus Stellarum

A real-time 4X space strategy game built with Python and pygame. 

Claim a foothold in a procedurally generated spiral galaxy, expand through a network of hyperlanes, and outmanoeuvre rival empires. Build up your fleets, establish gathering points, unleash nuclear strikes, and keep your population loyal—or risk watching your empire fracture from within.

[**Download a release**](https://github.com/hermonochy/Dominus-Stellarum/releases) · [Report a bug](https://github.com/hermonochy/Dominus-Stellarum/issues) · [View the source](https://github.com/hermonochy/Dominus-Stellarum/tree/main/game)

![](./screenshots/screenshot1.png)

## Getting started

### Download a release

The [Releases page](https://github.com/hermonochy/Dominus-Stellarum/releases) contains packaged builds. Download the build for your operating system, and launch the executable.

macOS users will need to run the game from source until a macOS package can be provided for the release.

### Building from source


#### Requirements

- Python 3.10 or newer recommended
- pygame

Clone the repository and enter the project directory:

```bash
git clone https://github.com/hermonochy/Dominus-Stellarum.git
cd Dominus-Stellarum
```

Create and activate a virtual environment:

#### Windows

```powershell
python -m venv .venv
.venv\Scripts\activate
```

#### macOS/Linux

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Install the dependencies:

```bash
pip install -r requirements.txt
```

## Running the game

If you built from source, start the game with:

```bash
python main.py
```

On systems where Python is invoked as `python3`, use:

```bash
python3 main.py
```

## How to play

You begin with a home system and a fleet. Systems under your control produce ships over time. Expand into neutral territory, reinforce vulnerable borders, and attack rival empires. Fleets travel along the hyperlanes shown on the map, so controlling routes and chokepoints is key. The objective is simple: to become the **last empire controlling the galaxy**. Victory is awarded when one empire controls every system; AI empires can win too.

#### Controls

| Action | Control |
| --- | --- |
| Select one of your systems | Left mouse button |
| Send a fleet to a system | Right mouse button |
| Pan the view | Drag with middle mouse button / Arrow keys |
| Toggle a gathering point | Click planet with middle mouse button |
| Zoom in / out | Mouse wheel |
| Send X ships from the selected planet | 1–9 |
| Send Y% of the fleet | F1–F10 |
| Toggle nuclear targeting | `N` |
| Pause or resume the simulation | `Space` |
| Increase simulation speed | `+` or `=` |
| Decrease simulation speed | `-` |
| Toggle fullscreen | `F` |
| Exit fullscreen (or quit the game) | `Esc` |
| Start a new game | `R` |

#### Fleet orders

1. **Select a system:** Left-click one of your systems.
2. **Choose a destination:** Right-click another system to send a fleet.
3. **Choose the force:** Use the number keys to send a small fixed number of ships, or the function keys to send a percentage of the available fleet.
4. **Plan around the map:** Fleets can only travel along connected hyperlanes.

#### Capital and command ship

Every empire is led by a single command ship. There is no separate capital building: the capital is simply wherever the command ship is docked, and it travels with the ship while the ship is in transit.

Press `L` to select or deselect your command ship. While it is selected, right-click another friendly system connected by hyperlanes to relocate it. The command ship cannot capture systems, and it never draws ships out of your garrisons.

Relocating is not free of risk. While in transit the command ship can be caught in the crossfire of any hostile system or fleet whose guns reach it—and since gun range grows with the size of a garrison, the biggest fleets threaten the widest stretch of space. It repairs itself slowly while docked, but it can be destroyed in three ways:

- Incidental fire while travelling between systems.
- A nuclear strike, if it lies within the blast radius.
- The capture of its current system by an enemy fleet.

Losing a command ship is a serious blow. All new orders are blocked for 180 simulation seconds—no fleet launches, no nuclear strikes, no gathering-point changes—while a successor takes command and establishes a new capital. 

If you lose your command ship, the consequences are permanent. When the disruption ends, the succession completes: your former empire passes to AI control and the game continues without you. You can watch it fight on, but you can no longer issue orders—and if that empire goes on to conquer the galaxy, the game records it as a defeat. You died, and your empire won without you.

AI empires face the same risk, and their command ships are handled by the same director: an AI capital quietly relocates toward safer systems whenever it is threatened or when a better-defended world lies further behind the lines. Hunting down an enemy capital therefore takes patience, and enemy capitals are not marked on the map.

##### Escorts

You can recruit an escort screen for your command ship. Escorts:

- **Guard the capital** while your flagship is docked and **protect the flagship in transit**, automatically returning fire at any hostile system or fleet engaging it.
- **Soak incoming fire**: With 5 escorts roughly 2-in-3 shots are absorbed; with hundreds, the flagship is nearly untouchable. Absorbed shots attrit the escort count, so screens wear down under sustained fire.
- **Cannot be taken over by the AI** — the escort pool is yours alone (unless you are killed), and works fully under autopilot.

#### Gathering points

To avoid manually sending newly generated ships to frontier planets, **Middle-click** any system (yours, neutral, or enemy) to toggle it as a gathering point, marked with an orange reticle. Your systems automatically send newly produced ships to gathering points, choosing the best one based on:

- **Distance** — closer gathering points are preferred.
- **Vulnerability** — thinly defended gathering points receive priority over ones already well stocked.
- **Safe passage** — routes that would cross enemy territory are avoided. If a gathering point cannot be reached without passing through hostile space, your ships stay home rather than fly to their deaths.

Gathering points persist even if the system changes hands — place one deep in enemy space to stage an invasion, or hold a contested chokepoint.

#### Nuclear Warfare

Arm nuclear targeting with N, then right-click an enemy system to launch. The missile destroys all ships in its blast radius and damages nearby systems. Both launcher and victim suffer citizen morale penalties—use carefully to avoid triggering rebellions.

#### Revolts and Betrayals

Empires grow restless after heavy casualties or nuclear strikes. When citizen happiness drops too low, systems may defect:

- Betrayal: A planet joins a neighboring empire
- Revolt: Multiple systems in a sector rise together, forming a new independent rebellion

Maintain morale by capturing new territory or reduce casualties. Neglect invites revolt.

### Galaxy Editor

Dominus Stellarum includes a standalone galaxy editor for creating and modifying custom galaxies. This will eventually be used to create a custom galaxy for the storyline.

#### Running the Editor

From the project's root directory, run:

```bash
python editor.py
```

#### Using the Editor

The editor allows you to:

- **Create systems:** Place, move, and delete star systems.
- **Edit systems:** Assign custom names and production values. Unspecified values use defaults.
- **Create hyperlanes:** Connect systems with hyperlanes. Hyperlanes cannot cross or overlap.
- **Set empire starting positions:** Assign a starting system to any predefined empire. Empires without assigned starts receive automatically generated starting positions.
- **Generate random galaxies:** Click **GENERATE RANDOM GALAXY**, enter the number of spiral arms and star systems, and generate a galaxy using the same generator as the main game.
- **Save and load galaxies:** Save your creations as human-readable `.galaxy` files and reopen them for further editing.

When the hyperlane tool is selected, hyperlanes become thicker and brighter for easier editing.

Use the mouse wheel to zoom and middle-click drag to pan around the galaxy.

#### Playing Custom Galaxies

1. Create or load a galaxy in the editor.
2. Save it.
3. Launch the game using `python main.py`.
4. Select your saved galaxy from the **Galaxy Map** setting in the main menu.
5. Choose how many empires will participate and start the game.

Empire starting positions are associated with specific empires, regardless of the number of empires selected for the game.

## Future Work

- Alliances
- Storyline
- Power boosts
- Better balance
- Different empire personalities