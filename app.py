import gradio as gr
import random
import copy

# Game constants
GRID_SIZE = 10
SHIPS = {
    "Carrier": 5,
    "Battleship": 4,
    "Cruiser": 3,
    "Submarine": 3,
    "Destroyer": 2
}

# Word-puzzle mode: target "ships" are autonomous coding tasks Devin excels at,
# grouped by word length (5, 4, 3, 3, 2 letters, mirroring the classic fleet).
WORD_SLOT_LENGTHS = [5, 4, 3, 3, 2]
TARGET_WORD_BANK = {
    5: ["DEBUG", "BUILD", "PATCH", "MERGE"],
    4: ["TEST", "CODE", "LINT", "PORT", "REPO"],
    3: ["FIX", "RUN", "DOC", "GIT"],
    2: ["PR", "CI", "QA"],
}

# Decoys: SWE tasks that need human judgment, ownership, or a human in the loop.
DECOY_WORD_BANK = {
    "SCOPE": "Deciding what to build and why is a product judgment call for humans.",
    "HIRE": "Hiring and evaluating engineers needs human judgment and accountability.",
    "DEMO": "Live stakeholder demos need a human presenter reading the room.",
    "ONCALL": "Production incident ownership needs an accountable human on call.",
    "DESIGN": "System design trade-offs need human context, ownership and buy-in.",
    "OWN": "Long-term code ownership and accountability belong to a human team.",
    "ASK": "Gathering requirements from stakeholders is a human conversation.",
    "SLA": "Committing to service-level agreements is a business decision for humans.",
    "OK": "Final sign-off and approval should come from a human reviewer.",
}

