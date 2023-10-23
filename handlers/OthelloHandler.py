from othello.board import Board
from othello import minimax
import pandas as pd
import random

class OthelloHandler:
    """
    Class for handling chess games and stockfish engine
    """
    def __init__(self, puzzle_path):

        self.puzzle_path = puzzle_path
        self.puzzle_gen = self.puzzle_generator(self.puzzle_path)

    
    def puzzle_generator(self, csv_path):
        p = 0.2
        df = pd.read_csv(csv_path, skiprows=lambda i: i>0 and random.random() > p)
        df = pd.read_csv(csv_path)
        for _, row in df.iterrows():
            board_state = row["board_state"]
            moves = row["move_choices"].split(" ")
            solution = moves[0]
            moves = moves[1:]
            evaluations = row["evaluations"].split(" ")
            solution_line = row["solution_line"]
            

            yield board_state, solution, moves, evaluations, solution_line


    def generate_puzzle(self):
        try:
            board_state, solution, choices, evaluations, solution_line = next(self.puzzle_gen)
        except Exception:
            self.puzzle_gen = self.puzzle_generator(self.puzzle_path)
            board_state, solution, choices, evaluations, solution_line = next(self.puzzle_gen)
        b = Board(board_state)
        explanation = ", ".join([f"{move}: {eval}" for move, eval in zip([solution] + choices, evaluations)]) +\
                        f"\n\nSolution line: {solution_line}"
        board_img = b.get_board_img()
        solution_ind = random.randint(0, len(choices))
        choices.insert(solution_ind, solution)
        turn = "White" if b.turn==Board.WHITE else "Black"
        prompt = f"\U000026AA Othello Puzzle \U000026AB\n{turn} to move"

        return board_img, choices, solution_ind, prompt, explanation
    

    def get_mcq_choices(self, board, solution_san=None, choices_count=4, top_moves_count=5, depth=4):
        
        choices = minimax.find_best_moves(board, n=top_moves_count)
        #choices = [x["move"] for x in choices]
        if len(choices) == 0:
            return ["Error", "No legal moves found", 0]

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
        cpu_turn = board.turn
        while board.turn == cpu_turn and not board.check_game_over():

            best_moves = minimax.find_best_moves(board,n=4)
            best_moves = [x["move"] for x in best_moves]
            weights = [100, 20, 10, 5]
            #cpu_move = random.choices(best_moves, weights = weights[:len(best_moves)])[0]
            cpu_move = best_moves[0]
            board.push(cpu_move)



    def new_votechess(self):
        
        temp_path = "./data/othello_votechess.csv"
        df = pd.read_csv(temp_path)
        board_state = df.loc[random.randint(0,130)]["board_state"]
        board = Board(board_state)
        '''
        board = Board()
        if random.choice([True, False]):
            self.cpu_move(board)
        '''
        board_img = board.get_board_img()
        turn = "White" if board.turn==Board.WHITE else "Black"
        prompt = f"{turn} to move"
        choices, solution_ind = self.get_mcq_choices(board, choices_count=4, top_moves_count=5, depth=20)
        choices = [x["move"] for x in choices]
        prompt = "\U0001F4CA Vote Othello \U0001F4CA\n" + prompt
        return board_img, choices, solution_ind, prompt, board.get_board_state()


    def generate_votechess(self, board_state, move=None):
        board = Board(board_state)
        
        player_turn = board.turn
        if move:
            board.push(move)
            if not board.check_game_over() and board.turn != player_turn:
                self.cpu_move(board)

        # Case: Game has ended
        if board.check_game_over():
            outcome = board.get_score()
            winner = outcome["winner"]
            white_score = outcome["white"]
            black_score = outcome["black"]
            score = f"{black_score}-{white_score}"
            if winner is None:
                result = "drew"
                text = "That was close!"
            elif winner == player_turn:
                result = "won"
                text = "Congratulations!"
            else:
                result = "lost"
                text = "*Insert generic consolation text here*"
            prompt = f"The game has ended! You {result} {score}. {text}\nUse /voteothello to start a new game."
            choices, solution_ind = [], -1

        # Case: Game has not ended
        else:
            turn = "White" if board.turn==Board.WHITE else "Black"
            prompt = f"{turn} to move"
            choices, solution_ind = self.get_mcq_choices(board, choices_count=4, top_moves_count=5, depth=20)


        prompt = "\U0001F4CA Vote Othello \U0001F4CA\n" + prompt
        board_img = board.get_board_img()
        choices = [x["move"] for x in choices]
        return board_img, choices, solution_ind, prompt, board.get_board_state()
        