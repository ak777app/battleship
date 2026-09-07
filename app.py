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

class BattleshipGame:
    def __init__(self):
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
        self.message = f"Place your {self.ship_names[0]} ({SHIPS[self.ship_names[0]]} cells)"
        
        # Place AI ships automatically
        self._place_ai_ships()
        
        # AI targeting
        self.ai_last_hit = None
        self.ai_target_mode = False
        self.ai_target_queue = []
    
    def _place_ai_ships(self):
        """Randomly place all AI ships, guaranteed to succeed"""
        max_board_resets = 10
        board_resets = 0
        
        while board_resets < max_board_resets:
            # Clear the board for a fresh attempt
            self.ai_ships = [["~" for _ in range(GRID_SIZE)] for _ in range(GRID_SIZE)]
            all_placed = True
            
            for ship_name, ship_size in SHIPS.items():
                placed = False
                attempts = 0
                
                while not placed and attempts < 100:
                    orientation = random.choice(["horizontal", "vertical"])
                    if orientation == "horizontal":
                        row = random.randint(0, GRID_SIZE - 1)
                        col = random.randint(0, GRID_SIZE - ship_size)
                        if self._can_place_ship(self.ai_ships, row, col, ship_size, orientation):
                            for i in range(ship_size):
                                self.ai_ships[row][col + i] = "S"
                            placed = True
                    else:
                        row = random.randint(0, GRID_SIZE - ship_size)
                        col = random.randint(0, GRID_SIZE - 1)
                        if self._can_place_ship(self.ai_ships, row, col, ship_size, orientation):
                            for i in range(ship_size):
                                self.ai_ships[row + i][col] = "S"
                            placed = True
                    attempts += 1
                
                if not placed:
                    # Failed to place this ship, retry from a fresh board
                    all_placed = False
                    break
            
            if all_placed:
                # Successfully placed all ships
                return
            
            board_resets += 1
        
        # If we get here, something is fundamentally wrong (should never happen)
        raise RuntimeError(f"Failed to place all AI ships after {max_board_resets} board resets. This should never happen.")
    
    def _can_place_ship(self, grid, row, col, size, orientation):
        """Check if ship can be placed at given position"""
        if orientation == "horizontal":
            if col + size > GRID_SIZE:
                return False
            for i in range(size):
                if grid[row][col + i] != "~":
                    return False
        else:
            if row + size > GRID_SIZE:
                return False
            for i in range(size):
                if grid[row + i][col] != "~":
                    return False
        return True
    
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
            result = f"Hit at ({row}, {col})!"
            
            if self.player_hits >= self.total_ship_cells:
                self.game_phase = "ended"
                return "🎉 You Win! All AI ships destroyed!"
        else:
            self.ai_grid[row][col] = "O"  # Miss
            result = f"Miss at ({row}, {col})"
        
        # AI turn
        self.turn = "ai"
        ai_result = self._ai_attack()
        self.turn = "player"
        
        return f"{result}\n{ai_result}"
    
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
            
            result = f"AI Hit your ship at ({row}, {col})!"
            
            if self.ai_hits >= self.total_ship_cells:
                self.game_phase = "ended"
                return "💀 AI Wins! All your ships destroyed!"
        else:
            self.player_grid[row][col] = "O"  # Miss
            result = f"AI Missed at ({row}, {col})"
            
            # If we missed in target mode, might need to adjust
            if not self.ai_target_queue:
                self.ai_target_mode = False
        
        return result

# Global game instance
game = BattleshipGame()

def cell_symbol(cell, show_ships):
    """Symbol shown on a board button for a grid cell"""
    if cell == "X":
        return "💥"
    if cell == "O":
        return "⚪"
    if cell == "S" and show_ships:
        return "🚢"
    return "🌊"