class BattleshipGame:
    def __init__(self):
        self.mode = "classic"  # classic, word
        self.reset_game()
    
    def toggle_mode(self):
        """Flip between classic and word-puzzle mode, starting a fresh game"""
        self.mode = "word" if self.mode == "classic" else "classic"
        self.reset_game()
    
    def reset_game(self):
        self.player_grid = [["~" for _ in range(GRID_SIZE)] for _ in range(GRID_SIZE)]
        self.ai_grid = [["~" for _ in range(GRID_SIZE)] for _ in range(GRID_SIZE)]
        self.player_ships = [["~" for _ in range(GRID_SIZE)] for _ in range(GRID_SIZE)]
        self.ai_ships = [["~" for _ in range(GRID_SIZE)] for _ in range(GRID_SIZE)]
        
        self.player_hits = 0
        self.ai_hits = 0
        self.total_ship_cells = sum(SHIPS.values())
        
        self.game_phase = "placement"  # placement, playing, ended
        self.current_ship_index = 0
        self.ship_names = list(SHIPS.keys())
        self.ship_orientation = "horizontal"
        self.turn = "player"
        
        # AI targeting
        self.ai_last_hit = None
        self.ai_target_mode = False
        self.ai_target_queue = []
        
        # Word-puzzle state
        self.target_words = []   # [{"word", "cells", "solved"}]
        self.decoy_words = []    # [{"word", "cells", "reason"}]
        self.selected_cells = []
        self.solved_count = 0
        
        if self.mode == "word":
            self.game_phase = "playing"
            self._place_ai_words()
            self._auto_place_player_ships()
            self.current_ship_index = len(self.ship_names)
            self.message = (f"Your fleet is auto-placed. Find {len(self.target_words)} hidden words: click letters "
                            f"to spell a word — the AI fires at you after every click. Solved 0/{len(self.target_words)}")
        else:
            self.message = f"Place your {self.ship_names[0]} ({SHIPS[self.ship_names[0]]} cells)"
            self._place_ai_ships()
    
    def _place_ai_words(self):
        """Fill ai_ships with 5 target words, best-effort decoys, and random camouflage letters."""
        for _ in range(50):
            if self._try_place_ai_words():
                return
        raise RuntimeError("Could not generate a word grid without stray words.")
    
    def _try_place_ai_words(self):
        """One layout attempt; False if placed words accidentally spell an extra bank word."""
        self.ai_ships = [["~" for _ in range(GRID_SIZE)] for _ in range(GRID_SIZE)]
        self.target_words = []
        self.decoy_words = []
        
        chosen = []
        for length in WORD_SLOT_LENGTHS:
            options = [w for w in TARGET_WORD_BANK[length]
                       if not any(w in prev or prev in w for prev in chosen)]
            chosen.append(random.choice(options))
        
        if not self._backtrack_place_ships([(w, len(w)) for w in chosen], 0, letters=True):
            raise RuntimeError(f"Cannot place target words {chosen} on {GRID_SIZE}x{GRID_SIZE} board.")
        
        decoys = [w for w in DECOY_WORD_BANK if w not in chosen]
        random.shuffle(decoys)
        for word in decoys:
            cells = self._place_word_anywhere(word)
            if cells:
                self.decoy_words.append({"word": word, "cells": cells, "reason": DECOY_WORD_BANK[word]})
        
        filler = [(r, c) for r in range(GRID_SIZE) for c in range(GRID_SIZE) if self.ai_ships[r][c] == "~"]
        return self._fill_camouflage(filler)
    
    def _fill_camouflage(self, filler_cells):
        """Fill cells with random letters, re-rolling any that spell an unrecorded bank word."""
        filler = set(filler_cells)
        for r, c in filler:
            self.ai_ships[r][c] = random.choice("ABCDEFGHIJKLMNOPQRSTUVWXYZ")
        for _ in range(200):
            stray = self._stray_word_cells()
            if not stray:
                return True
            if not stray & filler:
                return False  # stray word is made of placed letters; needs a new layout
            for r, c in stray & filler:
                self.ai_ships[r][c] = random.choice("ABCDEFGHIJKLMNOPQRSTUVWXYZ")
        return False
    
    def _stray_word_cells(self):
        """Cells of straight runs spelling any bank word (either direction) outside its recorded placement."""
        recorded = self.target_words + self.decoy_words
        placed = {entry["word"] for entry in recorded}
        bank = {w for words in TARGET_WORD_BANK.values() for w in words} | set(DECOY_WORD_BANK) | placed

        def is_recorded(run, text):
            """run is a placed word or a sub-run of one; a reversed sub-run only passes if that word isn't placed elsewhere"""
            for entry in recorded:
                for i in range(len(entry["cells"]) - len(run) + 1):
                    if entry["cells"][i:i + len(run)] == run:
                        word = text if text in bank else text[::-1]
                        return word in entry["word"] or word not in placed
            return False
        stray = set()
        lines = [[(r, c) for c in range(GRID_SIZE)] for r in range(GRID_SIZE)]
        lines += [[(r, c) for r in range(GRID_SIZE)] for c in range(GRID_SIZE)]
        for line in lines:
            for start in range(GRID_SIZE):
                for size in range(2, GRID_SIZE - start + 1):
                    run = line[start:start + size]
                    text = "".join(self.ai_ships[r][c] for r, c in run)
                    if (text in bank or text[::-1] in bank) and not is_recorded(run, text):
                        stray.update(run)
        return stray
    
    def _place_word_anywhere(self, word):
        """Write word into a random free straight run of ai_ships. Returns cells or None."""
        size = len(word)
        positions = [(r, c, o)
                     for o in ("horizontal", "vertical")
                     for r in range(GRID_SIZE)
                     for c in range(GRID_SIZE)
                     if self._can_place_ship(self.ai_ships, r, c, size, o)]
        if not positions:
            return None
        row, col, orientation = random.choice(positions)
        cells = [(row, col + i) if orientation == "horizontal" else (row + i, col) for i in range(size)]
        for (r, c), letter in zip(cells, word):
            self.ai_ships[r][c] = letter
        return cells
    
    def _place_ai_ships(self):
        """Place all AI ships using backtracking to guarantee success when a valid layout exists."""
        self.ai_ships = [["~" for _ in range(GRID_SIZE)] for _ in range(GRID_SIZE)]
        ship_list = list(SHIPS.items())
        
        if not self._backtrack_place_ships(ship_list, 0):
            # Only fails if GRID_SIZE and SHIPS configuration is unsatisfiable
            raise RuntimeError(
                f"Cannot place fleet on {GRID_SIZE}x{GRID_SIZE} board. "
                f"Configuration unsatisfiable for ships: {SHIPS}"
            )
    
    def _backtrack_place_ships(self, ship_list, index, letters=False):
        """Recursively place ships using backtracking. Returns True if successful.
        
        With letters=True each ship name is a word whose letters are written into
        the grid and recorded in target_words instead of the "S" marker.
        """
        if index >= len(ship_list):
            # All ships placed successfully
            return True
        
        ship_name, ship_size = ship_list[index]
        
        # Generate all valid positions for this ship (words additionally keep a one-cell gap)
        positions = []
        for orientation in ["horizontal", "vertical"]:
            if orientation == "horizontal":
                for row in range(GRID_SIZE):
                    for col in range(GRID_SIZE - ship_size + 1):
                        if self._can_place_ship(self.ai_ships, row, col, ship_size, orientation, isolated=letters):
                            positions.append((row, col, orientation))
            else:  # vertical
                for row in range(GRID_SIZE - ship_size + 1):
                    for col in range(GRID_SIZE):
                        if self._can_place_ship(self.ai_ships, row, col, ship_size, orientation, isolated=letters):
                            positions.append((row, col, orientation))
        
        # Shuffle positions for randomness
        random.shuffle(positions)
        
        # Try each valid position
        for row, col, orientation in positions:
            # Place the ship
            cells = []
            if orientation == "horizontal":
                for i in range(ship_size):
                    self.ai_ships[row][col + i] = ship_name[i] if letters else "S"
                    cells.append((row, col + i))
            else:
                for i in range(ship_size):
                    self.ai_ships[row + i][col] = ship_name[i] if letters else "S"
                    cells.append((row + i, col))
            if letters:
                self.target_words.append({"word": ship_name, "cells": cells, "solved": False})
            
            # Recurse to place remaining ships
            if self._backtrack_place_ships(ship_list, index + 1, letters):
                return True
            
            # Backtrack: remove this ship and try next position
            if letters:
                self.target_words.pop()
            for r, c in cells:
                self.ai_ships[r][c] = "~"
        
        # No valid placement found for this ship
        return False
    
    def _can_place_ship(self, grid, row, col, size, orientation, isolated=False):
        """Check if ship can be placed at given position; isolated=True also requires no
        occupied cell in any of the 8 neighbours of every cell (a one-cell gap)"""
        if orientation == "horizontal":
            if col + size > GRID_SIZE:
                return False
            cells = [(row, col + i) for i in range(size)]
        else:
            if row + size > GRID_SIZE:
                return False
            cells = [(row + i, col) for i in range(size)]
        if isolated:
            return all(self._isolated(grid, r, c) for r, c in cells)
        return all(grid[r][c] == "~" for r, c in cells)
    
    def place_ship(self, row, col):
        """Place current ship at given position"""
        if self.game_phase != "placement":
            return "Not in placement phase!"
        
        ship_name = self.ship_names[self.current_ship_index]
        ship_size = SHIPS[ship_name]
        
        if not self._can_place_ship(self.player_ships, row, col, ship_size, self.ship_orientation):
            return f"Cannot place {ship_name} there! Try another position."
        
        # Place the ship
        if self.ship_orientation == "horizontal":
            for i in range(ship_size):
                self.player_ships[row][col + i] = "S"
                self.player_grid[row][col + i] = "S"
        else:
            for i in range(ship_size):
                self.player_ships[row + i][col] = "S"
                self.player_grid[row + i][col] = "S"
        
        self.current_ship_index += 1
        
        if self.current_ship_index >= len(self.ship_names):
            self.game_phase = "playing"
            self.message = "All ships placed! Your turn - click on AI grid to fire!"
        else:
            next_ship = self.ship_names[self.current_ship_index]
            self.message = f"Place your {next_ship} ({SHIPS[next_ship]} cells)"
        
        return self.message
    
    def toggle_orientation(self):
        """Toggle ship orientation between horizontal and vertical"""
        if self.game_phase == "placement":
            self.ship_orientation = "vertical" if self.ship_orientation == "horizontal" else "horizontal"
            ship_name = self.ship_names[self.current_ship_index]
            return f"Orientation: {self.ship_orientation}. Place {ship_name} ({SHIPS[ship_name]} cells)"
        return self.message
    
    def player_attack(self, row, col):
        """Player attacks AI grid"""
        if self.game_phase != "playing":
            return "Game not started or already ended!"
        
        if self.turn != "player":
            return "Wait for AI turn!"
        
        if self.ai_grid[row][col] != "~":
            return "Already attacked this position!"
        
        # Check hit or miss
        if self.ai_ships[row][col] == "S":
            self.ai_grid[row][col] = "X"  # Hit
            self.player_hits += 1
            result = f"Hit at {format_coordinate(row, col)}!"
            
            if self.player_hits >= self.total_ship_cells:
                self.game_phase = "ended"
                return "🎉 You Win! All AI ships destroyed!"
        else:
            self.ai_grid[row][col] = "O"  # Miss
            result = f"Miss at {format_coordinate(row, col)}"
        
        # AI turn
        self.turn = "ai"
        ai_result = self._ai_attack()
        self.turn = "player"
        
        return f"{result}\n{ai_result}"
    
    def _auto_place_player_ships(self):
        """Place the player's fleet to resist the AI's hunt: ships never touch (not even
        diagonally), so a hit never leads the adjacent-cell search onto another ship, and
        placements hugging the board edge are preferred so fewer neighbours are open water
        the AI can probe."""
        for _ in range(100):
            grid = [["~" for _ in range(GRID_SIZE)] for _ in range(GRID_SIZE)]
            if self._place_spread_fleet(grid):
                self.player_ships = grid
                self.player_grid = copy.deepcopy(grid)
                return
        raise RuntimeError("Could not auto-place the player's fleet.")
    
    def _place_spread_fleet(self, grid):
        """Greedy placement, largest ship first; False if a ship has no isolated spot left."""
        for size in sorted(SHIPS.values(), reverse=True):
            options = []
            for orientation in ("horizontal", "vertical"):
                for row in range(GRID_SIZE):
                    for col in range(GRID_SIZE):
                        cells = ([(row, col + i) for i in range(size)] if orientation == "horizontal"
                                 else [(row + i, col) for i in range(size)])
                        if all(self._isolated(grid, r, c) for r, c in cells):
                            edge = sum(r in (0, GRID_SIZE - 1) or c in (0, GRID_SIZE - 1) for r, c in cells)
                            options.append((edge, random.random(), cells))
            if not options:
                return False
            options.sort(reverse=True)
            # Pick among the best-scoring few so fleets differ game to game
            _, _, cells = random.choice(options[:4])
            for r, c in cells:
                grid[r][c] = "S"
        return True
    
    @staticmethod
    def _isolated(grid, row, col):
        """Cell is on the board, empty, and has no ship in any of its 8 neighbours"""
        if not (0 <= row < GRID_SIZE and 0 <= col < GRID_SIZE):
            return False
        for dr in (-1, 0, 1):
            for dc in (-1, 0, 1):
                nr, nc = row + dr, col + dc
                if 0 <= nr < GRID_SIZE and 0 <= nc < GRID_SIZE and grid[nr][nc] != "~":
                    return False
        return True
    
    def _solved_cells(self):
        return {cell for w in self.target_words if w["solved"] for cell in w["cells"]}
    
    def _target_cells(self):
        return {cell for w in self.target_words for cell in w["cells"]}
    
    def select_cell(self, row, col):
        """Word mode: toggle a letter in the selection and check for word matches"""
        if self.game_phase != "playing":
            return self.message
        
        cell = (row, col)
        if cell in self._solved_cells():
            return f"{format_coordinate(row, col)} is already part of a solved word."
        
        if cell in self.selected_cells:
            self.selected_cells.remove(cell)
        else:
            self.selected_cells.append(cell)
        
        self._word_turn(row, col)
        if self.game_phase == "ended":
            return self.message
        ai_result = self._ai_attack()
        if self.game_phase == "ended":
            self.message = ai_result
        else:
            self.message = f"{self.message}\n{ai_result}"
        return self.message
    
    def _word_turn(self, row, col):
        """Resolve the player's selection against targets and decoys, setting self.message"""
        total = len(self.target_words)
        
        for target in self.target_words:
            if not target["solved"] and self._spells(target["cells"]):
                target["solved"] = True
                self.solved_count += 1
                self.selected_cells = []
                if self.solved_count >= total:
                    self.game_phase = "ended"
                    self.message = f"🎉 You Win! All {total} words found — every task a job for Devin!"
                else:
                    self.message = f"✅ {target['word']} solved! {self.solved_count}/{total} words found."
                return
        
        for decoy in self.decoy_words:
            if self._spells(decoy["cells"]):
                self.selected_cells = []
                gr.Warning(f"🚫 {decoy['word']}: {decoy['reason']}")
                self.message = (f"🚫 {decoy['word']} is a task better owned by humans — not a target. "
                                f"Solved {self.solved_count}/{total}")
                return
        
        if not self.selected_cells:
            self.message = f"Selection cleared. Solved {self.solved_count}/{total}"
        else:
            spelled = "".join(self.ai_ships[r][c] for r, c in self.selected_cells)
            self.message = (f"Selected: {spelled} ({len(self.selected_cells)} letters). "
                            f"Words run straight across or down. Solved {self.solved_count}/{total}")
        return
    
    def _spells(self, cells):
        """True if the ordered selection traces cells forwards or backwards"""
        return self.selected_cells == cells or self.selected_cells == cells[::-1]
    
    def clear_selection(self):
        self.selected_cells = []
        if self.game_phase == "playing":
            self.message = f"Selection cleared. Solved {self.solved_count}/{len(self.target_words)}"
        return self.message
    
    def _ai_attack(self):
        """AI makes an attack"""
        if self.ai_target_mode and self.ai_target_queue:
            # Smart targeting mode - attack adjacent cells after a hit
            row, col = self.ai_target_queue.pop(0)
        else:
            # Random attack
            available = [(r, c) for r in range(GRID_SIZE) for c in range(GRID_SIZE) 
                        if self.player_grid[r][c] == "~" or self.player_grid[r][c] == "S"]
            if not available:
                return "AI has no moves!"
            row, col = random.choice(available)
        
        # Check hit or miss
        if self.player_ships[row][col] == "S":
            self.player_grid[row][col] = "X"  # Hit
            self.ai_hits += 1
            
            # Enter smart targeting mode
            self.ai_target_mode = True
            self.ai_last_hit = (row, col)
            
            # Add adjacent cells to target queue
            for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                nr, nc = row + dr, col + dc
                if (0 <= nr < GRID_SIZE and 0 <= nc < GRID_SIZE and 
                    self.player_grid[nr][nc] in ["~", "S"] and 
                    (nr, nc) not in self.ai_target_queue):
                    self.ai_target_queue.append((nr, nc))
            
            result = f"AI Hit your ship at {format_coordinate(row, col)}!"
            
            if self.ai_hits >= self.total_ship_cells:
                self.game_phase = "ended"
                return "💀 AI Wins! All your ships destroyed!"
        else:
            self.player_grid[row][col] = "O"  # Miss
            result = f"AI Missed at {format_coordinate(row, col)}"
            
            # If we missed in target mode, might need to adjust
            if not self.ai_target_queue:
                self.ai_target_mode = False
        
        return result

