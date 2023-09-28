import datetime, logging, os
from ChessHandler import ChessHandler
from utils import INTRO_TEXT
import setup
STOCKFISH_PATH = "./stockfish/stockfish-ubuntu-x86-64-avx2" # Hardcoded path
PUZZLE_PATH = "./chess_puzzles.csv" # Hardcoded path
TOKEN = str(os.environ['TOKEN']) # Set environment variable via Heroku
SECRET = str(os.environ['SECRET']) # Set environment variable via Heroku
APPNAME = str(os.environ['APPNAME']) # Set environment var via Heroku
PORT = int(os.environ.get('PORT', '8443'))
#from config import TOKEN

from telegram import (
    Poll,
    ReplyKeyboardMarkup,
    Update,
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    PollAnswerHandler,
    CallbackContext,
    ContextTypes,
)


logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logging.getLogger().setLevel(logging.INFO)


# Telegram utility functions
def remove_queued(job_queue, job_name):
    """
    Remove jobs from job queue.
    """
    for job in job_queue.get_jobs_by_name(job_name):
        job.schedule_removal()


# Telegram command handlers
async def start(update: Update, context: CallbackContext) -> None:
    """
    Inform user about what this bot can do
    """

    reply_keyboard = [["/puzzle", "/votechess"]]
    reply_markup = ReplyKeyboardMarkup(
            reply_keyboard, one_time_keyboard=True, input_field_placeholder="Select command to start."
        )
    await context.bot.send_message(chat_id=update.effective_chat.id, text=INTRO_TEXT, reply_markup=reply_markup)


async def schedule_daily_puzzle(update: Update, context: CallbackContext) -> None:
    """
    Schedules a puzzle to be sent to the chat at SGT time daily.
    """
    chat_id = update.effective_chat.id
    job_name = "daily_puzzle_" + str(chat_id)

    time_str = "1000"
    if context.args and context.args[0].isdigit() and len(context.args[0]) == 4:
        time_str = context.args[0]
        
    hour = int(time_str[:2])
    minute = int(time_str[2:])
    hour = (hour - 8)%24 # Convert SGT to UTC
    time = datetime.time(hour=hour, minute=minute, second=15)

    job = context.job_queue.run_daily(send_puzzle, time=time, chat_id=chat_id, name=job_name)
    if job:
        reply = f"Scheduling daily puzzle at {time_str}H (SGT) everyday."
    else:
        reply = "Scheduling failed, please try again!"
    await context.bot.send_message(chat_id=update.effective_chat.id, text=reply)


async def puzzle(update: Update, context: CallbackContext) -> None:
    """
    Schedules a puzzle to be sent immediately.
    """
    context.job_queue.run_once(send_puzzle, 0, chat_id=update.message.chat_id)


async def send_puzzle(context: CallbackContext) -> None:
    """
    Sends a puzzle poll to the chat.
    """
    chat_id = context.job.chat_id
    board_img, choices, solution_ind, prompt, explanation = chess_handler.generate_puzzle()

    await context.bot.send_photo(photo=board_img,chat_id=chat_id)

    await context.bot.send_poll(
        question = prompt, options = choices, correct_option_id=solution_ind,
        type=Poll.QUIZ, allows_multiple_answers = False, explanation=explanation,
        chat_id=chat_id, is_anonymous = False
    )


async def schedule_vote_chess(update: Update, context: CallbackContext) -> None:
    """
    Schedules a vote chess to be sent to the chat at SGT time daily.
    """
    chat_id = update.effective_chat.id
    job_name = "vote_chess_" + str(chat_id)

    time_str = "2200"
    if context.args and context.args[0].isdigit() and len(context.args[0]) == 4:
        time_str = context.args[0]

    hour = int(time_str[:2])
    minute = int(time_str[2:])
    hour = (hour - 8)%24 # Convert SGT to UTC
    time = datetime.time(hour=hour, minute=minute, second=0)

    job = context.job_queue.run_daily(send_vote_chess, time=time, chat_id=chat_id, name=job_name)
    if job:
        reply = f"Scheduling vote chess at {time_str}H (SGT) everyday."
    else:
        reply = "Scheduling failed, please try again!"
    await context.bot.send_message(chat_id=update.effective_chat.id, text=reply)


