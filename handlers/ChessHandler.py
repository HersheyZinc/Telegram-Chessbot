from cairosvg import svg2png
import pandas as pd
from stockfish import Stockfish
import chess, chess.svg, random, tempfile, os
from copy import deepcopy
from PIL import Image, ImageFile
ImageFile.LOAD_TRUNCATED_IMAGES = True


class ChessHandler:
    """
    Class for handling chess games and stockfish engine
    """
    def __init__(self, stockfish_path, puzzle_path):

        self.stockfish = Stockfish(path=stockfish_path,depth=15)
        #self.stockfish.update_engine_parameters({"Hash": 128, "Threads": "4"})

        self.puzzle_path = puzzle_path
        self.puzzle_gen = self.puzzle_generator(self.puzzle_path)



    def puzzle_generator(self, csv_path, rating=None):
        """
        Generator that yields a random puzzle from the csv
        """
        p = 0.01
        df = pd.read_csv(csv_path, skiprows=lambda i: i>0 and random.random() > p)
        for _, row in df.iterrows():
            FEN = row["FEN"]
            moves = row["Moves"]
            puzzle_rating = row["Rating"]

            yield FEN, moves, puzzle_rating


    def get_mcq_choices(self, board, solution_san=None, choices_count=4, top_moves_count=5, rating=2500, depth=18):
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
        self.stockfish.set_elo_rating(rating)
        self.stockfish.set_depth(depth)
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


    def cpu_move(self, board, rating=1300, depth=11):
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
        self.stockfish.set_depth(depth)
        cpu_move = self.stockfish.get_best_move()
        move = chess.Move.from_uci(cpu_move)
        board.push(move)

        return board


    def generate_puzzle(self):
        """
        Generates a random puzzle with arguments for telegram poll format.
        """
        try:
            FEN, moves, puzzle_rating = next(self.puzzle_gen)
        except Exception:
            self.puzzle_gen = self.puzzle_generator(self.puzzle_path)
            FEN, moves, puzzle_rating = next(self.puzzle_gen)
        solution_line = moves.split(" ")
        first_move = solution_line.pop(0)
        board = chess.Board(FEN)
        move = chess.Move.from_uci(first_move)
        board.push(move)

        

        solution_uci = solution_line[0]
        solution_san = uci_to_san(board, solution_uci)

        choices, solution_ind = self.get_mcq_choices(board, solution_san, rating=2000, depth=13)

        turn = "White" if board.turn else "Black"
        prompt = f"\U0001F9E9 Chess Puzzle \U0001F9E9\n{turn} to move."

        solution_video, solution_line_san = ChessHandler.generate_solution_video(deepcopy(board), solution_line)
        explanation = "Solution line: " + ", ".join(solution_line_san) + f"\n Rating: {puzzle_rating}"
        board_img, _ = get_board_img(board)
        return board_img, choices, solution_ind, prompt, explanation, solution_video


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
            board = self.cpu_move(board,rating=2000,depth=7)

        board_img, _ = get_board_img(board)

        turn = "White" if board.turn else "Black"
        prompt = f"{turn} to move"
        choices, solution_ind = self.get_mcq_choices(board, choices_count=3, top_moves_count=7, rating=2000, depth=7)
        prompt = "\U0001F4CA Vote Chess \U0001F4CA\n" + prompt
        return board_img, choices, solution_ind, prompt, board.fen()


    def generate_votechess(self, fen, move=None, opponent_rating=2000):
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
        board = chess.Board(fen)
        player_turn = board.turn
        if move:
            board.push_san(move) # move must be in san format
            outcome = board.outcome()
            if not outcome:
                board = self.cpu_move(board, rating=opponent_rating, depth=17)

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
            choices, solution_ind = self.get_mcq_choices(board, choices_count=random.randint(3,4), top_moves_count=5,
                                                         rating=2500, depth=18)


        prompt = "\U0001F4CA Vote Chess \U0001F4CA\n" + prompt
        board_img, _ = get_board_img(board)
        return board_img, choices, solution_ind, prompt, board.fen()


    @staticmethod
    def generate_solution_video(board, solution_line):
        solution_line_san = []
        turn = not board.turn
        images = []
        filename = "solution.gif"

        _, first_im = get_board_img(board, pov=turn)

        for move in solution_line:
            solution_line_san.append(uci_to_san(board, move))
            board.push(chess.Move.from_uci(move))
            _, im = get_board_img(board, pov=turn)
            images.append(im)

        first_im.save(filename, save_all=True, append_images=images, duration=900, loop=0)
        solution_video = open(filename, "rb")
        return solution_video, solution_line_san

    # Static functions
def uci_to_san(board:chess.Board, uci:str):
    """
    Given a board state, converts move from UCI format to SAN format.
    """
    move = chess.Move.from_uci(uci)
    san = board.san(move)
    return san


def get_board_img(board: chess.Board, pov=None):
    """
    Renders a png image from a board state.
    """
    try:
        last_move = board.peek()
    except:
        last_move = None
    if pov is None:
        pov = not board.turn

    with tempfile.TemporaryDirectory() as tmpdirname:
        boardsvg = chess.svg.board(board=board,flipped = pov, lastmove = last_move)
        temp_path = os.path.join(tmpdirname, "board.png")
        svg2png(bytestring=boardsvg,write_to=temp_path)
        im = Image.open(temp_path)
        im_bytes = open(temp_path, "rb")
        
        return im_bytes, im