def format_coordinate(row, col):
    """Convert (row, col) to standard Battleship notation (e.g., 'B4')"""
    return f"{chr(ord('A') + col)}{row + 1}"

def cell_symbol(cell, show_ships, letters=False):
    """Symbol shown on a board button for a grid cell; letters=True renders a word-grid letter"""
    if letters and len(cell) == 1 and cell.isalpha():
        return cell.upper()
    if cell == "X":
        return "💥"
    if cell == "O":
        return "⚪"
    if cell == "S" and show_ships:
        return "🚢"
    return "🌊"

def word_cell_update(game, r, c):
    """Button update for a word-mode letter cell, styled by solved/selected state"""
    classes = ["word-cell"]
    variant = "secondary"
    if (r, c) in game._target_cells():
        classes.append("target-cell")
    if (r, c) in game._solved_cells():
        classes.append("solved-cell")
    elif (r, c) in game.selected_cells:
        classes.append("selected-cell")
        variant = "primary"
    return gr.update(value=cell_symbol(game.ai_ships[r][c], show_ships=True, letters=True),
                     variant=variant, elem_classes=classes)

def board_updates(game):
    """Button updates for both boards, flattened player-first then AI"""
    updates = [gr.update(value=cell_symbol(game.player_grid[r][c], show_ships=True))
               for r in range(GRID_SIZE) for c in range(GRID_SIZE)]
    if game.mode == "word":
        updates += [word_cell_update(game, r, c) for r in range(GRID_SIZE) for c in range(GRID_SIZE)]
    else:
        updates += [gr.update(value=cell_symbol(game.ai_grid[r][c], show_ships=False))
                    for r in range(GRID_SIZE) for c in range(GRID_SIZE)]
    return updates

