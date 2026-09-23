# Battleship

**Play online:** https://battleship-s0yh.onrender.com/

A Human-vs-AI Battleship game built with [Gradio](https://www.gradio.app/), with a retro arcade theme and two
ways to play: classic naval combat, and a word-puzzle variant where the AI's ships are hidden words.

## Game modes

Use the **Switch to Word Puzzle Mode / Switch to Classic Mode** button to change modes at any time; switching
starts a fresh game. Instructions are shown for the active mode only.

### Classic mode (default)

Standard 10x10 Battleship against an AI.

1. **Placement phase** — click cells on *your* grid (left) to place five ships: Carrier (5), Battleship (4),
   Cruiser (3), Submarine (3), Destroyer (2). Use **Toggle Orientation** to switch horizontal/vertical.
2. **Battle phase** — click cells on the *AI* grid (right) to fire. After every shot the AI fires back at your
   fleet, hunting the neighbouring cells after it scores a hit.
3. **Win** by sinking all 17 AI ship cells before the AI sinks yours.

The AI's fleet is placed with a backtracking algorithm so a full fleet is always guaranteed.
Legend: 🌊 water · 🚢 ship · 💥 hit · ⚪ miss.

### Word Puzzle mode

The right-hand grid becomes a 10x10 grid of letters. Five hidden words (5, 4, 3, 3 and 2 letters, running
across or down, never touching) are the AI's "ships" — each names a coding task Devin excels at
(e.g. DEBUG, LINT, FIX, PR). A **How to Win** popup explains the rules when you enter this mode and can be
reopened from the button below the boards.

- **Spell to sink** — click letters to select them (click again to deselect, or **Clear Selection**). Spelling a
  full target word sinks it: its cells turn green and a chime plays.
- **Hints** — letters belonging to a target word are shown in bold with a small green dot.
- **Decoys** — the grid also hides decoy words for tasks better owned by humans (e.g. SCOPE, HIRE, ONCALL).
  Spelling one shows a popup explaining why it isn't a fit for Devin and does not count toward the win.
- **The AI fires back** — your own fleet (left) is placed automatically, spread out and hugging the edges, and the
  AI takes one classic shot at it after every letter you click.
- **Win** by finding all five targets before the AI sinks your fleet.

Legend: bold letter + green dot = part of a target · green glow = solved word · accent border = selected.

## Running locally

```bash
pip install -r requirements.txt
python app.py          # serves at http://127.0.0.1:7860
```

`server.py` is the production entrypoint used by Render (`render.yaml`): it mounts the Gradio app inside
FastAPI and serves it with uvicorn on `$PORT`.

## Project layout

| Path | Purpose |
| --- | --- |
| `app.py` | The whole game: `BattleshipGame` (state, placement, AI, word-puzzle logic), Gradio UI, CSS and JS |
| `server.py` / `render.yaml` | Production server and Render deployment config |
| `tests/` | Pytest suite for the game logic and UI handlers |
| `pyproject.toml` | Pytest and coverage configuration |
| `requirements.txt` / `requirements-dev.txt` | Runtime and test dependencies |
| `debugging.md` | Debugging log — see below |

## Tests

```bash
pip install -r requirements.txt -r requirements-dev.txt
pytest
```

`pytest` picks up `tests/` and the coverage options from `pyproject.toml` (`--cov=app --cov-report=term-missing`,
failing below 90% coverage). The Gradio `with gr.Blocks(...)` UI construction and the `__main__` launch are
excluded from the coverage report; all game logic in `BattleshipGame` and the module-level handlers is covered.

## Debugging log (`debugging.md`)

`debugging.md` is the single source of truth for every bug found in this project. Each entry records the title,
reporter, status (Open / In progress / Fixed), description, impact, the fix, and the Devin session and PR that
resolved it, plus a PR-to-bug map at the top. When you find or fix a bug, add or update its entry there rather than
documenting it elsewhere.