async def stop_vote_chess(update: Update, context: CallbackContext):
    """
    Ends the current game of votechess
    """
    chat_id = update.effective_chat.id
    vc_data = context.bot_data.get("vote_chess")
    if vc_data and vc_data.get(chat_id):
        vc_data.pop(chat_id)
    await context.bot.send_message(chat_id=chat_id, text="Terminated current votechess.")


async def vote_chess(update: Update, context: CallbackContext):
    """
    Schedules a vote chess to be sent immediately.
    """
    chat_id = update.effective_chat.id
    context.job_queue.run_once(send_vote_chess, 0, chat_id=chat_id)


async def send_vote_chess(context: CallbackContext) -> None:
    """
    Sends a votechess poll to the chat.
    """
    chat_id = context.job.chat_id
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

    message = await context.bot.send_photo(photo=board_img,chat_id=chat_id)
    cleaned_choices = [choice.replace("#", "+") for choice in choices]
    # Case: Game has not ended
    if solution_ind >= 0:
        message = await context.bot.send_poll(
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
        message = await context.bot.send_message(chat_id=chat_id, text=prompt)
        vc_data.pop(chat_id)

    context.bot_data.update({"vote_chess": vc_data})


async def schedule_view(update: Update, context: CallbackContext) -> None:
    """
    Sends list of all scheduled jobs for the chat.
    """
    chat_id = update.effective_chat.id
    job_names = ["vote_chess_" + str(chat_id), "daily_puzzle_" + str(chat_id)]
    reply_list = []
    for job_name in job_names:
        name = job_name.replace(str(chat_id), "").replace("_", "")
        for job in context.job_queue.get_jobs_by_name(job_name):
            sgt_time = job.next_t + datetime.timedelta(hours=8)
            sgt_time = sgt_time.strftime("%d/%m/%y %H%MH")
            reply_list.append(f"{name} - {sgt_time}")

    if len(reply_list) == 0:
        reply = "There are no scheduled tasks."
    else:
        reply = "Schedule (SGT):\n" + "\n".join(reply_list)
    await context.bot.send_message(chat_id=chat_id, text=reply)


async def schedule_clear(update: Update, context: CallbackContext) -> None:
    """
    Clears all scheduled tasks for the chat.
    """
    chat_id = update.effective_chat.id
    job_names = ["vote_chess_" + str(chat_id), "daily_puzzle_" + str(chat_id)]
    for job_name in job_names:
        remove_queued(context.job_queue, job_name)

    reply = "All scheduled tasks have been cleared."
    await context.bot.send_message(chat_id=chat_id, text=reply)


async def receive_poll_answer(update: Update, context: CallbackContext) -> None:
    """
    Updates bot data whenever a user submits a poll vote.
    """
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
    """
    Builds telegram application and runs it.
    """
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler('start', start))
    app.add_handler(CommandHandler('schedule_view', schedule_view))
    app.add_handler(CommandHandler('schedule_clear', schedule_clear))

    app.add_handler(PollAnswerHandler(receive_poll_answer))

    app.add_handler(CommandHandler('puzzle', puzzle))
    app.add_handler(CommandHandler('schedule_dailypuzzle', schedule_daily_puzzle))

    app.add_handler(CommandHandler('votechess', vote_chess))
    app.add_handler(CommandHandler('schedule_votechess', schedule_vote_chess))
    app.add_handler(CommandHandler('stop_votechess', stop_vote_chess))
    
    logging.info("Chessbot initialized.")
    
    #app.run_polling()
    app.run_webhook(
    listen="0.0.0.0",
    port=PORT,
    secret_token=SECRET,
    webhook_url=f"https://{APPNAME}.herokuapp.com/"
    )
    

if __name__ == "__main__":
    setup.download_stockfish()
    chess_handler = ChessHandler(STOCKFISH_PATH, PUZZLE_PATH)

    main()