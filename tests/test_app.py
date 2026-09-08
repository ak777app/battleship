import random

import pytest

import app
from app import (
    DECOY_WORD_BANK,
    GRID_SIZE,
    SHIPS,
    TARGET_WORD_BANK,
    WORD_SLOT_LENGTHS,
    BattleshipGame,
    board_updates,
    cell_symbol,
    format_coordinate,
    handle_grid_click,
    mode_view_updates,
    orientation_toggle,
    reset_game_handler,
    toggle_mode_handler,
    word_cell_update,
)

CELLS = GRID_SIZE * GRID_SIZE


def empty_grid():
    return [["~" for _ in range(GRID_SIZE)] for _ in range(GRID_SIZE)]


def count(grid, symbol):
    return sum(cell == symbol for row in grid for cell in row)


@pytest.fixture(autouse=True)
def seed():
    random.seed(1234)


@pytest.fixture
def classic():
    return BattleshipGame()


@pytest.fixture
def playing(classic):
    """Classic game in the playing phase with a fully controlled ai_ships grid."""
    classic.game_phase = "playing"
    classic.ai_ships = empty_grid()
    classic.ai_ships[0][0] = "S"
    classic.ai_ships[0][1] = "S"
    classic.player_ships = empty_grid()
    classic.player_ships[5][5] = "S"
    classic.player_grid = empty_grid()
    classic.player_grid[5][5] = "S"
    return classic


@pytest.fixture
def word():
    g = BattleshipGame()
    g.toggle_mode()
    return g


@pytest.fixture
def quiet_ai(monkeypatch):
    """Make the AI turn deterministic and harmless."""
    monkeypatch.setattr(BattleshipGame, "_ai_attack", lambda self: "AI Missed at J10")


@pytest.fixture
def warning_spy(monkeypatch):
    calls = []
    monkeypatch.setattr(app.gr, "Warning", lambda msg: calls.append(msg))
    return calls


# --------------------------------------------------------------------------- module helpers

@pytest.mark.parametrize("pos, expected", [((0, 0), "A1"), ((3, 1), "B4"), ((9, 9), "J10")])
def test_format_coordinate(pos, expected):
    assert format_coordinate(*pos) == expected


@pytest.mark.parametrize("cell, show_ships, letters, expected", [
    ("a", True, True, "A"),
    ("D", False, True, "D"),
    ("X", True, False, "💥"),
    ("X", True, True, "X"),
    ("O", False, False, "⚪"),
    ("S", True, False, "🚢"),
    ("S", False, False, "🌊"),
    ("~", True, False, "🌊"),
    ("~", True, True, "🌊"),
])
def test_cell_symbol(cell, show_ships, letters, expected):
    assert cell_symbol(cell, show_ships, letters=letters) == expected


# --------------------------------------------------------------------------- classic setup / reset

def test_defaults(classic):
    assert classic.mode == "classic"
    assert classic.game_phase == "placement"
    assert classic.total_ship_cells == 17
    assert classic.turn == "player"
    assert classic.ship_orientation == "horizontal"
    assert classic.current_ship_index == 0
    for grid in (classic.player_grid, classic.ai_grid, classic.player_ships):
        assert len(grid) == GRID_SIZE and all(len(row) == GRID_SIZE for row in grid)
        assert count(grid, "~") == CELLS
    assert count(classic.ai_ships, "S") == 17
    assert classic.message == "Place your Carrier (5 cells)"
    assert classic.target_words == [] and classic.decoy_words == [] and classic.selected_cells == []


def test_reset_game_clears_state(classic):
    classic.game_phase = "playing"
    classic.player_hits = 5
    classic.ai_hits = 3
    classic.current_ship_index = 4
    classic.ship_orientation = "vertical"
    classic.selected_cells = [(0, 0)]
    classic.ai_target_mode = True
    classic.ai_target_queue = [(1, 1)]
    classic.ai_last_hit = (0, 0)
    classic.player_grid[0][0] = "X"
    old_ai_ships = classic.ai_ships

    classic.reset_game()

    assert classic.game_phase == "placement"
    assert classic.player_hits == 0 and classic.ai_hits == 0
    assert classic.current_ship_index == 0
    assert classic.ship_orientation == "horizontal"
    assert classic.selected_cells == []
    assert classic.ai_target_mode is False and classic.ai_target_queue == [] and classic.ai_last_hit is None
    assert count(classic.player_grid, "~") == CELLS
    assert classic.ai_ships is not old_ai_ships
    assert count(classic.ai_ships, "S") == 17


# --------------------------------------------------------------------------- ship placement

def test_place_ship_outside_placement_phase(classic):
    classic.game_phase = "playing"
    assert classic.place_ship(0, 0) == "Not in placement phase!"
    assert classic.current_ship_index == 0


def test_place_ship_horizontal(classic):
    msg = classic.place_ship(2, 3)
    assert msg == "Place your Battleship (4 cells)"
    assert classic.current_ship_index == 1
    for c in range(3, 8):
        assert classic.player_ships[2][c] == "S"
        assert classic.player_grid[2][c] == "S"
    assert count(classic.player_ships, "S") == 5
    assert count(classic.player_grid, "S") == 5


