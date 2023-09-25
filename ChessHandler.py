from cairosvg import svg2png
import pandas as pd
from stockfish import Stockfish
import chess, chess.svg, random


class ChessHandler:
    """
    Class for handling chess games and stockfish engine
    """
    def __init__(self, stockfish_path, puzzle_path):

        self.stockfish = Stockfish(path=stockfish_path,depth=7)

        self.puzzle_path = puzzle_path
        df = pd.read_csv(puzzle_path)
        self.puzzle_rows = df.shape[0]
        self.puzzle_colnames = df.columns

        #self.puzzle_db = pd.read_csv(puzzle_path)


    def get_puzzle(self, rating=None, sample_chunk_size=100):
        """
        Reads a random chess puzzle from the puzzle csv file.

            Parameters:
                rating (int): The rating of puzzle to be generated.
                sample_chunk_size (int): The number of rows to read at a time.

            Returns:
                board (chess.Board): The board state on the player's move.
                solution_line (list): List of moves (string) of the next moves
                rating (int): rating of the puzzle
        """
        start_row = random.randint(0,self.puzzle_rows-sample_chunk_size)
        puzzle_db = pd.read_csv(self.puzzle_path,nrows=sample_chunk_size,
                                skiprows=start_row,names=self.puzzle_colnames)
        if rating:
            rating_lower = max(rating - 50, puzzle_db.min()["Rating"])
            rating_upper = min(rating + 50, puzzle_db.max()["Rating"])
            row = puzzle_db[(puzzle_db.Rating>=rating_lower) & (puzzle_db.Rating<=rating_upper)].sample()
        else:
            row = puzzle_db.sample()
        FEN = row["FEN"].values[0]
        moves = row["Moves"].values[0]
        rating = row["Rating"].values[0]
        solution_line = moves.split(" ")
        first_move = solution_line.pop(0)
        board = chess.Board(FEN)
        move = chess.Move.from_uci(first_move)
        board.push(move)
        del puzzle_db
        return board, solution_line, rating


    def get_mcq_choices(self, board, solution_san=None, choices_count=4, top_moves_count=7):
        """
        Generates possible moves from a chess board.

            Parameters:
                board (chess.Board): chess board containing the current board state.
                solution_san (str): The best move in san format.
                choices_count (int): The number of choices to return.
                top_moves_count (int): The number of possible moves to generate.
            
            Returns:
                choices (list): list of possible moves in san format.
                solution_ind (int): index of the solution/best move.
        """
        FEN = board.fen()
        self.stockfish.set_fen_position(FEN)
        self.stockfish.set_elo_rating(2000)
        top_moves = self.stockfish.get_top_moves(top_moves_count)
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


    def cpu_move(self, board, rating=1300):
        """
        Plays the best possible move using stockfish engine.

            Parameters:
                board (chess.Board): current state of the board.
                rating (int): elo of stockfish engine.

            Returns:
                board (chess.Board): new state of board.
        """

        FEN = board.fen()
        self.stockfish.set_fen_position(FEN)
        self.stockfish.set_elo_rating(rating)
        cpu_move = self.stockfish.get_best_move()
        move = chess.Move.from_uci(cpu_move)
        board.push(move)

        return board


    def generate_puzzle(self, rating=None):
        """
        Generates a random puzzle with arguments for telegram poll format.

            Parameters:
                rating (int): rating of puzzle to be generated.

            Returns:
                board_img (image): image of current board.
                choices (list): list of possible moves.
                solution_ind (int): index of best move.
                prompt (str): string prompt to be sent with telegram poll.
                explanation (str): solution line and rating of puzzle.
        """
        board, solution_line, rating = self.get_puzzle(rating)
        board_img = get_board_img(board)

        solution_uci = solution_line[0]
        solution_san = uci_to_san(board, solution_uci)

        choices, solution_ind = self.get_mcq_choices(board, solution_san)

        turn = "White" if board.turn else "Black"
        prompt = f"\U0001F9E9 Chess Puzzle \U0001F9E9\n{turn} to move."
        explanation = "Solution line (in UCI): " + ", ".join(solution_line) + f"\n Rating: {rating}"
        return board_img, choices, solution_ind, prompt, explanation


    def new_votechess(self):
        """
        Creates a new votechess board and randomizes the starting player.

            Returns:
                board_img (image): image of current board.
                choices (list): list of possible moves.
                solution_ind (int): index of best move.
                prompt (str): string prompt to be sent with telegram poll.
                board (chess.Board): updated board state
        """
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
        """
        Takes player move and generates the next votechess board.

            Parameters:
                board (chess.Board): current board state.
                move (str): new player move to be inputted.

            Returns:
                board_img (image): image of current board.
                choices (list): list of possible moves.
                solution_ind (int): index of best move.
                prompt (str): string prompt to be sent with telegram poll.
                board (chess.Board): updated board state

        """
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
    """
    Given a board state, converts move from UCI format to SAN format.
    """
    move = chess.Move.from_uci(uci)
    san = board.san(move)
    return san


def get_board_img(board: chess.Board):
    """
    Renders a png image from a board state.
    """
    try:
        last_move = board.peek()
    except:
        last_move = None
    boardsvg = chess.svg.board(board=board,flipped = not board.turn, lastmove = last_move)
    svg2png(bytestring=boardsvg,write_to='board.png')
    board_img = open("board.png", "rb")
    return board_img