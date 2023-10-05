import pandas as pd
from othello.board import Board
import othello.minimax as minimax
from tqdm import tqdm


def generate_puzzles(src_csv, dest_csv, n=100):
    df = pd.read_csv(src_csv)
    puzzle_count = 0

    puzzle_df = pd.DataFrame(columns=["board_state", "solution", "moves"])
    for game_moves in tqdm(df["game_moves"]):
        b = Board()
        move_count = 0
        if n and puzzle_count >= n:
            break
        while len(game_moves)>=2:
            move = game_moves[:2]
            game_moves = game_moves[2:]
            b.push(move)
            move_count+=1
            if move_count < 55:
                continue
            else:
                depth = 5
                threshold = 150
            moves = minimax.find_best_moves(b,depth=depth)
            if len(moves) < 3:
                continue
            elif abs(moves[0]["eval"]) - abs(moves[1]["eval"]) > threshold:
                solution = Board.coord2move(moves[0]["move"])
                moves = " ".join([Board.coord2move(move["move"]) for move in moves[1:]])
                row = {"board_state": b.get_board_state(), "solution": solution, "moves":moves}
                puzzle_df.loc[len(puzzle_df)] = row
                puzzle_count+=1
                
    puzzle_df.to_csv(dest_csv,index=False)