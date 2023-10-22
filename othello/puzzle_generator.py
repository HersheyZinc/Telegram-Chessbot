import pandas as pd
from othello.board import Board
import othello.minimax as minimax
from tqdm import tqdm

def get_sign(evaluation):
    if evaluation > 0:
        return 1
    elif evaluation < 0:
        return -1
    else:
        return 0


def generate_puzzles(src_csv, dest_csv, n=100):
    df = pd.read_csv(src_csv)
    puzzle_count = 0

    puzzle_df = pd.DataFrame(columns=["board_state", "solution", "moves"])
    with tqdm(total=n) as pbar:
        for game_moves in df["game_moves"]:
            b = Board()
            if n and puzzle_count >= n:
                break
            while len(game_moves)>=2:
                move = game_moves[:2]
                game_moves = game_moves[2:]
                b.push(move)
                legal_moves = b.all_legal_moves()
                if b.move < 50:
                    continue
                elif b.move>56:
                    break
                elif len(legal_moves)<=2 or len(legal_moves)>=5:
                    continue
                
                moves = minimax.find_best_moves(b)
                move1 = moves[0]["eval"]
                move2 = moves[1]["eval"]
                if get_sign(move1) == get_sign(move2):
                    continue

                solution = moves[0]["move"]
                legal_moves = " ".join([move["move"] for move in moves[1:]])
                row = {"board_state": b.get_board_state(), "solution": solution, "moves":legal_moves}
                puzzle_df.loc[len(puzzle_df)] = row
                puzzle_count+=1
                pbar.update(1)
                puzzle_df.to_csv(dest_csv,index=False)
                break
                    
        #puzzle_df.to_csv(dest_csv,index=False)



def generate_votechess_positions(src_csv, dest_csv, n=500):
    df = pd.read_csv(src_csv)
    df = df.sample(n)
    vc_df = pd.DataFrame(columns=["board_state"])
    for index in tqdm(df.index):
        
        game_moves = df["game_moves"][index]

        b = Board()
        while len(game_moves)>=2:
            move = game_moves[:2]
            game_moves = game_moves[2:]
            b.push(move)
            if (b.move >= 48) and (b.move <= 54) and len(b.all_legal_moves())>=3 and len(b.all_legal_moves())<=4:
                best_move = minimax.find_best_moves(b,1)[0]
                if best_move["eval"] > 0:
                    row = {"board_state": b.get_board_state()}
                    vc_df.loc[len(vc_df)] = row
                    break
        
    vc_df.to_csv(dest_csv, index=False)