def test_place_ship_vertical(classic):
    classic.toggle_orientation()
    msg = classic.place_ship(4, 9)
    assert msg == "Place your Battleship (4 cells)"
    for r in range(4, 9):
        assert classic.player_ships[r][9] == "S"
        assert classic.player_grid[r][9] == "S"
    assert count(classic.player_ships, "S") == 5


def test_place_all_ships_starts_game(classic):
    for row in range(len(SHIPS)):
        msg = classic.place_ship(row, 0)
    assert msg == "All ships placed! Your turn - click on AI grid to fire!"
    assert classic.game_phase == "playing"
    assert classic.current_ship_index == len(SHIPS)
    assert count(classic.player_ships, "S") == 17


def test_place_ship_out_of_bounds(classic):
    msg = classic.place_ship(0, 6)
    assert msg == "Cannot place Carrier there! Try another position."
    assert classic.current_ship_index == 0
    assert count(classic.player_ships, "S") == 0


def test_place_ship_overlapping(classic):
    classic.place_ship(0, 0)
    msg = classic.place_ship(0, 4)  # Battleship over last Carrier cell
    assert msg == "Cannot place Battleship there! Try another position."
    assert classic.current_ship_index == 1
    assert count(classic.player_ships, "S") == 5


def test_can_place_ship_bounds_and_overlap(classic):
    grid = empty_grid()
    assert classic._can_place_ship(grid, 0, 5, 5, "horizontal") is True
    assert classic._can_place_ship(grid, 0, 6, 5, "horizontal") is False
    assert classic._can_place_ship(grid, 5, 0, 5, "vertical") is True
    assert classic._can_place_ship(grid, 6, 0, 5, "vertical") is False
    grid[0][7] = "S"
    assert classic._can_place_ship(grid, 0, 5, 3, "horizontal") is False
    assert classic._can_place_ship(grid, 0, 4, 3, "horizontal") is True
    grid[3][0] = "S"
    assert classic._can_place_ship(grid, 1, 0, 3, "vertical") is False
    assert classic._can_place_ship(grid, 0, 0, 3, "vertical") is True


def test_can_place_ship_isolated(classic):
    grid = empty_grid()
    grid[5][5] = "S"
    # touches diagonally at (4,4)-(4,6): fine without isolation, rejected with it
    assert classic._can_place_ship(grid, 4, 2, 3, "horizontal") is True
    assert classic._can_place_ship(grid, 4, 2, 3, "horizontal", isolated=True) is False
    # one-cell gap satisfied
    assert classic._can_place_ship(grid, 3, 2, 3, "horizontal", isolated=True) is True
    assert classic._can_place_ship(grid, 0, 7, 4, "vertical", isolated=True) is True
    assert classic._can_place_ship(grid, 3, 6, 4, "vertical", isolated=True) is False
    # bounds still enforced
    assert classic._can_place_ship(grid, 0, 8, 3, "horizontal", isolated=True) is False
    assert classic._can_place_ship(grid, 8, 0, 3, "vertical", isolated=True) is False


def test_toggle_orientation(classic):
    assert classic.toggle_orientation() == "Orientation: vertical. Place Carrier (5 cells)"
    assert classic.ship_orientation == "vertical"
    assert classic.toggle_orientation() == "Orientation: horizontal. Place Carrier (5 cells)"
    assert classic.ship_orientation == "horizontal"


def test_toggle_orientation_outside_placement(classic):
    classic.game_phase = "playing"
    classic.message = "status"
    assert classic.toggle_orientation() == "status"
    assert classic.ship_orientation == "horizontal"


# --------------------------------------------------------------------------- AI ship placement

@pytest.mark.parametrize("seed_value", range(5))
def test_place_ai_ships_fleet(seed_value, monkeypatch):
    random.seed(seed_value)
    placed_before = {}
    original = BattleshipGame._backtrack_place_ships

    def spy(self, ship_list, index, letters=False):
        placed_before[index] = count(self.ai_ships, "S")
        return original(self, ship_list, index, letters)
    monkeypatch.setattr(BattleshipGame, "_backtrack_place_ships", spy)

    g = BattleshipGame()
    assert count(g.ai_ships, "S") == g.total_ship_cells
    # on the successful path each ship adds exactly its own size before the next index is entered
    sizes = list(SHIPS.values())
    for i, size in enumerate(sizes):
        assert placed_before[i + 1] - placed_before[i] == size
    assert placed_before[len(sizes)] == 17


def test_place_ai_ships_unsatisfiable_raises(classic, monkeypatch):
    monkeypatch.setattr(BattleshipGame, "_backtrack_place_ships", lambda *a, **k: False)
    with pytest.raises(RuntimeError, match="Cannot place fleet"):
        classic._place_ai_ships()


def test_backtrack_places_all_ships_when_possible(classic):
    classic.ai_ships = empty_grid()
    assert classic._backtrack_place_ships(list(SHIPS.items()), 0) is True
    assert count(classic.ai_ships, "S") == 17


