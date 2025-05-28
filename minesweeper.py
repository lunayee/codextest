# Simple Minesweeper console game in Python
import random

class Minesweeper:
    def __init__(self, rows=9, cols=9, mines=10):
        self.rows = rows
        self.cols = cols
        self.mines = mines
        self.board = [[0 for _ in range(cols)] for _ in range(rows)]
        self.visible = [[False for _ in range(cols)] for _ in range(rows)]
        self.flags = [[False for _ in range(cols)] for _ in range(rows)]
        self.place_mines()
        self.calculate_numbers()
        self.uncovered = 0

    def place_mines(self):
        positions = [(r, c) for r in range(self.rows) for c in range(self.cols)]
        for r, c in random.sample(positions, self.mines):
            self.board[r][c] = 'M'

    def calculate_numbers(self):
        directions = [
            (-1, -1), (-1, 0), (-1, 1),
            (0, -1),          (0, 1),
            (1, -1), (1, 0), (1, 1),
        ]
        for r in range(self.rows):
            for c in range(self.cols):
                if self.board[r][c] == 'M':
                    continue
                count = 0
                for dr, dc in directions:
                    nr, nc = r + dr, c + dc
                    if 0 <= nr < self.rows and 0 <= nc < self.cols:
                        if self.board[nr][nc] == 'M':
                            count += 1
                self.board[r][c] = count

    def print_board(self):
        print("   " + " ".join(str(c) for c in range(self.cols)))
        for r in range(self.rows):
            row_str = []
            for c in range(self.cols):
                if self.visible[r][c]:
                    val = self.board[r][c]
                    row_str.append(str(val) if val != 0 else '.')
                elif self.flags[r][c]:
                    row_str.append('F')
                else:
                    row_str.append('#')
            print(f"{r:2} " + " ".join(row_str))

    def in_bounds(self, r, c):
        return 0 <= r < self.rows and 0 <= c < self.cols

    def reveal(self, r, c):
        if not self.in_bounds(r, c) or self.visible[r][c] or self.flags[r][c]:
            return True
        self.visible[r][c] = True
        if self.board[r][c] == 'M':
            return False
        self.uncovered += 1
        if self.board[r][c] == 0:
            for dr in [-1, 0, 1]:
                for dc in [-1, 0, 1]:
                    if dr == 0 and dc == 0:
                        continue
                    self.reveal(r + dr, c + dc)
        return True

    def toggle_flag(self, r, c):
        if not self.in_bounds(r, c) or self.visible[r][c]:
            return
        self.flags[r][c] = not self.flags[r][c]

    def check_win(self):
        return self.uncovered == self.rows * self.cols - self.mines

    def play(self):
        while True:
            self.print_board()
            move = input("Enter move (r c) or flag (f r c): ").split()
            if not move:
                continue
            if move[0].lower() == 'f' and len(move) == 3:
                r, c = int(move[1]), int(move[2])
                self.toggle_flag(r, c)
            elif len(move) == 2:
                r, c = int(move[0]), int(move[1])
                alive = self.reveal(r, c)
                if not alive:
                    self.print_board()
                    print("BOOM! You hit a mine.")
                    return
                if self.check_win():
                    self.print_board()
                    print("Congratulations! You cleared the board.")
                    return
            else:
                print("Invalid move. Try again.")

if __name__ == "__main__":
    game = Minesweeper()
    game.play()
