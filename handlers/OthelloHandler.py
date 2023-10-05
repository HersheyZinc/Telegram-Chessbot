from othello.board import Board
from othello import minimax
import pandas as pd
import random

class OthelloHandler:
    """
    Class for handling chess games and stockfish engine
    """
    def __init__(self, puzzle_path):
        #self.stockfish.update_engine_parameters({"Hash": 128, "Threads": "4"})

        self.puzzle_path = puzzle_path
        self.puzzle_gen = self.puzzle_generator(self.puzzle_path)

    
    def puzzle_generator(self, csv_path):
        for chunk in pd.read_csv(csv_path, chunksize=100):
            chunk = chunk.sample(frac=1)

            for _, row in chunk.iterrows():
                board_state = row["board_state"]
                moves = row["moves"].split(" ")
                solution = row["solution"]

                yield board_state, solution, moves


    def generate_puzzle(self):
        try:
            board_state, solution, choices = next(self.puzzle_gen)
        except Exception:
            self.puzzle_gen = self.puzzle_generator(self.puzzle_path)
            board_state, solution, choices = next(self.puzzle_gen)
        b = Board(board_state)
        board_img = b.get_board()
        solution_ind = random.randint(0, len(choices))
        choices.insert(solution_ind, solution)
        turn = "White" if b.turn==Board.WHITE else "Black"
        prompt = f"{turn} to move"
        explanation = "Yes"


        return board_img, choices, solution_ind, prompt, explanation