def test_backtrack_fails_and_restores_grid(classic):
    classic.ai_ships = empty_grid()
    # leave only a 2x2 free corner: a 3-ship cannot fit
    for r in range(GRID_SIZE):
        for c in range(GRID_SIZE):
            if not (r < 2 and c < 2):
                classic.ai_ships[r][c] = "S"
    snapshot = [row[:] for row in classic.ai_ships]
    assert classic._backtrack_place_ships([("Destroyer", 2), ("Cruiser", 3)], 0) is False
    assert classic.ai_ships == snapshot


def test_backtrack_letters_records_and_pops_words(classic):
    classic.ai_ships = empty_grid()
    classic.target_words = []
    assert classic._backtrack_place_ships([("FIX", 3), ("PR", 2)], 0, letters=True) is True
    assert [w["word"] for w in classic.target_words] == ["FIX", "PR"]
    for entry in classic.target_words:
        assert "".join(classic.ai_ships[r][c] for r, c in entry["cells"]) == entry["word"]
        assert entry["solved"] is False

    # only room for FIX (with its one-cell gap): PR cannot follow, so FIX is recorded then popped
    classic.ai_ships = empty_grid()
    classic.target_words = []
    free = {(0, 0), (0, 1), (0, 2), (0, 3), (1, 0), (1, 1), (1, 2), (1, 3)}
    for r in range(GRID_SIZE):
        for c in range(GRID_SIZE):
            if (r, c) not in free:
                classic.ai_ships[r][c] = "Z"
    assert classic._backtrack_place_ships([("FIX", 3), ("PR", 2)], 0, letters=True) is False
    assert classic.target_words == []
    assert all(classic.ai_ships[r][c] == "~" for r, c in free)


def test_isolated():
    grid = empty_grid()
    assert BattleshipGame._isolated(grid, -1, 0) is False
    assert BattleshipGame._isolated(grid, 0, GRID_SIZE) is False
    assert BattleshipGame._isolated(grid, 4, 4) is True
    grid[5][5] = "S"
    assert BattleshipGame._isolated(grid, 5, 5) is False
    for dr in (-1, 0, 1):
        for dc in (-1, 0, 1):
            assert BattleshipGame._isolated(grid, 5 + dr, 5 + dc) is False
    assert BattleshipGame._isolated(grid, 3, 5) is True
    assert BattleshipGame._isolated(grid, 7, 7) is True


# --------------------------------------------------------------------------- player attack

def test_player_attack_wrong_phase(classic):
    assert classic.player_attack(0, 0) == "Game not started or already ended!"
    classic.game_phase = "ended"
    assert classic.player_attack(0, 0) == "Game not started or already ended!"


def test_player_attack_not_player_turn(playing):
    playing.turn = "ai"
    assert playing.player_attack(0, 0) == "Wait for AI turn!"


def test_player_attack_already_attacked(playing, quiet_ai):
    playing.ai_grid[3][3] = "O"
    assert playing.player_attack(3, 3) == "Already attacked this position!"


def test_player_attack_hit(playing, quiet_ai):
    msg = playing.player_attack(0, 1)
    assert msg == "Hit at B1!\nAI Missed at J10"
    assert playing.ai_grid[0][1] == "X"
    assert playing.player_hits == 1
    assert playing.turn == "player"
    assert playing.game_phase == "playing"


def test_player_attack_miss(playing, quiet_ai):
    msg = playing.player_attack(7, 2)
    assert msg == "Miss at C8\nAI Missed at J10"
    assert playing.ai_grid[7][2] == "O"
    assert playing.player_hits == 0


def test_player_attack_win(playing, quiet_ai):
    playing.player_hits = playing.total_ship_cells - 1
    msg = playing.player_attack(0, 0)
    assert msg == "🎉 You Win! All AI ships destroyed!"
    assert playing.game_phase == "ended"
    assert playing.player_hits == playing.total_ship_cells


# --------------------------------------------------------------------------- AI attack

def test_ai_attack_random_hit_enters_target_mode(playing, monkeypatch):
    monkeypatch.setattr(app.random, "choice", lambda seq: (5, 5))
    msg = playing._ai_attack()
    assert msg == "AI Hit your ship at F6!"
    assert playing.player_grid[5][5] == "X"
    assert playing.ai_hits == 1
    assert playing.ai_target_mode is True
    assert playing.ai_last_hit == (5, 5)
    assert playing.ai_target_queue == [(4, 5), (6, 5), (5, 4), (5, 6)]


def test_ai_attack_queue_skips_out_of_bounds_and_attacked(playing, monkeypatch):
    playing.player_ships[0][0] = "S"
    playing.player_grid[0][0] = "S"
    playing.player_grid[0][1] = "O"
    monkeypatch.setattr(app.random, "choice", lambda seq: (0, 0))
    playing._ai_attack()
    assert playing.ai_target_queue == [(1, 0)]


def test_ai_attack_random_miss(playing, monkeypatch):
    monkeypatch.setattr(app.random, "choice", lambda seq: (2, 2))
    msg = playing._ai_attack()
    assert msg == "AI Missed at C3"
    assert playing.player_grid[2][2] == "O"
    assert playing.ai_hits == 0
    assert playing.ai_target_mode is False