def board_updates():
    """Button updates for both boards, flattened player-first then AI"""
    updates = [gr.update(value=cell_symbol(game.player_grid[r][c], show_ships=True))
               for r in range(GRID_SIZE) for c in range(GRID_SIZE)]
    updates += [gr.update(value=cell_symbol(game.ai_grid[r][c], show_ships=False))
                for r in range(GRID_SIZE) for c in range(GRID_SIZE)]
    return updates

def handle_grid_click(row, col, is_ai_grid):
    """Handle grid clicks for placement and attacking"""
    if game.game_phase == "placement":
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
    
    return [msg] + board_updates()

def handle_cell_click(evt: gr.SelectData):
    """Handle click events on the grids"""
    # Determine which grid was clicked based on index
    # Since we have 2 grids side by side, we need coordinates
    # For now, this is handled by separate buttons for each cell
    pass

def orientation_toggle():
    """Toggle ship orientation"""
    msg = game.toggle_orientation()
    return msg

def reset_game_handler():
    """Reset the game"""
    game.reset_game()
    return [game.message] + board_updates()

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
    gr.Markdown("# 🚢 Battleship Game")
    gr.Markdown("### Human vs AI")
    
    with gr.Row():
        message_box = gr.Textbox(label="Game Status", value=game.message, interactive=False)
    
    with gr.Row():
        toggle_btn = gr.Button("Toggle Orientation (Horizontal/Vertical)")
        reset_btn = gr.Button("Reset Game")
    
    with gr.Row():
        with gr.Column():
            gr.Markdown("### Your Grid")
            with gr.Group():
                player_buttons = []
                for r in range(GRID_SIZE):
                    with gr.Row():
                        row_btns = []
                        for c in range(GRID_SIZE):
                            btn = gr.Button(cell_symbol(game.player_grid[r][c], show_ships=True),
                                            size="sm", scale=1, min_width=40)
                            row_btns.append(btn)
                        player_buttons.append(row_btns)
        
        with gr.Column():
            gr.Markdown("### AI Grid (Click to attack)")
            with gr.Group():
                ai_buttons = []
                for r in range(GRID_SIZE):
                    with gr.Row():
                        row_btns = []
                        for c in range(GRID_SIZE):
                            btn = gr.Button(cell_symbol(game.ai_grid[r][c], show_ships=False),
                                            size="sm", scale=1, min_width=40)
                            row_btns.append(btn)
                        ai_buttons.append(row_btns)
    
    gr.Markdown("""
    ### How to Play:
    1. **Placement Phase**: Click on your grid (left) to place ships. Toggle orientation as needed.
    2. **Battle Phase**: Click on AI grid (right) to attack. AI attacks automatically after your turn.
    3. **Ships**: Carrier (5), Battleship (4), Cruiser (3), Submarine (3), Destroyer (2)
    
    **Legend**: 🌊 Water | 🚢 Ship | 💥 Hit | ⚪ Miss
    """)
    
    flat_buttons = ([player_buttons[r][c] for r in range(GRID_SIZE) for c in range(GRID_SIZE)] +
                    [ai_buttons[r][c] for r in range(GRID_SIZE) for c in range(GRID_SIZE)])
    board_outputs = [message_box] + flat_buttons
    
    # Wire up player grid clicks (for placement)
    for r in range(GRID_SIZE):
        for c in range(GRID_SIZE):
            player_buttons[r][c].click(
                fn=lambda r=r, c=c: handle_grid_click(r, c, is_ai_grid=False),
                outputs=board_outputs
            )
    
    # Wire up AI grid clicks (for attacking)
    for r in range(GRID_SIZE):
        for c in range(GRID_SIZE):
            ai_buttons[r][c].click(
                fn=lambda r=r, c=c: handle_grid_click(r, c, is_ai_grid=True),
                outputs=board_outputs
            )
    
    toggle_btn.click(
        fn=orientation_toggle,
        outputs=[message_box]
    )
    
    reset_btn.click(
        fn=reset_game_handler,
        outputs=board_outputs
    )

if __name__ == "__main__":
    app.launch()
