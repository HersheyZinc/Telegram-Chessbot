import pandas as pd
from Othello.src.utils.board import Board
import Othello.src.utils.minimax as minimax
from tqdm import tqdm

df = pd.read_csv("Othello/src/utils/othello_dataset.csv")

puzzle_df = pd.DataFrame(columns=["board_state", "solution", "moves"])
for game_moves in tqdm(df["game_moves"]):
    b = Board()
    move_count = 0
    while len(game_moves)>=2:
        move = game_moves[:2]
        game_moves = game_moves[2:]
        b.push(move)
        move_count+=1
        if move_count < 55:
            continue
        else:
            depth = 5
            threshold = 40
        moves = minimax.find_best_moves(b,depth=depth)
        if len(moves) < 2:
            continue
        elif abs(moves[0]["eval"]) - abs(moves[1]["eval"]) > threshold:
            solution = Board.coord2move(moves[0]["move"])
            moves = " ".join([Board.coord2move(move["move"]) for move in moves[1:]])
            #row = pd.DataFrame([b.get_board_state(), solution, moves], columns=["board_state", "solution", "moves"])
            row = {"board_state": b.get_board_state(), "solution": solution, "moves":moves}
            puzzle_df.loc[len(puzzle_df)] = row
            #pd.concat([puzzle_df, pd.DataFrame(row.values(), columns=puzzle_df.columns)], ignore_index=True)

    puzzle_df.to_csv("othello_puzzles.csv",index=False)