def test_ai_attack_miss_clears_target_mode_when_queue_empty(playing):
    playing.ai_target_mode = True
    playing.ai_target_queue = [(2, 2)]
    msg = playing._ai_attack()
    assert msg == "AI Missed at C3"
    assert playing.ai_target_queue == []
    assert playing.ai_target_mode is False


def test_ai_attack_miss_keeps_target_mode_when_queue_nonempty(playing):
    playing.ai_target_mode = True
    playing.ai_target_queue = [(2, 2), (3, 3)]
    playing._ai_attack()
    assert playing.ai_target_queue == [(3, 3)]
    assert playing.ai_target_mode is True


def test_ai_attack_smart_targeting_pops_queue(playing, monkeypatch):
    def boom(seq):
        raise AssertionError("random.choice must not be used in target mode")
    monkeypatch.setattr(app.random, "choice", boom)
    playing.ai_target_mode = True
    playing.ai_target_queue = [(5, 5), (9, 9)]
    msg = playing._ai_attack()
    assert msg == "AI Hit your ship at F6!"
    assert playing.ai_target_queue == [(9, 9), (4, 5), (6, 5), (5, 4), (5, 6)]


def test_ai_attack_random_when_target_mode_but_queue_empty(playing, monkeypatch):
    playing.ai_target_mode = True
    playing.ai_target_queue = []
    monkeypatch.setattr(app.random, "choice", lambda seq: (1, 1))
    assert playing._ai_attack() == "AI Missed at B2"


def test_ai_attack_win(playing):
    playing.ai_hits = playing.total_ship_cells - 1
    playing.ai_target_mode = True
    playing.ai_target_queue = [(5, 5)]
    msg = playing._ai_attack()
    assert msg == "💀 AI Wins! All your ships destroyed!"
    assert playing.game_phase == "ended"


def test_ai_attack_no_moves(playing):
    playing.player_grid = [["O" for _ in range(GRID_SIZE)] for _ in range(GRID_SIZE)]
    assert playing._ai_attack() == "AI has no moves!"


# --------------------------------------------------------------------------- word mode

def test_toggle_mode_starts_word_game(word):
    assert word.mode == "word"
    assert word.game_phase == "playing"
    assert word.current_ship_index == len(SHIPS)
    assert len(word.target_words) == 5
    assert sorted((len(w["word"]) for w in word.target_words), reverse=True) == WORD_SLOT_LENGTHS
    for entry in word.target_words:
        assert entry["word"] in TARGET_WORD_BANK[len(entry["word"])]
        assert "".join(word.ai_ships[r][c] for r, c in entry["cells"]) == entry["word"]
        assert entry["solved"] is False
    assert count(word.player_ships, "S") == 17
    assert word.player_grid == word.player_ships
    assert "Solved 0/5" in word.message
    assert "Find 5 hidden words" in word.message


def test_toggle_mode_back_to_classic(word):
    word.toggle_mode()
    assert word.mode == "classic"
    assert word.game_phase == "placement"
    assert word.target_words == []
    assert count(word.ai_ships, "S") == 17


def test_toggle_mode_via_mode_and_reset():
    g = BattleshipGame()
    g.mode = "word"
    g.reset_game()
    assert g.game_phase == "playing"
    assert len(g.target_words) == 5


@pytest.mark.parametrize("seed_value", range(5))
def test_place_ai_words_layout(seed_value):
    random.seed(seed_value)
    g = BattleshipGame()
    g.mode = "word"
    g.reset_game()
    words = [w["word"] for w in g.target_words]
    assert len(set(words)) == 5
    for w in words:
        assert not any(w != o and (w in o or o in w) for o in words)
    # target words keep a one-cell gap from each other
    for entry in g.target_words:
        others = {c for o in g.target_words if o is not entry for c in o["cells"]}
        for r, c in entry["cells"]:
            for dr in (-1, 0, 1):
                for dc in (-1, 0, 1):
                    assert (r + dr, c + dc) not in others
    for decoy in g.decoy_words:
        assert decoy["word"] in DECOY_WORD_BANK
        assert decoy["reason"] == DECOY_WORD_BANK[decoy["word"]]
        assert "".join(g.ai_ships[r][c] for r, c in decoy["cells"]) == decoy["word"]
    assert len(g.decoy_words) > 0
    # every cell is a letter and no unrecorded bank word can be read anywhere
    assert all(cell.isalpha() and len(cell) == 1 for row in g.ai_ships for cell in row)
    assert g._stray_word_cells() == set()


def test_place_ai_words_gives_up_after_50_attempts(word, monkeypatch):
    attempts = []
    monkeypatch.setattr(BattleshipGame, "_try_place_ai_words", lambda self: attempts.append(1) or False)
    with pytest.raises(RuntimeError, match="stray words"):
        word._place_ai_words()
    assert len(attempts) == 50


def test_try_place_ai_words_unplaceable_targets_raises(word, monkeypatch):
    monkeypatch.setattr(BattleshipGame, "_backtrack_place_ships", lambda *a, **k: False)
    with pytest.raises(RuntimeError, match="Cannot place target words"):
        word._try_place_ai_words()


