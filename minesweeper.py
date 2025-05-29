import random
from dataclasses import dataclass, field
from typing import List, Set, Tuple

@dataclass
class Minesweeper:
    width: int = 9
    height: int = 9
    mines: int = 10
    mine_positions: Set[Tuple[int, int]] = field(default_factory=set)
    opened: Set[Tuple[int, int]] = field(default_factory=set)
    flagged: Set[Tuple[int, int]] = field(default_factory=set)

    def __post_init__(self):
        self._place_mines()

    def _place_mines(self):
        all_cells = [(x, y) for x in range(self.width) for y in range(self.height)]
        self.mine_positions = set(random.sample(all_cells, self.mines))

    def in_bounds(self, x: int, y: int) -> bool:
        return 0 <= x < self.width and 0 <= y < self.height

    def adjacent_mines(self, x: int, y: int) -> int:
        deltas = [(-1,-1),(-1,0),(-1,1),(0,-1),(0,1),(1,-1),(1,0),(1,1)]
        return sum((x+dx, y+dy) in self.mine_positions for dx, dy in deltas if self.in_bounds(x+dx, y+dy))

    def open_cell(self, x: int, y: int) -> bool:
        if not self.in_bounds(x, y) or (x, y) in self.opened or (x, y) in self.flagged:
            return True
        self.opened.add((x, y))
        if (x, y) in self.mine_positions:
            return False
        if self.adjacent_mines(x, y) == 0:
            for dx in [-1,0,1]:
                for dy in [-1,0,1]:
                    if dx or dy:
                        self.open_cell(x+dx, y+dy)
        return True

    def toggle_flag(self, x: int, y: int):
        if not self.in_bounds(x, y) or (x, y) in self.opened:
            return
        if (x, y) in self.flagged:
            self.flagged.remove((x, y))
        else:
            self.flagged.add((x, y))

    def is_victory(self) -> bool:
        return len(self.opened) == self.width * self.height - self.mines

    def display(self):
        for y in range(self.height):
            row = []
            for x in range(self.width):
                if (x, y) in self.flagged:
                    row.append('F')
                elif (x, y) not in self.opened:
                    row.append('.')
                elif (x, y) in self.mine_positions:
                    row.append('*')
                else:
                    count = self.adjacent_mines(x, y)
                    row.append(str(count) if count > 0 else ' ')
            print(' '.join(row))
        print()


def main():
    print('Welcome to Minesweeper!')
    game = Minesweeper()
    while True:
        game.display()
        if game.is_victory():
            print('You cleared all the mines! Congratulations!')
            break
        try:
            cmd = input('Enter command (open x y / flag x y): ').strip().split()
        except EOFError:
            print()
            break
        if not cmd:
            continue
        if cmd[0] == 'open' and len(cmd) == 3:
            x, y = map(int, cmd[1:])
            alive = game.open_cell(x, y)
            if not alive:
                game.display()
                print('Boom! You hit a mine. Game over.')
                break
        elif cmd[0] == 'flag' and len(cmd) == 3:
            x, y = map(int, cmd[1:])
            game.toggle_flag(x, y)
        else:
            print('Invalid command.')


if __name__ == '__main__':
    main()