def handle_grid_click(game, row, col, is_ai_grid):
    """Handle grid clicks for placement and attacking; returns [game, message, *board updates]"""
    if game.mode == "word":
        msg = game.select_cell(row, col) if is_ai_grid else game.message
    elif game.game_phase == "placement":
        if is_ai_grid:
            msg = "Place your ships on your own grid (left)!"
        else:
            msg = game.place_ship(row, col)
    elif game.game_phase == "playing":
        if is_ai_grid:
            msg = game.player_attack(row, col)
        else:
            msg = "Fire at the AI grid (right)!"
    else:
        msg = game.message
    
    return [game, msg] + board_updates(game)

def handle_cell_click(evt: gr.SelectData):
    """Handle click events on the grids"""
    # Determine which grid was clicked based on index
    # Since we have 2 grids side by side, we need coordinates
    # For now, this is handled by separate buttons for each cell
    pass

def orientation_toggle(game):
    """Toggle ship orientation"""
    return [game, game.toggle_orientation()]

def reset_game_handler(game):
    """Reset the game"""
    game.reset_game()
    return [game, game.message] + board_updates(game)

def mode_view_updates(game):
    """Visibility / label / theme updates for the current mode"""
    word = game.mode == "word"
    heading = ("### Word Puzzle Grid — click letters to spell words" if word
               else "### AI Grid (Click to attack)")
    player_heading = "### Your Fleet (auto-placed — the AI fires back)" if word else "### Your Grid"
    return [
        gr.update(value=player_heading),                               # player grid heading
        gr.update(visible=not word),                                   # orientation toggle
        gr.update(visible=word),                                       # clear selection
        gr.update(value=heading),                                      # AI grid heading
        gr.update(value="Switch to Classic Mode" if word else "Switch to Word Puzzle Mode"),
        gr.update(elem_classes=["word-mode"] if word else []),         # root container
    ]

def toggle_mode_handler(game):
    """Switch classic <-> word mode and start a fresh game"""
    game.toggle_mode()
    board = board_updates(game)
    if game.mode == "classic":
        # Strip word-mode button styling before re-rendering the classic boards
        for upd in board[GRID_SIZE * GRID_SIZE:]:
            upd["variant"] = "secondary"
            upd["elem_classes"] = []
    return [game, game.message] + board + mode_view_updates(game)