def test_try_place_ai_words_skips_unplaceable_decoys(word, monkeypatch):
    original = BattleshipGame._place_word_anywhere
    monkeypatch.setattr(BattleshipGame, "_place_word_anywhere",
                        lambda self, w: None if w == "ONCALL" else original(self, w))
    assert any(word._try_place_ai_words() for _ in range(50))  # a single layout attempt may be rejected
    placed = {d["word"] for d in word.decoy_words}
    assert "ONCALL" not in placed
    assert placed  # other decoys still land


def test_fill_camouflage_rerolls_stray_filler(word, monkeypatch):
    word.ai_ships = empty_grid()
    word.target_words = []
    word.decoy_words = []
    letters = iter(["P", "R"] + ["Z"] * 500)  # PR (or RP, reversed) is a stray bank word
    monkeypatch.setattr(app.random, "choice", lambda seq: next(letters))
    assert word._fill_camouflage([(0, 0), (0, 1)]) is True
    assert word.ai_ships[0][:2] == ["Z", "Z"]


def test_fill_camouflage_rejects_stray_made_of_placed_letters(word):
    word.ai_ships = empty_grid()
    word.target_words = []
    word.decoy_words = []
    for c, letter in enumerate("FIX"):
        word.ai_ships[0][c] = letter
    assert word._fill_camouflage([(9, 9)]) is False


def test_fill_camouflage_gives_up_after_200_rounds(word, monkeypatch):
    word.ai_ships = empty_grid()
    word.target_words = []
    word.decoy_words = []
    # cells (0,0),(0,1) are filler; force them to always spell PR
    letters = iter(["P", "R"] * 1000)
    monkeypatch.setattr(app.random, "choice", lambda seq: next(letters))
    assert word._fill_camouflage([(0, 0), (0, 1)]) is False


def test_stray_word_cells_detects_unrecorded_words(word):
    word.ai_ships = empty_grid()
    word.target_words = []
    word.decoy_words = []
    for c, letter in enumerate("FIX"):
        word.ai_ships[0][c] = letter
    assert word._stray_word_cells() == {(0, 0), (0, 1), (0, 2)}
    # reversed reading, vertical
    word.ai_ships = empty_grid()
    for r, letter in enumerate("RP"):
        word.ai_ships[r + 3][4] = letter
    assert word._stray_word_cells() == {(3, 4), (4, 4)}


def test_stray_word_cells_ignores_recorded_placements(word):
    word.ai_ships = empty_grid()
    for c, letter in enumerate("FIX"):
        word.ai_ships[0][c] = letter
    for r, letter in enumerate("HIRE"):
        word.ai_ships[r + 2][7] = letter
    word.target_words = [{"word": "FIX", "cells": [(0, 0), (0, 1), (0, 2)], "solved": False}]
    word.decoy_words = [{"word": "HIRE", "cells": [(2, 7), (3, 7), (4, 7), (5, 7)], "reason": "r"}]
    assert word._stray_word_cells() == set()
    # a second, unrecorded copy of a recorded word is still stray
    for c, letter in enumerate("FIX"):
        word.ai_ships[9][c] = letter
    assert word._stray_word_cells() == {(9, 0), (9, 1), (9, 2)}


def test_stray_word_cells_sub_run_rules(word):
    # DOC read backwards inside a placed CODE is fine when DOC is not placed elsewhere...
    word.ai_ships = empty_grid()
    cells = [(0, c) for c in range(4)]
    for (r, c), letter in zip(cells, "CODE"):
        word.ai_ships[r][c] = letter
    word.target_words = [{"word": "CODE", "cells": cells, "solved": False}]
    word.decoy_words = []
    assert word._stray_word_cells() == set()
    # ...but not when DOC is itself a placed target
    doc_cells = [(5, 0), (5, 1), (5, 2)]
    for (r, c), letter in zip(doc_cells, "DOC"):
        word.ai_ships[r][c] = letter
    word.target_words.append({"word": "DOC", "cells": doc_cells, "solved": False})
    assert word._stray_word_cells() == {(0, 0), (0, 1), (0, 2)}


def test_place_word_anywhere(word):
    word.ai_ships = empty_grid()
    cells = word._place_word_anywhere("DEMO")
    assert len(cells) == 4
    assert "".join(word.ai_ships[r][c] for r, c in cells) == "DEMO"
    rows = {r for r, _ in cells}
    cols = {c for _, c in cells}
    assert len(rows) == 1 or len(cols) == 1


def test_place_word_anywhere_no_space(word):
    word.ai_ships = [["Z" for _ in range(GRID_SIZE)] for _ in range(GRID_SIZE)]
    word.ai_ships[0][0] = "~"
    assert word._place_word_anywhere("OK") is None
    assert word.ai_ships[0][0] == "~"


def test_place_word_anywhere_vertical_when_forced(word):
    word.ai_ships = [["Z" for _ in range(GRID_SIZE)] for _ in range(GRID_SIZE)]
    for r in range(3):
        word.ai_ships[r][0] = "~"
    assert word._place_word_anywhere("OWN") == [(0, 0), (1, 0), (2, 0)]


def test_spells(word):
    cells = [(0, 0), (0, 1), (0, 2)]
    word.selected_cells = list(cells)
    assert word._spells(cells) is True
    word.selected_cells = cells[::-1]
    assert word._spells(cells) is True
    word.selected_cells = [(0, 1), (0, 0), (0, 2)]
    assert word._spells(cells) is False
    word.selected_cells = cells[:2]
    assert word._spells(cells) is False
    word.selected_cells = []
    assert word._spells(cells) is False


