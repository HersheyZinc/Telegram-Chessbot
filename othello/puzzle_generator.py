import pandas as pd
from board import Board
import minimax as minimax


game_moves = "f5d6c4d3e6f4e3f6c5b4e7f3c6d7b5a5c3b3g5h5g4h4e2g6b6d8c7c8a4a6a7f1a3c2d2b2e1b7g3h3f2d1a1a2b1a8c1g1f7g8e8f8b8g7h8h7h6h2g2h1"



b = Board()
move_count = 0
while len(game_moves)>=2:
    move = game_moves[:2]
    game_moves = game_moves[2:]
    b.push(move)
    move_count+=1
    print(move_count)
    if move_count < 30:
        continue
    elif move_count < 45:
        depth = 3
        threshold = 30
    else:
        depth = 5
        threshold = 50
    moves = minimax.find_best_moves(b,depth=depth)
    if len(moves) < 2:
        continue
    elif abs(moves[0]["eval"]) - abs(moves[1]["eval"]) > threshold:
        solution = Board.coord2move(moves[0]["move"])
        moves = " ".join([Board.coord2move(move["move"]) for move in moves[1:]])
        row = {"board_state": b.get_board_state(), "solution": solution, "moves":moves}
        print(row)