def clear_selection_handler(game):
    return [game, game.clear_selection()] + board_updates(game)

ARCADE_CSS = """
/* Import retro gaming font */
@import url('https://fonts.googleapis.com/css2?family=Press+Start+2P&display=swap');

/* Arcade video game styling */
body {
    background: linear-gradient(135deg, #0a0e27 0%, #1a1a2e 100%) !important;
    font-family: 'Press Start 2P', cursive !important;
}

.gradio-container {
    background: radial-gradient(circle at center, #16213e 0%, #0f1419 100%) !important;
    border: 3px solid #00ff00 !important;
    box-shadow: 0 0 30px rgba(0, 255, 0, 0.5), inset 0 0 50px rgba(0, 255, 0, 0.1) !important;
}

/* Neon glow buttons */
button {
    background: linear-gradient(145deg, #1a1a2e, #16213e) !important;
    border: 2px solid #00ff00 !important;
    color: #00ff00 !important;
    text-shadow: 0 0 10px #00ff00 !important;
    box-shadow: 0 0 10px rgba(0, 255, 0, 0.5) !important;
    font-family: 'Press Start 2P', cursive !important;
    font-size: 10px !important;
    transition: all 0.3s ease !important;
}

button:hover {
    background: linear-gradient(145deg, #00ff00, #00cc00) !important;
    color: #000 !important;
    box-shadow: 0 0 20px rgba(0, 255, 0, 1) !important;
    transform: scale(1.05) !important;
}

/* Game grid cells with neon borders */
.grid-cell {
    border: 1px solid #00ff00 !important;
    box-shadow: inset 0 0 5px rgba(0, 255, 0, 0.3) !important;
    background: #0f1419 !important;
    transition: all 0.2s ease !important;
}

.grid-cell:hover {
    box-shadow: 0 0 15px rgba(0, 255, 0, 0.8) !important;
    transform: scale(1.1) !important;
}

/* Message box - arcade terminal style */
textarea {
    background: #000 !important;
    border: 3px solid #00ff00 !important;
    color: #00ff00 !important;
    font-family: 'Press Start 2P', cursive !important;
    text-shadow: 0 0 10px #00ff00 !important;
    padding: 20px !important;
    box-shadow: 0 0 20px rgba(0, 255, 0, 0.5) !important;
    font-size: 12px !important;
}

/* Centered title and subtitle */
#game-title, #game-subtitle {
    text-align: center !important;
}
#game-title h1, #game-subtitle h3 {
    text-align: center !important;
    display: block !important;
}

/* Headings with neon green glow */
h1, h2, h3, label {
    color: #00ff00 !important;
    text-shadow: 0 0 20px #00ff00, 0 0 40px #00ff00 !important;
    font-family: 'Press Start 2P', cursive !important;
    animation: neon-flicker 2s infinite alternate !important;
}

/* Make rule/instruction text white and visible */
.gr-prose, .gr-prose p, .gr-prose li, .gr-markdown, 
.gr-markdown p, .gr-markdown li, .gr-markdown ol, .gr-markdown ul,
p, li, span, div {
    color: #ffffff !important;
    text-shadow: 0 0 5px rgba(255, 255, 255, 0.3) !important;
}

/* Specific targeting for instruction text */
.gradio-container p, 
.gradio-container li,
.gradio-container span:not(button span) {
    color: #ffffff !important;
    font-family: 'Press Start 2P', cursive !important;
    font-size: 10px !important;
    line-height: 1.8 !important;
    text-shadow: 0 0 5px rgba(255, 255, 255, 0.3) !important;
}

/* Legend and symbols - make them bright */
.gr-prose strong, strong, b {
    color: #00ff00 !important;
    text-shadow: 0 0 10px #00ff00 !important;
}

/* Target words in word mode - bold and highly visible */
button b, button strong {
    color: #ffff00 !important;
    text-shadow: 0 0 15px #ffff00, 0 0 25px #ffff00 !important;
    font-weight: 900 !important;
    font-size: 14px !important;
}

@keyframes neon-flicker {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.8; }
}

/* Victory overlay */
#victory-overlay {
    position: fixed;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    background: rgba(0, 0, 0, 0.95);
    display: none;
    justify-content: center;
    align-items: center;
    z-index: 9999;
    flex-direction: column;
}

#victory-message {
    font-family: 'Press Start 2P', cursive;
    font-size: 64px;
    color: #00ff00;
    text-shadow: 
        0 0 10px #00ff00,
        0 0 20px #00ff00,
        0 0 30px #00ff00,
        0 0 40px #00ff00,
        0 0 70px #00ff00,
        0 0 80px #00ff00,
        0 0 100px #00ff00;
    animation: neon-glow 1.5s ease-in-out infinite alternate;
    text-align: center;
    padding: 40px;
    line-height: 1.5;
}

@keyframes neon-glow {
    from {
        text-shadow: 
            0 0 10px #00ff00,
            0 0 20px #00ff00,
            0 0 30px #00ff00,
            0 0 40px #00ff00,
            0 0 70px #00ff00;
    }
    to {
        text-shadow: 
            0 0 20px #00ff00,
            0 0 30px #00ff00,
            0 0 40px #00ff00,
            0 0 50px #00ff00,
            0 0 80px #00ff00,
            0 0 90px #00ff00,
            0 0 120px #00ff00;
    }
}

/* Firework particles */
.firework {
    position: fixed;
    width: 6px;
    height: 6px;
    border-radius: 50%;
    pointer-events: none;
    z-index: 10000;
}

@keyframes explode {
    0% {
        transform: translate(0, 0);
        opacity: 1;
    }
    100% {
        transform: translate(var(--tx), var(--ty));
        opacity: 0;
    }
}
"""