def test_solved_and_target_cells(word):
    word.target_words = [
        {"word": "PR", "cells": [(0, 0), (0, 1)], "solved": True},
        {"word": "FIX", "cells": [(2, 0), (2, 1), (2, 2)], "solved": False},
    ]
    assert word._solved_cells() == {(0, 0), (0, 1)}
    assert word._target_cells() == {(0, 0), (0, 1), (2, 0), (2, 1), (2, 2)}


def controlled_word_game(g):
    """Two targets (FIX, PR) and one decoy (OK) at known coordinates."""
    g.ai_ships = [["Z" for _ in range(GRID_SIZE)] for _ in range(GRID_SIZE)]
    for c, letter in enumerate("FIX"):
        g.ai_ships[0][c] = letter
    for c, letter in enumerate("PR"):
        g.ai_ships[2][c] = letter
    for c, letter in enumerate("OK"):
        g.ai_ships[4][c] = letter
    g.target_words = [
        {"word": "FIX", "cells": [(0, 0), (0, 1), (0, 2)], "solved": False},
        {"word": "PR", "cells": [(2, 0), (2, 1)], "solved": False},
    ]
    g.decoy_words = [{"word": "OK", "cells": [(4, 0), (4, 1)], "reason": DECOY_WORD_BANK["OK"]}]
    g.selected_cells = []
    g.solved_count = 0
    return g


def test_select_cell_toggles_selection(word, quiet_ai):
    controlled_word_game(word)
    msg = word.select_cell(0, 0)
    assert word.selected_cells == [(0, 0)]
    assert msg == "Selected: F (1 letters). Words run straight across or down. Solved 0/2\nAI Missed at J10"
    word.select_cell(0, 1)
    assert word.selected_cells == [(0, 0), (0, 1)]
    msg = word.select_cell(0, 0)
    assert word.selected_cells == [(0, 1)]
    assert msg.startswith("Selected: I (1 letters).")


def test_select_cell_solved_cell(word, quiet_ai):
    controlled_word_game(word)
    word.target_words[1]["solved"] = True
    assert word.select_cell(2, 1) == "B3 is already part of a solved word."
    assert word.selected_cells == []


def test_select_cell_not_playing(word):
    word.game_phase = "ended"
    word.message = "done"
    assert word.select_cell(0, 0) == "done"


def test_select_cell_solves_word(word, quiet_ai):
    controlled_word_game(word)
    word.select_cell(0, 0)
    word.select_cell(0, 1)
    msg = word.select_cell(0, 2)
    assert msg == "✅ FIX solved! 1/2 words found.\nAI Missed at J10"
    assert word.target_words[0]["solved"] is True
    assert word.solved_count == 1
    assert word.selected_cells == []
    assert word.game_phase == "playing"


def test_select_cell_win(word, quiet_ai):
    controlled_word_game(word)
    word.target_words[0]["solved"] = True
    word.solved_count = 1
    word.select_cell(2, 1)
    msg = word.select_cell(2, 0)  # backwards spelling counts
    assert msg == "🎉 You Win! All 2 words found — every task a job for Devin!"
    assert word.game_phase == "ended"
    assert word.solved_count == 2


def test_select_cell_ai_wins(word, monkeypatch):
    controlled_word_game(word)

    def ai_wins(self):
        self.game_phase = "ended"
        return "💀 AI Wins! All your ships destroyed!"
    monkeypatch.setattr(BattleshipGame, "_ai_attack", ai_wins)
    msg = word.select_cell(0, 0)
    assert msg == "💀 AI Wins! All your ships destroyed!"
    assert word.message == msg


def test_select_cell_runs_real_ai_turn(word):
    controlled_word_game(word)
    before = count(word.player_grid, "~") + count(word.player_grid, "S")
    word.select_cell(0, 0)
    after = count(word.player_grid, "~") + count(word.player_grid, "S")
    assert after == before - 1
    assert "AI " in word.message.splitlines()[-1]


def test_word_turn_decoy(word, warning_spy):
    controlled_word_game(word)
    word.selected_cells = [(4, 0), (4, 1)]
    word._word_turn(4, 1)
    assert word.selected_cells == []
    assert word.solved_count == 0
    assert word.message == ("🚫 OK is a task better owned by humans — not a target. Solved 0/2")
    assert warning_spy == [f"🚫 OK: {DECOY_WORD_BANK['OK']}"]


def test_word_turn_target(word, warning_spy):
    controlled_word_game(word)
    word.selected_cells = [(2, 1), (2, 0)]
    word._word_turn(2, 0)
    assert word.message == "✅ PR solved! 1/2 words found."
    assert word.target_words[1]["solved"] is True
    assert warning_spy == []


def test_word_turn_empty_and_partial(word):
    controlled_word_game(word)
    word.selected_cells = []
    word._word_turn(0, 0)
    assert word.message == "Selection cleared. Solved 0/2"
    word.selected_cells = [(0, 2), (0, 1)]
    word._word_turn(0, 1)
    assert word.message == "Selected: XI (2 letters). Words run straight across or down. Solved 0/2"


