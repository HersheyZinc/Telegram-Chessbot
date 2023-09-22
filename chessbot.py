import chess, chess.svg, random, datetime, logging
from stockfish import Stockfish
from cairosvg import svg2png
import pandas as pd
from telegram import (
    Poll,
    KeyboardButton,
    KeyboardButtonPollType,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.ext import (
    Updater,
    CommandHandler,
    PollAnswerHandler,
    PollHandler,
    MessageHandler,
    CallbackContext,
    CallbackQueryHandler,
)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logging.getLogger().setLevel(logging.INFO)

# ---------------------------------------------------------------------------------------------------------------------------------------------#

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
        choices = [ChessHandler.uci_to_san(board, top_moves[i]["Move"]) for i, _ in enumerate(top_moves)]

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
        board_img = ChessHandler.get_board_img(board)

        solution_uci = solution_line[0]
        solution_san = ChessHandler.uci_to_san(board, solution_uci)

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

        board_img = ChessHandler.get_board_img(board)

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
        board_img = ChessHandler.get_board_img(board)
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


# ---------------------------------------------------------------------------------------------------------------------------------------------#


# Telegram utility functions

def is_queued(job_queue, job_name):
    if len(job_queue.get_jobs_by_name(job_name)) == 0:
      return False
    else:
      return True

def remove_queued(job_queue, job_name):
    for job in job_queue.get_jobs_by_name(job_name):
        job.schedule_removal()


# Telegram command handlers
def start(update: Update, context: CallbackContext) -> None:
    """Inform user about what this bot can do"""
    text = """
Beep boop! Welcome to the Chessbot-3000. This bot lets you discover your inner chess with your friends!

Utility
/start - Displays the commands available


\U0001F9E9 Chess Puzzles \U0001F9E9
Challenge puzzles from the Lichess puzzle database!
/puzzle - Sends a puzzle
/schedule_dailypuzzle HHMM - Schedules a puzzle to be sent everyday (UTC)
/stop_dailypuzzle - Clears all daily puzzle schedules


\U0001F4CA Vote Chess \U0001F4CA
Team up with your friends to win Stockfish!
/votechess - Ends the current vote and initiates the next turn
/schedule_votechess HHMM - Schedules a vote chess to be sent everyday (UTC)
/stop_votechess - Clears all vote chess schedules
    """
    reply_keyboard = [["/puzzle", "/votechess"]]
    reply_markup = ReplyKeyboardMarkup(
            reply_keyboard, one_time_keyboard=True, input_field_placeholder="Select command to start."
        )
    context.bot.send_message(chat_id=update.effective_chat.id, text=text, reply_markup=reply_markup)


def schedule_daily_puzzle(update: Update, context: CallbackContext) -> None:
    chat_id = update.effective_chat.id
    job_name = "daily_puzzle_" + str(chat_id)

    if context.args and context.args[0].isdigit():
            time_str = context.args[0]
    else:
        time_str = "1400" # 2pm UTC -> 10pm SGT
    hour = int(time_str[:2])
    minute = int(time_str[2:])
    time = datetime.time(hour=hour, minute=minute, second=random.randint(30,59))

    context.job_queue.run_daily(send_puzzle, time=time, context=chat_id, name=job_name)
    context.bot.send_message(chat_id=chat_id, text=f"Scheduling daily puzzle at {time_str}H (UTC) everyday.")


def stop_daily_puzzle(update: Update, context: CallbackContext) -> None:
    chat_id = update.effective_chat.id
    job_name = "daily_puzzle_" + str(chat_id)

    remove_queued(context.job_queue, job_name)
    context.bot.send_message(chat_id=update.effective_chat.id, text="Daily puzzle schedule has been cleared!")


def puzzle(update: Update, context: CallbackContext) -> None:
    context.job_queue.run_once(send_puzzle, 0.1, context=update.message.chat_id)


def send_puzzle(context: CallbackContext) -> None:
    chat_id = context.job.context
    board_img, choices, solution_ind, prompt, explanation = chess_handler.generate_puzzle()

    context.bot.send_photo(photo=board_img,chat_id=chat_id)

    message = context.bot.send_poll(
        question = prompt, options = choices, correct_option_id=solution_ind,
        type=Poll.QUIZ, allows_multiple_answers = False, explanation=explanation,
        chat_id=chat_id, is_anonymous = False
    )


def schedule_vote_chess(update: Update, context: CallbackContext) -> None:
    chat_id = update.effective_chat.id
    job_name = "vote_chess_" + str(chat_id)

    if context.args and context.args[0].isdigit():
        time_str = context.args[0]
    else:
        time_str = "0200" # 2am UTC -> 10am SGT
    hour = int(time_str[:2])
    minute = int(time_str[2:])
    time = datetime.time(hour=hour, minute=minute, second=random.randint(0,29))

    context.job_queue.run_daily(send_vote_chess, time=time, context=update.message.chat_id, name=job_name)
    context.bot.send_message(chat_id=update.effective_chat.id, text=f"Scheduling vote chess at {time_str}H (UTC) everyday.")


def stop_vote_chess(update: Update, context: CallbackContext):
    chat_id = update.effective_chat.id
    job_name = "vote_chess_" + str(chat_id)
    remove_queued(context.job_queue, job_name)
    vc_data = context.bot_data.get("vote_chess")
    if vc_data and vc_data.get(chat_id):
        vc_data.pop(chat_id)
    context.bot.send_message(chat_id=update.effective_chat.id, text="Vote chess schedule has been cleared!")


def vote_chess(update: Update, context: CallbackContext):
    chat_id = update.effective_chat.id
    context.job_queue.run_once(send_vote_chess, 0.1, context=chat_id)


def send_vote_chess(context: CallbackContext) -> None:
    chat_id = context.job.context
    vc_data = context.bot_data.get("vote_chess")
    if not vc_data: vc_data = {}

    chat_data = vc_data.get(chat_id)
    # Case: Game has not been initialized
    if not chat_data:
        board_img, choices, solution_ind, prompt, board = chess_handler.new_votechess()

    # Case: Game has been initialized
    else:
        board = chat_data.get("board")
        # Get the most voted move
        moves = chat_data.get("player_moves")
        choices = []
        for player_choice in moves.values():
            choices.extend(player_choice)

        # Case: Nobody voted -> generate poll from the same position
        if len(choices) == 0:
            board_img, choices, solution_ind, prompt, board = chess_handler.generate_votechess(board, None)
        # Case: Top move exists
        else:
            top_choice = max(set(choices), key = choices.count) # If tie, selects first index
            top_move = chat_data.get("move_choices")[top_choice]
            board_img, choices, solution_ind, prompt, board = chess_handler.generate_votechess(board, top_move)

    context.bot.send_photo(photo=board_img,chat_id=chat_id)
    cleaned_choices = [choice.replace("#", "+") for choice in choices]
    # Case: Game has not ended
    if solution_ind >= 0:
        message = context.bot.send_poll(
            question = prompt, options = cleaned_choices, chat_id=chat_id, is_anonymous = False
        )

        data = {
            chat_id: {
                "board": board,
                "current_poll_id": message.poll.id,
                "move_choices": choices,
                "player_moves": {}
            }
        }
        vc_data.update(data)

    # Case: Game has ended
    else:
        context.bot.send_message(chat_id=chat_id, text=prompt)
        vc_data.pop(chat_id)

    context.bot_data.update({"vote_chess": vc_data})





def receive_poll_answer(update: Update, context: CallbackContext) -> None:

    answer = update.poll_answer
    poll_id = answer.poll_id
    user_id = answer["user"]['id']
    option_ids = answer["option_ids"]

    vc_data = context.bot_data.get("vote_chess")
    if vc_data:
        for chat_id in vc_data.keys():
            chat_data = vc_data.get(chat_id)
            current_poll_id = chat_data["current_poll_id"]

            if poll_id == current_poll_id:
                chat_data["player_moves"][user_id] = option_ids
                break







def main() -> None:
    """Run bot."""
    # Create the Updater and pass it your bot's token.
    updater = Updater(TOKEN)
    dp = updater.dispatcher

    # add handlers
    dp.add_handler(CommandHandler('start', start))

    dp.add_handler(PollAnswerHandler(receive_poll_answer))

    dp.add_handler(CommandHandler('puzzle', puzzle))
    dp.add_handler(CommandHandler('schedule_dailypuzzle', schedule_daily_puzzle))
    dp.add_handler(CommandHandler('stop_dailypuzzle', stop_daily_puzzle))

    dp.add_handler(CommandHandler('votechess', vote_chess))
    dp.add_handler(CommandHandler('schedule_votechess', schedule_vote_chess))
    dp.add_handler(CommandHandler('stop_votechess', stop_vote_chess))

    # Start the Bot
    updater.start_polling()
    logging.info("Chessbot initialized.")

    # Run the bot until the user presses Ctrl-C or the process receives SIGINT,
    # SIGTERM or SIGABRT

    updater.idle()
    logging.warning("Ending chessbot process.")

from config import TOKEN
stockfish_path = "./stockfish/stockfish-ubuntu-x86-64-avx2"
puzzle_path = "./chess_puzzles.csv"
chess_handler = ChessHandler(stockfish_path, puzzle_path)

main()