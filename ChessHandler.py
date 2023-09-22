from stockfish import Stockfish
from cairosvg import svg2png
import pandas as pd
import chess, chess.svg, random


class ChessHandler:
    def __init__(self, stockfish_path, puzzle_path):
        self.user_stockfish = Stockfish(path=stockfish_path)
        self.user_stockfish.set_depth(10)
        self.user_stockfish.set_elo_rating(2000)

        self.cpu_stockfish = Stockfish(path=stockfish_path)
        self.cpu_stockfish.set_depth(7)
        self.cpu_stockfish.set_elo_rating(1300)

        self.puzzle_path = puzzle_path
        self.puzzle_db = pd.read_csv(puzzle_path)


    def get_puzzle(self, rating=None):
        if rating:
            rating_lower = max(rating - 50, self.puzzle_db.min()["Rating"])
            rating_upper = min(rating + 50, self.puzzle_db.max()["Rating"])
            row = self.puzzle_db[(self.puzzle_db.Rating>=rating_lower) & (self.puzzle_db.Rating<=rating_upper)].sample()
        else:
            row = self.puzzle_db.sample()
        FEN = row["FEN"].values[0]
        moves = row["Moves"].values[0]
        rating = row["Rating"].values[0]
        solution_line = moves.split(" ")
        first_move = solution_line.pop(0)
        board = chess.Board(FEN)
        move = chess.Move.from_uci(first_move)
        board.push(move)
        return board, solution_line, rating


    def get_mcq_choices(self, board, solution_san=None, choices_count=4, top_moves_count=7):
        FEN = board.fen()
        self.user_stockfish.set_fen_position(FEN)
        top_moves = self.user_stockfish.get_top_moves(top_moves_count)
        if len(top_moves) == 0:
            return ["Error", "No legal moves found", 0]
        choices = [uci_to_san(board, top_moves[i]["Move"]) for i, _ in enumerate(top_moves)]

        if not solution_san:
            solution_san = choices[0]
        if choices_count < len(choices):
            choices = random.sample(choices, choices_count)

        if solution_san in choices:
            choices.remove(solution_san)
        else:
            choices.pop()
        solution_ind = random.randint(0,len(choices))
        choices.insert(solution_ind, solution_san)
        if len(choices) == 1:
            choices = choices * 2

        return choices, solution_ind


    def cpu_move(self, board):

        FEN = board.fen()
        self.cpu_stockfish.set_fen_position(FEN)
        cpu_move = self.cpu_stockfish.get_best_move()
        move = chess.Move.from_uci(cpu_move)
        board.push(move)

        return board


    def generate_puzzle(self, rating=None):
        board, solution_line, rating = self.get_puzzle(rating)
        board_img = get_board_img(board)

        solution_uci = solution_line[0]
        solution_san = uci_to_san(board, solution_uci)

        choices, solution_ind = self.get_mcq_choices(board, solution_san)

        turn = "White" if board.turn else "Black"
        prompt = f"\U0001F9E9 Chess Puzzle \U0001F9E9\n{turn} to move."
        explanation = "Solution line (in UCI): " + ", ".join(solution_line) + "\n Rating: {}".format(rating)
        return board_img, choices, solution_ind, prompt, explanation


    def new_votechess(self):
        board = chess.Board()
        # Randomize starting player
        if random.choice([True, False]):
          board = self.cpu_move(board)

        board_img = get_board_img(board)

        turn = "White" if board.turn else "Black"
        prompt = f"{turn} to move"
        choices, solution_ind = self.get_mcq_choices(board, choices_count=5, top_moves_count=8)
        prompt = "\U0001F4CA Vote Chess \U0001F4CA\n" + prompt
        return board_img, choices, solution_ind, prompt, board


    def generate_votechess(self, board, move=None):
        player_turn = board.turn
        if move:
            board.push_san(move) # move must be in san format
            outcome = board.outcome()
            if not outcome:
                board = self.cpu_move(board)

        outcome = board.outcome()
        # Case: Game has ended
        if outcome:
            winner = outcome.winner
            reason = chess.Termination(outcome.termination).name.lower()
            score = outcome.result()
            if winner is None:
                result = "drew"
                text = "That was close!"
            elif winner == player_turn:
                result = "won"
                text = "Congratulations!"
            else:
                result = "lost"
                text = "*Insert generic consolation text here*"
            prompt = f"The game has ended! You {result} {score} by {reason}. {text}\nUse /votechess to start a new game."
            choices, solution_ind = [], -1

        # Case: Game has not ended
        else:
            turn = "White" if board.turn else "Black"
            prompt = f"{turn} to move"
            choices, solution_ind = self.get_mcq_choices(board, choices_count=random.randint(3,4), top_moves_count=5)


        prompt = "\U0001F4CA Vote Chess \U0001F4CA\n" + prompt
        board_img = get_board_img(board)
        return board_img, choices, solution_ind, prompt, board


    # Static functions
def uci_to_san(board:chess.Board, uci:str):
    move = chess.Move.from_uci(uci)
    san = board.san(move)
    return san

def get_board_img(board: chess.Board):
    try:
        last_move = board.peek()
    except Exception as e:
        last_move = None
    boardsvg = chess.svg.board(board=board,flipped = not board.turn, lastmove = last_move)
    svg2png(bytestring=boardsvg,write_to='board.png')
    board_img = open("board.png", "rb")
    return board_img