def test_clear_selection(word):
    word.selected_cells = [(0, 0), (1, 1)]
    word.solved_count = 2
    assert word.clear_selection() == "Selection cleared. Solved 2/5"
    assert word.selected_cells == []


def test_clear_selection_after_game_ended(word):
    word.game_phase = "ended"
    word.message = "final"
    word.selected_cells = [(0, 0)]
    assert word.clear_selection() == "final"
    assert word.selected_cells == []


def test_auto_place_player_ships_isolated(word):
    for _ in range(5):
        word._auto_place_player_ships()
        grid = word.player_ships
        assert count(grid, "S") == 17
        for r in range(GRID_SIZE):
            for c in range(GRID_SIZE):
                if grid[r][c] != "S":
                    continue
                # no diagonal neighbours
                for dr, dc in ((-1, -1), (-1, 1), (1, -1), (1, 1)):
                    nr, nc = r + dr, c + dc
                    if 0 <= nr < GRID_SIZE and 0 <= nc < GRID_SIZE:
                        assert grid[nr][nc] != "S"
        assert word.player_grid == grid and word.player_grid is not grid


def test_auto_place_player_ships_gives_up(word, monkeypatch):
    monkeypatch.setattr(BattleshipGame, "_place_spread_fleet", lambda self, grid: False)
    with pytest.raises(RuntimeError, match="auto-place"):
        word._auto_place_player_ships()


def test_place_spread_fleet_no_room(word):
    grid = empty_grid()
    for r in range(0, GRID_SIZE, 2):
        for c in range(0, GRID_SIZE, 2):
            grid[r][c] = "S"
    assert word._place_spread_fleet(grid) is False


def test_place_spread_fleet_prefers_edges(word):
    grid = empty_grid()
    assert word._place_spread_fleet(grid) is True
    edge_cells = sum(grid[r][c] == "S" and (r in (0, 9) or c in (0, 9))
                     for r in range(GRID_SIZE) for c in range(GRID_SIZE))
    assert edge_cells >= 9  # carrier + battleship both hug an edge


# --------------------------------------------------------------------------- handlers (per-session game)

@pytest.fixture
def global_classic():
    return BattleshipGame()


@pytest.fixture
def global_word():
    g = BattleshipGame()
    g.toggle_mode()
    controlled_word_game(g)
    return g


def test_word_cell_update(global_word):
    upd = word_cell_update(global_word, 9, 9)
    assert upd["value"] == "Z"
    assert upd["variant"] == "secondary"
    assert upd["elem_classes"] == ["word-cell"]
    upd = word_cell_update(global_word, 0, 0)
    assert upd["value"] == "F"
    assert upd["elem_classes"] == ["word-cell", "target-cell"]
    global_word.selected_cells = [(0, 0)]
    upd = word_cell_update(global_word, 0, 0)
    assert upd["variant"] == "primary"
    assert upd["elem_classes"] == ["word-cell", "target-cell", "selected-cell"]
    global_word.target_words[0]["solved"] = True
    upd = word_cell_update(global_word, 0, 0)
    assert upd["variant"] == "secondary"
    assert upd["elem_classes"] == ["word-cell", "target-cell", "solved-cell"]


def test_board_updates_classic(global_classic):
    global_classic.player_grid[0][0] = "S"
    global_classic.ai_grid[1][1] = "X"
    global_classic.ai_ships[2][2] = "S"
    updates = board_updates(global_classic)
    assert len(updates) == 2 * CELLS
    assert updates[0]["value"] == "🚢"
    assert updates[CELLS + 11]["value"] == "💥"
    assert updates[CELLS + 22]["value"] == "🌊"  # AI ships stay hidden
    assert all("elem_classes" not in u for u in updates)


def test_board_updates_word(global_word):
    updates = board_updates(global_word)
    assert len(updates) == 2 * CELLS
    assert updates[CELLS]["value"] == "F"
    assert "word-cell" in updates[CELLS]["elem_classes"]
    assert count(global_word.player_grid, "S") == sum(u["value"] == "🚢" for u in updates[:CELLS])


def test_handle_grid_click_word_mode(global_word, quiet_ai):
    result = handle_grid_click(global_word, 0, 0, is_ai_grid=True)
    assert len(result) == 2 + 2 * CELLS
    assert result[1].startswith("Selected: F (1 letters).")
    assert global_word.selected_cells == [(0, 0)]
    assert result[2 + CELLS]["variant"] == "primary"
    # own grid is inert in word mode
    result = handle_grid_click(global_word, 5, 5, is_ai_grid=False)
    assert result[1] == global_word.message
    assert global_word.selected_cells == [(0, 0)]


def test_handle_grid_click_placement(global_classic):
    result = handle_grid_click(global_classic, 0, 0, is_ai_grid=True)
    assert result[1] == "Place your ships on your own grid (left)!"
    assert global_classic.current_ship_index == 0
    result = handle_grid_click(global_classic, 0, 0, is_ai_grid=False)
    assert result[1] == "Place your Battleship (4 cells)"
    assert len(result) == 2 + 2 * CELLS
    assert [u["value"] for u in result[2:7]] == ["🚢"] * 5