GAME_JS = """
console.log('🎮 Game effects initializing...');

// Sound effects using Web Audio API
let audioContext;
let isAudioInitialized = false;

function initAudio() {
    if (!isAudioInitialized && !audioContext) {
        try {
            audioContext = new (window.AudioContext || window.webkitAudioContext)();
            isAudioInitialized = true;
            console.log('✅ Audio initialized');
        } catch (e) {
            console.error('Audio init failed:', e);
        }
    }
}

// Initialize audio on ANY user interaction
document.addEventListener('click', initAudio);
document.addEventListener('keydown', initAudio);

function playHitSound() {
    initAudio();
    if (!audioContext) return;
    
    try {
        const oscillator = audioContext.createOscillator();
        const gainNode = audioContext.createGain();
        
        oscillator.connect(gainNode);
        gainNode.connect(audioContext.destination);
        
        oscillator.type = 'sawtooth';
        oscillator.frequency.setValueAtTime(800, audioContext.currentTime);
        oscillator.frequency.exponentialRampToValueAtTime(50, audioContext.currentTime + 0.3);
        
        gainNode.gain.setValueAtTime(0.3, audioContext.currentTime);
        gainNode.gain.exponentialRampToValueAtTime(0.01, audioContext.currentTime + 0.3);
        
        oscillator.start(audioContext.currentTime);
        oscillator.stop(audioContext.currentTime + 0.3);
        console.log('💥 Hit sound played');
    } catch (e) {
        console.error('Hit sound failed:', e);
    }
}

function playMissSound() {
    initAudio();
    if (!audioContext) return;
    
    try {
        const oscillator = audioContext.createOscillator();
        const gainNode = audioContext.createGain();
        
        oscillator.connect(gainNode);
        gainNode.connect(audioContext.destination);
        
        oscillator.type = 'sine';
        oscillator.frequency.setValueAtTime(150, audioContext.currentTime);
        oscillator.frequency.exponentialRampToValueAtTime(80, audioContext.currentTime + 0.15);
        
        gainNode.gain.setValueAtTime(0.2, audioContext.currentTime);
        gainNode.gain.exponentialRampToValueAtTime(0.01, audioContext.currentTime + 0.15);
        
        oscillator.start(audioContext.currentTime);
        oscillator.stop(audioContext.currentTime + 0.15);
        console.log('💧 Miss sound played');
    } catch (e) {
        console.error('Miss sound failed:', e);
    }
}

function playVictorySound() {
    initAudio();
    if (!audioContext) return;
    
    try {
        const notes = [262, 330, 392, 523];
        notes.forEach((freq, i) => {
            setTimeout(() => {
                const osc = audioContext.createOscillator();
                const gain = audioContext.createGain();
                osc.connect(gain);
                gain.connect(audioContext.destination);
                osc.type = 'square';
                osc.frequency.value = freq;
                gain.gain.setValueAtTime(0.2, audioContext.currentTime);
                gain.gain.exponentialRampToValueAtTime(0.01, audioContext.currentTime + 0.5);
                osc.start(audioContext.currentTime);
                osc.stop(audioContext.currentTime + 0.5);
            }, i * 150);
        });
        console.log('🎺 Victory sound played');
    } catch (e) {
        console.error('Victory sound failed:', e);
    }
}

function playWordSolvedSound() {
    initAudio();
    if (!audioContext) return;
    
    try {
        // Rising three-note arpeggio for a correctly spelled target word
        const notes = [523, 659, 784];
        notes.forEach((freq, i) => {
            const osc = audioContext.createOscillator();
            const gain = audioContext.createGain();
            osc.connect(gain);
            gain.connect(audioContext.destination);
            osc.type = 'triangle';
            osc.frequency.value = freq;
            const start = audioContext.currentTime + i * 0.12;
            gain.gain.setValueAtTime(0.25, start);
            gain.gain.exponentialRampToValueAtTime(0.01, start + 0.35);
            osc.start(start);
            osc.stop(start + 0.35);
        });
        console.log('✅ Word solved sound played');
    } catch (e) {
        console.error('Word solved sound failed:', e);
    }
}

function createFirework(x, y) {
    console.log('🎆 Creating firework at', x, y);
    const colors = ['#ff0000', '#00ff00', '#0000ff', '#ffff00', '#ff00ff', '#00ffff'];
    const particleCount = 80;
    
    for (let i = 0; i < particleCount; i++) {
        const particle = document.createElement('div');
        particle.className = 'firework';
        particle.style.left = x + 'px';
        particle.style.top = y + 'px';
        particle.style.backgroundColor = colors[Math.floor(Math.random() * colors.length)];
        
        const angle = (Math.PI * 2 * i) / particleCount;
        const velocity = 100 + Math.random() * 150;
        const tx = Math.cos(angle) * velocity;
        const ty = Math.sin(angle) * velocity;
        
        particle.style.setProperty('--tx', tx + 'px');
        particle.style.setProperty('--ty', ty + 'px');
        particle.style.animation = 'explode 1.2s ease-out forwards';
        
        document.body.appendChild(particle);
        
        setTimeout(() => {
            if (particle.parentNode) {
                particle.parentNode.removeChild(particle);
            }
        }, 1200);
    }
}

let victoryTriggered = false;

// Claim the current win exactly once: play the fanfare and schedule the overlay.
// Returns false if this win was already celebrated.
function celebrateVictory(soundDelay) {
    if (victoryTriggered) return false;
    victoryTriggered = true;
    setTimeout(playVictorySound, soundDelay);
    setTimeout(showVictoryScreen, 300);
    return true;
}

function showVictoryScreen() {
    console.log('🏆 VICTORY! Showing celebration');
    
    let overlay = document.getElementById('victory-overlay');
    if (!overlay) {
        overlay = document.createElement('div');
        overlay.id = 'victory-overlay';
        overlay.innerHTML = '<div id="victory-message">HUMANS RULE<br/>THE WORLD!</div>';
        document.body.appendChild(overlay);
    }
    
    overlay.style.display = 'flex';
    
    // Launch fireworks in waves
    let fireworkCount = 0;
    const launchWave = () => {
        for (let i = 0; i < 5; i++) {
            setTimeout(() => {
                const x = 200 + Math.random() * (window.innerWidth - 400);
                const y = 100 + Math.random() * (window.innerHeight - 200);
                createFirework(x, y);
            }, i * 100);
        }
    };
    
    // Launch 8 waves of fireworks
    for (let wave = 0; wave < 8; wave++) {
        setTimeout(launchWave, wave * 600);
    }
    
    // Hide after 10 seconds
    setTimeout(() => {
        overlay.style.display = 'none';
    }, 10000);
}

// Watch for game messages more aggressively
let lastMessageText = '';

function checkForGameEvents() {
    // Find all textareas (message boxes)
    const textareas = document.querySelectorAll('textarea');
    textareas.forEach(textarea => {
        const text = textarea.value || '';
        
        if (text !== lastMessageText) {
            console.log('📝 Message changed:', text);
            lastMessageText = text;
            if (!text.includes('You Win!') && !text.includes('🎉')) {
                victoryTriggered = false;  // new game started; allow the next win to celebrate
            }
            
            // 'words found' also appears in the word-mode win message, so the last word chimes too
            const wordSolved = text.includes('solved!') || text.includes('words found');
            if (wordSolved) {
                playWordSolvedSound();
            }
            if (text.includes('You Win!') || text.includes('🎉')) {
                celebrateVictory(wordSolved ? 450 : 0);
            } else if (!wordSolved && text.includes('Hit at')) {
                playHitSound();
            } else if (!wordSolved && text.includes('Miss at')) {
                playMissSound();
            }
        }
    });
    
    // Also check all text content (fallback). Skip once the win has already
    // been celebrated so the sound doesn't repeat while 'You Win!' stays on screen.
    if (!victoryTriggered) {
        const allText = document.body.textContent || '';
        if (allText.includes('You Win!')) {
            celebrateVictory(0);
        }
    }
}

// Poll for changes every 200ms
setInterval(checkForGameEvents, 200);

// Also use MutationObserver as backup, but coalesce bursts of mutations
// (e.g. firework particles being added/removed) into a single check.
let scanScheduled = false;
const observer = new MutationObserver(() => {
    if (scanScheduled) return;
    scanScheduled = true;
    requestAnimationFrame(() => {
        scanScheduled = false;
        checkForGameEvents();
    });
});

observer.observe(document.body, {
    childList: true,
    subtree: true,
    characterData: true,
    attributes: false
});

console.log('✅ Game effects ready!');
"""




