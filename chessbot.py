import random, datetime, logging, os
from ChessHandler import ChessHandler
from utils import INTRO_TEXT
STOCKFISH_PATH = "./stockfish/stockfish-ubuntu-x86-64-avx2"
PUZZLE_PATH = "./chess_puzzles.csv"
TOKEN=os.environ['TOKEN']
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
    
    reply_keyboard = [["/puzzle", "/votechess"]]
    reply_markup = ReplyKeyboardMarkup(
            reply_keyboard, one_time_keyboard=True, input_field_placeholder="Select command to start."
        )
    context.bot.send_message(chat_id=update.effective_chat.id, text=INTRO_TEXT, reply_markup=reply_markup)


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

    context.bot.send_poll(
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



if __name__ == "__main__":
    chess_handler = ChessHandler(STOCKFISH_PATH, PUZZLE_PATH)
    main()