def test_handle_grid_click_playing(global_classic, quiet_ai):
    global_classic.game_phase = "playing"
    global_classic.ai_ships = empty_grid()
    result = handle_grid_click(global_classic, 3, 3, is_ai_grid=False)
    assert result[1] == "Fire at the AI grid (right)!"
    assert global_classic.ai_grid[3][3] == "~"
    result = handle_grid_click(global_classic, 3, 3, is_ai_grid=True)
    assert result[1] == "Miss at D4\nAI Missed at J10"
    assert result[2 + CELLS + 33]["value"] == "⚪"


def test_handle_grid_click_ended(global_classic):
    global_classic.game_phase = "ended"
    global_classic.message = "over"
    assert handle_grid_click(global_classic, 0, 0, is_ai_grid=True)[1] == "over"


def test_handle_cell_click_is_noop():
    assert app.handle_cell_click(None) is None


def test_orientation_toggle(global_classic):
    assert orientation_toggle(global_classic) == [global_classic, "Orientation: vertical. Place Carrier (5 cells)"]
    assert global_classic.ship_orientation == "vertical"


def test_reset_game_handler(global_classic):
    global_classic.place_ship(0, 0)
    result = reset_game_handler(global_classic)
    assert len(result) == 2 + 2 * CELLS
    assert result[1] == "Place your Carrier (5 cells)"
    assert global_classic.current_ship_index == 0
    assert all(u["value"] == "🌊" for u in result[2:])


def test_mode_view_updates(global_classic):
    upd = mode_view_updates(global_classic)
    assert len(upd) == 6
    assert upd[0]["value"] == "### Your Grid"
    assert upd[1]["visible"] is True
    assert upd[2]["visible"] is False
    assert upd[3]["value"] == "### AI Grid (Click to attack)"
    assert upd[4]["value"] == "Switch to Word Puzzle Mode"
    assert upd[5]["elem_classes"] == []
    global_classic.mode = "word"
    upd = mode_view_updates(global_classic)
    assert upd[0]["value"].startswith("### Your Fleet")
    assert upd[1]["visible"] is False
    assert upd[2]["visible"] is True
    assert upd[3]["value"].startswith("### Word Puzzle Grid")
    assert upd[4]["value"] == "Switch to Classic Mode"
    assert upd[5]["elem_classes"] == ["word-mode"]


def test_toggle_mode_handler_to_word(global_classic):
    result = toggle_mode_handler(global_classic)
    assert global_classic.mode == "word"
    assert len(result) == 2 + 2 * CELLS + 6
    assert "Solved 0/5" in result[1]
    ai_updates = result[2 + CELLS:1 + 2 * CELLS]
    assert all("word-cell" in u["elem_classes"] for u in ai_updates)
    assert result[-1]["elem_classes"] == ["word-mode"]


def test_toggle_mode_handler_back_to_classic_strips_styling(global_word):
    result = toggle_mode_handler(global_word)
    assert global_word.mode == "classic"
    assert len(result) == 2 + 2 * CELLS + 6
    assert result[1] == "Place your Carrier (5 cells)"
    ai_updates = result[2 + CELLS:1 + 2 * CELLS]
    assert all(u["variant"] == "secondary" and u["elem_classes"] == [] for u in ai_updates)
    assert all(u["value"] == "🌊" for u in ai_updates)
    assert result[-1]["elem_classes"] == []


def test_clear_selection_handler(global_word):
    global_word.selected_cells = [(0, 0)]
    result = app.clear_selection_handler(global_word)
    assert result[1] == "Selection cleared. Solved 0/2"
    assert global_word.selected_cells == []
    assert len(result) == 2 + 2 * CELLS
    assert all(u["variant"] == "secondary" for u in result[2 + CELLS:])


def test_handlers_return_game_as_state(global_classic):
    assert handle_grid_click(global_classic, 0, 0, is_ai_grid=False)[0] is global_classic
    assert reset_game_handler(global_classic)[0] is global_classic
    assert toggle_mode_handler(global_classic)[0] is global_classic
    assert app.clear_selection_handler(global_classic)[0] is global_classic


def test_sessions_do_not_share_state(quiet_ai):
    """Two independent games (one per browser session) never see each other's moves"""
    a, b = BattleshipGame(), BattleshipGame()
    handle_grid_click(a, 0, 0, is_ai_grid=False)
    assert a.current_ship_index == 1
    assert b.current_ship_index == 0
    assert all(cell == "~" for row in b.player_grid for cell in row)
    toggle_mode_handler(b)
    assert b.mode == "word" and a.mode == "classic"


def test_create_interactive_grid():
    grid = empty_grid()
    grid[0][0] = "X"
    grid[0][1] = "O"
    grid[0][2] = "S"
    buttons = app.create_interactive_grid(grid)
    assert len(buttons) == GRID_SIZE and all(len(row) == GRID_SIZE for row in buttons)
    assert [b.value for b in buttons[0][:4]] == ["💥", "⚪", "🚢", "🌊"]
    assert app.create_interactive_grid(grid, is_ai_grid=True)[0][2].value == "🌊"