WORD_MODE_CSS = """
/* Grid headers: row labels are a fixed 40px column, column letters flex exactly like the buttons */
.row-label {
    flex: 0 0 40px !important;
    min-width: 40px !important;
}
.col-header {
    flex: 1 1 0 !important;
    min-width: 40px !important;
}
.word-mode, .word-mode .block, .word-mode .form, .word-mode .gap, .word-mode .panel {
    background: #0d0d0f !important;
    color: #e6e6e6 !important;
    border-color: #2a2a30 !important;
}
.word-mode .prose, .word-mode .prose *, .word-mode .html-container, .word-mode .html-container *,
.word-mode label, .word-mode label span {
    color: #e6e6e6 !important;
}
.word-mode input, .word-mode textarea {
    background: #1a1a1e !important;
    color: #e6e6e6 !important;
    border-color: #2a2a30 !important;
}
.word-mode button {
    background: #1a1a1e !important;
    color: #e6e6e6 !important;
    border: 1px solid #2a2a30 !important;
    box-shadow: none !important;
}
.word-mode button:hover {
    border-color: #6c6cff !important;
}
.word-mode button.word-cell {
    font-weight: 400;
    letter-spacing: 0.05em;
}
.word-mode button.target-cell {
    font-weight: 900;
    position: relative;
    overflow: visible !important;
}
/* Green dot on the bottom border line marks letters that belong to a target word */
.word-mode button.target-cell::after {
    content: "";
    position: absolute;
    bottom: -2px;
    left: 50%;
    transform: translateX(-50%);
    width: 3px;
    height: 3px;
    border-radius: 50%;
    background: #3ddc84;
    box-shadow: 0 0 3px #3ddc84, 0 0 6px rgba(61, 220, 132, 0.8);
    pointer-events: none;
    z-index: 1;
}
.word-mode button.solved-cell::after {
    display: none;
}
.word-mode button.selected-cell {
    border: 2px solid #6c6cff !important;
    color: #ffffff !important;
    background: #23233a !important;
}
.word-mode button.solved-cell {
    border: 1px solid #3ddc84 !important;
    color: #3ddc84 !important;
    background: #10231a !important;
    box-shadow: 0 0 8px rgba(61, 220, 132, 0.6) !important;
}
"""

def create_interactive_grid(grid, is_ai_grid=False):
    """Create interactive grid with buttons"""
    buttons = []
    for r in range(GRID_SIZE):
        row_buttons = []
        for c in range(GRID_SIZE):
            cell = grid[r][c]
            if cell == "X":
                symbol = "💥"
            elif cell == "O":
                symbol = "⚪"
            elif cell == "S" and not is_ai_grid:
                symbol = "🚢"
            else:
                symbol = "🌊"
            
            row_buttons.append(gr.Button(symbol, size="sm", scale=1))
        buttons.append(row_buttons)
    return buttons

