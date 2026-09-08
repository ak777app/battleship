# Debugging Log

Single source of truth for all bugs found in this project, their fixes, and the Devin session / PR that resolved each one.

Each bug is documented with: Title, Reported by, Status (Open / In progress / Fixed), Description, Impact, Fix, Devin session, PR.

## PR → bug map

| PR | Bugs | Notes |
| --- | --- | --- |
| [#1](https://github.com/ak777app/battleship/pull/1) | — | Created this debugging log |
| [#2](https://github.com/ak777app/battleship/pull/2) | 1, 2, 11 | Board merge: per-grid click routing, live buttons, reset repaint |
| [#3](https://github.com/ak777app/battleship/pull/3) | 3 | Backtracking AI ship placement |
| [#4](https://github.com/ak777app/battleship/pull/4) | 13 | A–J / 1–10 grid labels, `format_coordinate` |
| [#5](https://github.com/ak777app/battleship/pull/5) | 15, 16, 17 | Word-puzzle mode and its review fixes |
| [#6](https://github.com/ak777app/battleship/pull/6), [#7](https://github.com/ak777app/battleship/pull/7), [#8](https://github.com/ak777app/battleship/pull/8) | — | Word-mode features (bold targets, AI fire-back, spaced words) |
| [#11](https://github.com/ak777app/battleship/pull/11) | — | Pytest suite, 100% coverage gate |
| [#12](https://github.com/ak777app/battleship/pull/12), [#13](https://github.com/ak777app/battleship/pull/13) | — | Arcade theme, green target dots, word chime |
| [#14](https://github.com/ak777app/battleship/pull/14) | — | Background music (closed, not merged) |
| [#15](https://github.com/ak777app/battleship/pull/15) | — | Render deployment (`render.yaml`, `server.py`) |
| [#16](https://github.com/ak777app/battleship/pull/16) | 4 | Per-session `gr.State` game |
| [#17](https://github.com/ak777app/battleship/pull/17) | 5, 6, 7, 8, 9, 12, 14 | Remaining open bugs |
| _(pending)_ | 10 | Needs rules-variant decision (touching ships) |

---

## Bug 1 — Shared click handler across both grids (routing bug)

- **Reported by:** self / analysis
- **Status:** Fixed
- **Description:** Every button on both grids is wired to the same `handle_grid_click(r, c)` (app.py lines ~344-358), which dispatches only on `game.game_phase` (lines ~239-244) and never on which grid was clicked. During the "placement" phase, clicking a cell on the AI grid still calls `game.place_ship` and places a player ship; during "playing", clicking the player grid calls `game.player_attack` and fires at the AI.
- **Impact:** Clicks are routed to the wrong board. Players can place ships by clicking the enemy board and attack the enemy by clicking their own board, which makes the two-grid layout meaningless and confuses the game model.
- **Fix:** `handle_grid_click(row, col, is_ai_grid)` now takes an `is_ai_grid` flag, bound per grid when the buttons are wired. Placement ignores AI-grid clicks ("Place your ships on your own grid (left)!") and attacks ignore player-grid clicks ("Fire at the AI grid (right)!").
- **Devin session:** https://app.devin.ai/sessions/5b3471310b8c4d5288cae5205b7b2c25
- **PR:** https://github.com/ak777app/battleship/pull/2

---

## Bug 2 — Interactive buttons never reflect game state (UI/UX)

- **Reported by:** user
- **Status:** Fixed
- **Description:** The `gr.Button` grids (`player_buttons`, `ai_buttons`) are hard-coded to "🌊" (lines ~316, ~331) and are never included in any handler's `outputs` (lines ~347-358), so they remain water forever. Only the separate `gr.HTML` panels (`player_display`, `ai_display`) show the true board state, and those panels are not clickable.
- **Impact:** The clickable board and the visible board are two different widgets. The player cannot see which cells they already attacked on the interactive grid, and must cross-reference the static HTML panel, which is a poor and error-prone experience.
- **Fix:** The `gr.HTML` panels (and the now-orphaned `create_grid_display`) were removed, leaving one interactive board per side. New `cell_symbol(cell, show_ships)` and `board_updates()` helpers return a `gr.update(value=symbol)` for all 200 cells; `handle_grid_click` and `reset_game_handler` return `[message] + board_updates()` and both are wired to `board_outputs = [message_box] + flat_buttons`, so the buttons now always show live state (including reset — see bug #11).
- **Devin session:** https://app.devin.ai/sessions/5b3471310b8c4d5288cae5205b7b2c25
- **PR:** https://github.com/ak777app/battleship/pull/2

---

## Bug 3 — AI ship placement can silently fail, producing an unwinnable game

- **Reported by:** self / analysis
- **Status:** Fixed
- **Description:** `_place_ai_ships` gives up after 100 attempts with `placed` still False (lines ~44-65) and moves on to the next ship without reporting anything. Meanwhile the win condition uses the hardcoded `total_ship_cells = sum(SHIPS.values())` (line ~27, checked at line ~140).
- **Impact:** The AI board may contain fewer than 17 ship cells, so the player can never reach `player_hits >= 17` and the game becomes unwinnable.
- **Fix:** Replaced bounded random retry with a backtracking placement algorithm. `_place_ai_ships` now uses `_backtrack_place_ships` which:
  - Generates all valid positions for each ship
  - Shuffles positions for randomness while preserving placement guarantee
  - Recursively places ships with backtracking if a position doesn't lead to a complete fleet
  - Only fails with RuntimeError for genuinely unsatisfiable GRID_SIZE/SHIPS configurations
  - Guarantees exactly 17 ship cells are always placed for standard configurations
- **Devin session:** Databricks Assistant (Genie Code)
- **PR:** https://github.com/ak777app/battleship/pull/3

---

## Bug 4 — Global game state shared across all sessions

- **Reported by:** self / analysis
- **Status:** Fixed
- **Description:** `game = BattleshipGame()` is a single module-level instance (line ~200) used directly by every handler, so all Gradio clients and browser tabs share one board, one turn, and one placement phase.
- **Impact:** Two concurrent users (or even two tabs of the same user) corrupt each other's game: ships placed by one appear for the other, turns interleave, and resets wipe out other players' games.

  Update (PR #5, word-puzzle mode): the shared instance now also carries `game.mode`. When one client switches modes, `handle_grid_click` reroutes every other client's clicks to the new mode while their UI (grid visibility, labels, theme) still shows the old one. Flagged by Devin Review on PR #5; the user chose to leave the shared-state architecture as is for now.
- **Fix:** The module-level `game` was removed. `gr.State(BattleshipGame)` (callable, so Gradio builds a fresh, independently randomised game per browser session) is threaded through every handler: each takes the game as its first input and returns it as its first output (`[game, message, *board updates]`). Verified with two browser contexts against the Render deployment. Public deployment context: bug surfaced by Devin Review on PR #15 (Render blueprint).
- **Devin session:** https://app.devin.ai/sessions/a110ddb7b140405a8e64afe462dc7831
- **PR:** https://github.com/ak777app/battleship/pull/16

---

## Bug 5 — AI target-queue cells popped without re-validation

- **Reported by:** self / analysis
- **Status:** Fixed
- **Description:** In smart-targeting mode `_ai_attack` pops a cell from `ai_target_queue` (line ~158) and acts on it immediately, without re-checking that the cell is still `~` or `S`. Cells are only validated at insertion time (lines ~177-182), so a cell queued earlier may already have been resolved by a later attack.
- **Impact:** The AI can "attack" an already-hit or already-missed cell, overwriting the mark and potentially double-counting a hit (`ai_hits += 1` on a cell already marked `X`), which can end the game early or produce misleading board state.
- **Fix:** `_ai_attack` first drains any leading queue entries whose `player_grid` cell is no longer `~`/`S`; if the queue empties it clears `ai_target_mode` and falls back to a random shot, so a cell is never attacked twice and `ai_hits` cannot be double-counted.
- **Devin session:** https://app.devin.ai/sessions/a110ddb7b140405a8e64afe462dc7831
- **PR:** https://github.com/ak777app/battleship/pull/17

---

## Bug 6 — `turn` reset unconditionally even after the game ends

- **Reported by:** self / analysis
- **Status:** Fixed
- **Description:** After the AI moves, `player_attack` always sets `self.turn = "player"` (line ~150), even when `_ai_attack` has just set `game_phase = "ended"` because the AI won.
- **Impact:** Turn state is inconsistent with the ended phase, which makes any turn-based guard unreliable and can mislead future logic that checks `turn` rather than `game_phase`.
- **Fix:** `player_attack` returns straight after `_ai_attack` when the AI ended the game, leaving `turn == "ai"`; `turn = "player"` only runs when the game continues.
- **Devin session:** https://app.devin.ai/sessions/a110ddb7b140405a8e64afe462dc7831
- **PR:** https://github.com/ak777app/battleship/pull/17

---

## Bug 7 — AI targeting never resets when a ship is sunk

- **Reported by:** self / analysis
- **Status:** Fixed
- **Description:** The game tracks only a total hit count and never per-ship sinking. After the AI destroys a ship, `ai_target_mode` stays True and stale adjacent cells from that ship remain in `ai_target_queue` (lines ~172-182). The mode is only cleared when the queue happens to empty on a miss (lines ~193-195).
- **Impact:** The AI wastes turns hunting around an already-sunk ship instead of resuming its search, and the "smart targeting" heuristic behaves incoherently — a subtle difficulty/quality bug.
- **Fix:** Ship identity is now recorded in `player_fleet` (a list of cell lists) by both `place_ship` and `_place_spread_fleet`. New `_ship_sunk(row, col)` checks whether every cell of the ship containing the hit is `X`; when it is, `_ai_attack` clears `ai_target_queue`, `ai_target_mode` and `ai_last_hit`, reports "AI sank your ship at …", and resumes the random search next turn.
- **Devin session:** https://app.devin.ai/sessions/a110ddb7b140405a8e64afe462dc7831
- **PR:** https://github.com/ak777app/battleship/pull/17

---

## Bug 8 — "Ended" phase clicks overwrite the win/loss message

- **Reported by:** self / analysis
- **Status:** Fixed
- **Description:** `player_attack` returns the win string but never assigns it to `self.message` (lines ~140-142); `_ai_attack` does the same for the AI win (lines ~186-188). After the game ends, further clicks fall into the `else` branch of `handle_grid_click` and return the stale `game.message` (lines ~245-246).
- **Impact:** The victory/defeat banner disappears as soon as the player clicks anywhere, replaced by an outdated status line — the player may not know the game is over.
- **Fix:** `player_attack` and `_ai_attack` assign the win/loss banner to `self.message` (and `player_attack` also stores the regular "Hit/Miss + AI reply" text), so post-game clicks — which fall through to `game.message` in `handle_grid_click` — keep showing the final result.
- **Devin session:** https://app.devin.ai/sessions/a110ddb7b140405a8e64afe462dc7831
- **PR:** https://github.com/ak777app/battleship/pull/17

---

## Bug 9 — Orientation toggle has no visual preview and no fit validation

- **Reported by:** self / analysis
- **Status:** Fixed
- **Description:** `toggle_orientation` (lines ~115-121) only flips a string and returns a message; its wiring outputs to `message_box` only (lines ~360-363). Nothing checks whether the current ship can fit in the new orientation until a placement attempt fails (lines ~91-92), and nothing previews where the ship would go.

  Clarification (confirmed): `toggle_orientation` does **not** corrupt state or crash. The potential `IndexError` on `self.ship_names[self.current_ship_index]` is prevented because the method is gated behind `game_phase == "placement"`, so `current_ship_index` is always 0-4; and `place_ship` re-validates via `_can_place_ship`, so a bad orientation only yields an error message with no grid writes. Separately, the toggle message overwrites any prior status text in the message box.
- **Impact:** Placement is trial-and-error: the player cannot see the ship footprint before clicking and only learns a position is invalid after a failed attempt, and the toggle wipes the previous status message.
- **Fix:** (a) Hover preview: player-grid buttons carry `elem_id="pcell-r-c"`, and a hidden `#placement-info` HTML element (emitted by `placement_info(game)` on every handler) exposes `data-phase/size/orient`. `GAME_JS` highlights the cells the current ship would occupy on hover — green (`preview-ok`) when it fits, red (`preview-bad`) when it runs off the board or overlaps a ship. (b) `toggle_orientation` now stores its text in `self.message` and appends a warning when `_fits_anywhere` finds no free spot for the current ship in the new orientation. (c) `place_ship` failures say why: "…: it would run off the board." / "…: it overlaps another ship.".
- **Devin session:** https://app.devin.ai/sessions/a110ddb7b140405a8e64afe462dc7831
- **PR:** https://github.com/ak777app/battleship/pull/17

---

## Bug 10 — Ships can be placed directly adjacent

- **Reported by:** self / analysis
- **Status:** Open — awaiting rules decision (see fix)
- **Description:** `_can_place_ship` (lines ~67-81) only checks bounds and cell emptiness; there is no one-cell buffer between ships, so ships may touch side by side or end to end (for both player and AI placement).
- **Impact:** Depends on the intended rules variant. Under classic tournament rules ships may not touch; touching ships also weaken the AI's adjacency heuristic and can make two ships read as one.
- **Fix (proposed):** Confirm the intended rules variant with the user; optionally enforce a no-touching rule by rejecting placements with an occupied cell in the 8-neighbourhood of any ship cell. `_can_place_ship(..., isolated=True)` and `_isolated` already implement that rule (used for word-mode targets and the auto-placed player fleet), so enforcing it for classic mode is a one-flag change in `place_ship` and `_backtrack_place_ships`. Raised with the owner in the session below.
- **Devin session:** https://app.devin.ai/sessions/a110ddb7b140405a8e64afe462dc7831 (decision requested)
- **PR:** _(to fill in when opened)_

---

## Bug 11 — Reset (and toggle) do not refresh the interactive buttons

- **Reported by:** self / analysis
- **Status:** Fixed
- **Description:** `reset_game_handler` (lines ~265-270) and its wiring (lines ~365-368) output only to the HTML panels and the message box, never to the button grids. This is a facet of bug #2.
- **Impact:** After a reset the interactive board keeps whatever labels it had, so the clickable board disagrees with the actual (fresh) game state.
- **Fix:** Resolved together with bug #2 — `reset_game_handler` now returns `[game.message] + board_updates()` and is wired to `board_outputs`, so every button is repainted on reset. The orientation toggle still writes to the message box only, which is correct since it changes no board state (see bug #9 for the preview work).
- **Devin session:** https://app.devin.ai/sessions/5b3471310b8c4d5288cae5205b7b2c25
- **PR:** https://github.com/ak777app/battleship/pull/2

---

## Bug 12 — Dead / unused code

- **Reported by:** self / analysis
- **Status:** Fixed
- **Description:** `handle_cell_click` is an empty stub (lines ~253-258), `create_interactive_grid` is defined but never called (lines ~272-290), and the `clickable` parameter of `create_grid_display` (line ~202) is never used. (`create_grid_display` and its unused `clickable` parameter were already deleted by the bug #1/#2 board merge; `handle_cell_click` and `create_interactive_grid` remain.)
- **Impact:** Dead code misleads readers about how input is handled and adds maintenance noise.
- **Fix:** `handle_cell_click` and `create_interactive_grid` (and their tests) are deleted; `create_grid_display`/`clickable` had already gone with PR #2.
- **Devin session:** https://app.devin.ai/sessions/a110ddb7b140405a8e64afe462dc7831
- **PR:** https://github.com/ak777app/battleship/pull/17

---

## Bug 13 — Grid axis labels don't follow standard Battleship convention

- **Reported by:** self / analysis
- **Status:** Fixed
- **Description:** In `create_grid_display`, the column header loop (lines ~208-211) prints `0`-`9` and the row header (lines ~213-214) prints `0`-`9`. Standard Battleship uses letters `A`-`J` for columns and numbers `1`-`10` for rows.
- **Impact:** Coordinates shown to the player don't match the conventional notation ("B4"), making the board harder to read and status messages harder to relate to the grid.
- **Fix:** Added standard Battleship grid labels to both grids:
  - Column headers now display A-J using `gr.Markdown` widgets above each grid
  - Row labels now display 1-10 using `gr.Markdown` widgets at the start of each row
  - Added `format_coordinate(row, col)` helper function to convert internal 0-based indexing to standard notation (e.g., "B4")
  - Updated all coordinate messages (hit/miss) in `player_attack` and `_ai_attack` to use standard notation
  - Internal `grid[r][c]` indexing remains 0-based for code clarity
- **Devin session:** Databricks Assistant (Genie Code)
- **PR:** https://github.com/ak777app/battleship/pull/4

---

## Bug 14 — Game state lost / silently desynced on page refresh

- **Reported by:** self / analysis
- **Status:** Fixed
- **Description:** State lives in the module-level singleton `game = BattleshipGame()`, and the widget initial values are computed once at module load (message box line ~298, HTML panels lines ~307/~322). On refresh the server keeps the game but the page re-renders the initial empty board, so the UI desyncs from the real state. If bug #4 is fixed to per-session state, a refresh instead loses the game entirely.
- **Impact:** An accidental refresh either shows a board that is wrong or throws away the game in progress, with no warning.
- **Fix (tier a):** `GAME_JS` (already injected via `head=`) registers a `beforeunload` handler that shows the browser's leave-page confirmation whenever `#placement-info` reports `data-progress="1"` (ships placed or shots fired, game not ended). With per-session state (bug #4) a refresh now consistently starts a fresh game instead of desyncing, and the prompt prevents doing so by accident.
- **Fix (tier b, Open follow-up, not started):** Full persistence via localStorage or a server-side session store, coordinated with bug #4.
- **Devin session:** https://app.devin.ai/sessions/a110ddb7b140405a8e64afe462dc7831
- **PR:** https://github.com/ak777app/battleship/pull/17

---

## Bug 15 — Word mode: scrambled selections solved hidden words

- **Reported by:** Devin Review (PR #5)
- **Status:** Fixed
- **Description:** The first version of `BattleshipGame.select_cell` compared `set(selected_cells) == set(target["cells"])`, discarding click order. Selecting a word's letters backwards or in any scrambled order counted as spelling it (same for decoys).
- **Impact:** Players could "solve" a word they never spelled, trivialising the puzzle.
- **Fix:** New `_spells(cells)` helper requires the ordered selection to equal the word's cells forwards or backwards; used for both target and decoy matching.
- **Devin session:** https://app.devin.ai/sessions/72e9503ebf3d48578c53ab4826946869
- **PR:** https://github.com/ak777app/battleship/pull/5

---

## Bug 16 — Word mode: random camouflage could spell unsolvable copies of hidden words

- **Reported by:** Devin Review (PR #5)
- **Status:** Fixed
- **Description:** `_place_ai_words` filled leftover cells with uniformly random letters. Those letters (alone or together with placed words) could form a second straight-line occurrence of a target or decoy — especially the 2-letter targets PR / CI / QA — which `select_cell` rejected because only the recorded coordinates are recognised.
- **Impact:** A visibly valid word received no credit (or no decoy popup), which looks like a broken game.
- **Fix:** `_fill_camouflage` re-rolls filler cells that participate in a stray occurrence (`_stray_word_cells`, both reading directions). If a stray run consists only of placed letters, the layout attempt is rejected and `_place_ai_words` retries with a fresh layout (up to 50 attempts). The check covers the *entire* target and decoy bank, not just the words placed this game, so filler can't spell an unplaced bank word either (a follow-up Devin Review finding). Known exception: `DOC` reads backwards inside `CODE`, so when `CODE` is placed those three cells are allowed to spell `DOC`.
- **Devin session:** https://app.devin.ai/sessions/72e9503ebf3d48578c53ab4826946869
- **PR:** https://github.com/ak777app/battleship/pull/5

---

## Bug 17 — Word mode: reversed sub-runs of a placed word escaped stray-word cleanup

- **Reported by:** Devin Review (PR #5)
- **Status:** Fixed
- **Description:** The stray-word check exempted any contiguous sub-run of a recorded placement, so with `CODE` placed its cells `C-O-D` read backwards as `DOC` were treated as legitimate even when `DOC` was a separate hidden target.
- **Impact:** Same symptom as bug #16 — a readable copy of a hidden word that cannot be solved.
- **Fix:** `_stray_word_cells` only considers words actually placed on this board (chosen targets + placed decoys), and a sub-run is exempt only when the reading that matches a placed word is a substring of the containing word in that direction. Layouts where placed letters still collide are rejected and regenerated.
- **Devin session:** https://app.devin.ai/sessions/72e9503ebf3d48578c53ab4826946869
- **PR:** https://github.com/ak777app/battleship/pull/5