# Create Gradio interface
with gr.Blocks(title="Battleship Game") as app:
    # Callable: a fresh, independently randomized game is created per browser session
    game_state = gr.State(BattleshipGame)
    initial_game = BattleshipGame()  # only for the initial (static) board render
    with gr.Column(elem_id="root-container") as root_container:
        gr.Markdown("# 🚢 Battleship Game", elem_id="game-title")
        gr.Markdown("### Human vs AI", elem_id="game-subtitle")
    
        with gr.Row():
            message_box = gr.Textbox(label="Game Status", value=initial_game.message, interactive=False)
    
        with gr.Row():
            toggle_btn = gr.Button("Toggle Orientation (Horizontal/Vertical)")
            reset_btn = gr.Button("Reset Game")
            mode_btn = gr.Button("Switch to Word Puzzle Mode")
            clear_btn = gr.Button("Clear Selection", visible=False)
    
        with gr.Row():
            with gr.Column():
                player_heading = gr.Markdown("### Your Grid")
                with gr.Group():
                    # Column headers (A-J)
                    with gr.Row():
                        gr.HTML("<div style='text-align:center'>&nbsp;</div>", elem_classes=["row-label"])  # Row label column
                        for c in range(GRID_SIZE):
                            gr.HTML(f"<div style='text-align:center'><b>{chr(ord('A') + c)}</b></div>",
                                    elem_classes=["col-header"])
                
                    # Grid rows with row labels (1-10)
                    player_buttons = []
                    for r in range(GRID_SIZE):
                        with gr.Row():
                            gr.HTML(f"<div style='text-align:center'><b>{r + 1}</b></div>", elem_classes=["row-label"])  # Row label
                            row_btns = []
                            for c in range(GRID_SIZE):
                                btn = gr.Button(cell_symbol(initial_game.player_grid[r][c], show_ships=True),
                                                size="sm", scale=1, min_width=40)
                                row_btns.append(btn)
                            player_buttons.append(row_btns)
        
            with gr.Column():
                ai_heading = gr.Markdown("### AI Grid (Click to attack)")
                with gr.Group():
                    # Column headers (A-J)
                    with gr.Row():
                        gr.HTML("<div style='text-align:center'>&nbsp;</div>", elem_classes=["row-label"])  # Row label column
                        for c in range(GRID_SIZE):
                            gr.HTML(f"<div style='text-align:center'><b>{chr(ord('A') + c)}</b></div>",
                                    elem_classes=["col-header"])
                
                    # Grid rows with row labels (1-10)
                    ai_buttons = []
                    for r in range(GRID_SIZE):
                        with gr.Row():
                            gr.HTML(f"<div style='text-align:center'><b>{r + 1}</b></div>", elem_classes=["row-label"])  # Row label
                            row_btns = []
                            for c in range(GRID_SIZE):
                                btn = gr.Button(cell_symbol(initial_game.ai_grid[r][c], show_ships=False),
                                                size="sm", scale=1, min_width=40)
                                row_btns.append(btn)
                            ai_buttons.append(row_btns)
    
        gr.Markdown("""
        ### How to Play:
        1. **Placement Phase**: Click on your grid (left) to place ships. Toggle orientation as needed.
        2. **Battle Phase**: Click on AI grid (right) to attack. AI attacks automatically after your turn.
        3. **Ships**: Carrier (5), Battleship (4), Cruiser (3), Submarine (3), Destroyer (2)
    
        **Legend**: 🌊 Water | 🚢 Ship | 💥 Hit | ⚪ Miss
    
        ### Word Puzzle Mode:
        Press **Switch to Word Puzzle Mode** for a 10x10 grid of letters on the right. Five hidden words
        (5, 4, 3, 3 and 2 letters, running across or down, never touching each other) are the AI's "ships" — each is a coding
        task Devin is great at (e.g. DEBUG, LINT, FIX, PR). Click letters to select them (click again
        to deselect, or use **Clear Selection**); spell a full word to sink it. Letters that belong to a
        hidden target word are shown in **bold** with a green dot on their bottom edge as a hint; a
        chime plays every time you spell a target word. Cells of solved words
        turn green. The grid also hides decoy words — SWE tasks better owned by humans (e.g. SCOPE,
        HIRE, ONCALL). Spelling a decoy opens a popup explaining why it isn't a fit for Devin and
        doesn't count toward the win. Your own fleet (left) is placed automatically, spread out and
        hugging the edges so the AI's hunt-after-a-hit tactic finds as little as possible; the AI
        fires one classic shot at it after every letter you click. Find all five targets before it
        sinks your fleet.
    
        **Word Legend**: **bold** letter + green dot = part of a target | green glow = solved word | accent border = selected
        """)
    
        flat_buttons = ([player_buttons[r][c] for r in range(GRID_SIZE) for c in range(GRID_SIZE)] +
                        [ai_buttons[r][c] for r in range(GRID_SIZE) for c in range(GRID_SIZE)])
        board_outputs = [game_state, message_box] + flat_buttons
    
        # Wire up player grid clicks (for placement)
        for r in range(GRID_SIZE):
            for c in range(GRID_SIZE):
                player_buttons[r][c].click(
                    fn=lambda g, r=r, c=c: handle_grid_click(g, r, c, is_ai_grid=False),
                    inputs=[game_state],
                    outputs=board_outputs
                )
    
        # Wire up AI grid clicks (for attacking)
        for r in range(GRID_SIZE):
            for c in range(GRID_SIZE):
                ai_buttons[r][c].click(
                    fn=lambda g, r=r, c=c: handle_grid_click(g, r, c, is_ai_grid=True),
                    inputs=[game_state],
                    outputs=board_outputs
                )
    
        toggle_btn.click(
            fn=orientation_toggle,
            inputs=[game_state],
            outputs=[game_state, message_box]
        )
    
        reset_btn.click(
            fn=reset_game_handler,
            inputs=[game_state],
            outputs=board_outputs
        )
    
        mode_btn.click(
            fn=toggle_mode_handler,
            inputs=[game_state],
            outputs=board_outputs + [player_heading, toggle_btn, clear_btn, ai_heading, mode_btn, root_container]
        )
    
        clear_btn.click(
            fn=clear_selection_handler,
            inputs=[game_state],
            outputs=board_outputs
        )

if __name__ == "__main__":
    # Combine arcade styling with word mode styling
    combined_css = ARCADE_CSS + WORD_MODE_CSS
    app.launch(
        css=combined_css,
        head=f"<script>{GAME_JS}</script>"
    )
