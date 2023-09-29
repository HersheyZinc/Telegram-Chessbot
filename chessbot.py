import datetime, logging, os, random, redis, json
from enum import Enum
from ChessHandler import ChessHandler
from utils import INTRO_TEXT
import setup
from urllib.parse import urlparse


TOKEN = str(os.environ['TOKEN']) # Set environment variable via Heroku
SECRET = str(os.environ['SECRET']) # Set environment variable via Heroku
APPNAME = str(os.environ['APPNAME']) # Set environment var via Heroku
PORT = int(os.environ.get('PORT', '8443'))
REDIS_URL = os.environ.get('REDISCLOUD_URL')

#from config import TOKEN, REDIS_URL

REDIS = urlparse(REDIS_URL)
from telegram import (
    Poll,
    ReplyKeyboardMarkup,
    Update,
)
from telegram.ext import (
    ApplicationBuilder,
    Application,
    CommandHandler,
    PollAnswerHandler,
    CallbackContext,
)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logging.getLogger().setLevel(logging.INFO)


# --------------------------- Helper Functions --------------------------- #


class Task(Enum):
    CHESS_PUZZLE = "chess puzzle"
    CHESS_VOTE = "vote chess"


def remove_queued(job_queue, job_name):
    """
    Remove jobs from job queue.
    """
    for job in job_queue.get_jobs_by_name(job_name):
        job.schedule_removal()


# --------------------------- Chess Puzzle --------------------------- #


async def send_chess_puzzle(context: CallbackContext) -> None:
    """
    Sends a puzzle poll to the chat.
    """
    chat_id = context.job.chat_id
    board_img, choices, solution_ind, prompt, explanation = chess_handler.generate_puzzle()

    await context.bot.send_photo(photo=board_img,chat_id=chat_id)

    await context.bot.send_poll(
        question = prompt, options = choices, correct_option_id=solution_ind,
        type=Poll.QUIZ, allows_multiple_answers = False, explanation=explanation,
        chat_id=chat_id, is_anonymous = False, disable_notification=True
    )


async def chess_puzzle(update: Update, context: CallbackContext) -> None:
    """
    Schedules a puzzle to be sent immediately.
    """
    chat_id = update.effective_chat.id
    msg_id = update.effective_message.message_id
    context.job_queue.run_once(send_chess_puzzle, 0, chat_id=update.message.chat_id)
    context.job_queue.run_once(delete_msg, datetime.timedelta(minutes=30), chat_id=chat_id, data=msg_id)


async def schedule_chess_puzzle(update: Update, context: CallbackContext) -> None:
    """
    Schedules a puzzle to be sent to the chat at SGT time daily.
    """
    task = Task.CHESS_PUZZLE
    chat_id = update.effective_chat.id
    job_name = task.value + str(chat_id)

    # Check if user specified timing
    time_str = "2200"
    if context.args and context.args[0].isdigit() and len(context.args[0]) == 4:
        time_str = context.args[0]
    
    schedules = context.bot_data.get("schedules")
    schedule = (chat_id, task.value, time_str)
    if schedule not in schedules:
        hour = (int(time_str[:2]) - 8)%24 # Convert SGT to UTC
        minute = min(int(time_str[2:]),59)
        time = datetime.time(hour=hour, minute=minute, second=random.randint(0,15))

        job = context.job_queue.run_daily(send_chess_vote, time=time, 
                                          chat_id=chat_id, name=job_name,)
        if job:
            reply = f"Scheduling {task.value} at {time_str}H (SGT) everyday."
            schedules.append(schedule)
        else:
            reply = "Scheduling failed, please try again!"
    else:
        reply = f"Schedule for {task.value} already exists for {time_str}H, please try another timing!"

    await context.bot.send_message(chat_id=chat_id, text=reply)


# --------------------------- Vote Chess --------------------------- #


async def send_chess_vote(context: CallbackContext) -> None:
    """
    Sends a votechess poll to the chat.
    """
    chat_id = context.job.chat_id
    vc_data = context.bot_data.get("vote_chess")

    chat_data = vc_data.get(str(chat_id))
    # Case: Game has not been initialized
    if not chat_data:
        board_img, choices, solution_ind, prompt, fen = chess_handler.new_votechess()

    # Case: Game has been initialized
    else:
        fen = chat_data.get("board")
        # Get the most voted move
        moves = chat_data.get("player_moves")
        choices = []
        for player_choice in moves.values():
            choices.extend(player_choice)

        # Case: Nobody voted -> generate poll from the same position
        if len(choices) == 0:
            board_img, choices, solution_ind, prompt, fen = chess_handler.generate_votechess(fen, None)
        # Case: Top move exists
        else:
            top_choice = max(set(choices), key = choices.count) # If tie, selects first index
            top_move = chat_data.get("move_choices")[top_choice]
            board_img, choices, solution_ind, prompt, fen = chess_handler.generate_votechess(fen, top_move)

    message = await context.bot.send_photo(photo=board_img,chat_id=chat_id)
    cleaned_choices = [choice.replace("#", "+") for choice in choices]
    # Case: Game has not ended
    if solution_ind >= 0:
        message = await context.bot.send_poll(question = prompt, options = cleaned_choices,
                                              chat_id=chat_id, is_anonymous = False,
                                              disable_notification=True)

        data = {
            str(chat_id): {
                "board": fen,
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


async def stop_chess_vote(update: Update, context: CallbackContext):
    """
    Ends the current game of votechess
    """
    chat_id = update.effective_chat.id
    vc_data = context.bot_data.get("vote_chess")
    if vc_data and vc_data.get(str(chat_id)):
        vc_data.pop(str(chat_id))
    await context.bot.send_message(chat_id=chat_id, text="Terminated current votechess.")


async def chess_vote(update: Update, context: CallbackContext):
    """
    Schedules a vote chess to be sent immediately.
    """
    chat_id = update.effective_chat.id
    msg_id = update.effective_message.message_id
    context.job_queue.run_once(send_chess_vote, 0, chat_id=chat_id)
    context.job_queue.run_once(delete_msg, datetime.timedelta(minutes=30), chat_id=chat_id, data=msg_id)


async def schedule_chess_vote(update: Update, context: CallbackContext) -> None:
    """
    Schedules a vote chess to be sent to the chat at SGT time daily.
    """
    task = Task.CHESS_VOTE
    chat_id = update.effective_chat.id
    job_name = task.value + str(chat_id)

    # Check if user specified timing
    time_str = "1000"
    if context.args and context.args[0].isdigit() and len(context.args[0]) == 4:
        time_str = context.args[0]
    
    schedules = context.bot_data.get("schedules")
    schedule = (chat_id, task.value, time_str)
    if schedule not in schedules:
        hour = (int(time_str[:2]) - 8)%24 # Convert SGT to UTC
        minute = int(time_str[2:])
        time = datetime.time(hour=hour, minute=minute, second=random.randint(0,15))

        job = context.job_queue.run_daily(send_chess_vote, time=time,
                                          chat_id=chat_id, name=job_name,)
        if job:
            reply = f"Scheduling {task.value} at {time_str}H (SGT) everyday."
            schedules.append(schedule)
        else:
            reply = "Scheduling failed, please try again!"
    else:
        reply = f"Schedule for {task.value} already exists for {time_str}H, please try another timing!"

    await context.bot.send_message(chat_id=update.effective_chat.id, text=reply)


# --------------------------- Utility Functions --------------------------- #


async def start(update: Update, context: CallbackContext) -> None:
    """
    Inform user about what this bot can do
    """

    reply_keyboard = [["/puzzle", "/votechess"]]
    reply_markup = ReplyKeyboardMarkup(
            reply_keyboard, one_time_keyboard=True, input_field_placeholder="Select command to start."
        )
    await context.bot.send_message(chat_id=update.effective_chat.id, 
                                   text=INTRO_TEXT, reply_markup=reply_markup,
                                   disable_notification=True)


async def schedule_view(update: Update, context: CallbackContext) -> None:
    """
    Sends list of all scheduled jobs for the chat.
    """
    chat_id = update.effective_chat.id
    
    job_names = [task.value+str(chat_id) for task in Task]
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
    await context.bot.send_message(chat_id=chat_id, text=reply, disable_notification=True)


async def schedule_clear(update: Update, context: CallbackContext) -> None:
    """
    Clears all scheduled tasks for the chat.
    """
    chat_id = update.effective_chat.id
    job_names = [task.value+str(chat_id) for task in Task]
    for job_name in job_names:
        remove_queued(context.job_queue, job_name)
    
    schedules = context.bot_data.get("schedules")
    cleared_schedules = [sched for sched in schedules if sched[0]==chat_id]
    context.bot_data.update({"schedules":cleared_schedules})

    reply = "All scheduled tasks have been cleared."
    await context.bot.send_message(chat_id=chat_id, text=reply, disable_notification=True)


# --------------------------- Background Functions --------------------------- #


async def delete_msg(context: CallbackContext) -> None:
    """
    Deletes a message from chat
    """
    chat_id = context.job.chat_id
    msg_id = context.job.data
    await context.bot.delete_message(chat_id=chat_id, message_id=msg_id)


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
            chat_data = vc_data.get(str(chat_id))
            current_poll_id = chat_data["current_poll_id"]

            if poll_id == current_poll_id:
                chat_data["player_moves"][user_id] = option_ids
                break


async def init_app(app: Application) -> None:
    """
    Initialize persistent data, reschedule tasks if needed
    """
    r = redis.Redis(host=REDIS.hostname, port=REDIS.port, password=REDIS.password)
    try:
        bot_data_bytes = r.get(TOKEN)
        bot_data = json.loads(bot_data_bytes.decode('utf-8'))
    except Exception:
        logging.warning("No previous data discovered. Initializing empty bot data.")
        bot_data = {"vote_chess": {}, "schedules": []}
        app.bot_data.update(bot_data)
        return

    app.bot_data = bot_data
    chat_ids = []
    for schedule in bot_data.get("schedules"):
        chat_id, task, time_str = schedule
        job_name = task + str(chat_id)

        hour = (int(time_str[:2]) - 8)%24 # Convert SGT to UTC
        minute = min(int(time_str[2:]),59)
        time = datetime.time(hour=hour, minute=minute, second=random.randint(0,30))
        if task == Task.CHESS_PUZZLE.value:
            func = send_chess_puzzle
        elif task == Task.CHESS_VOTE.value:
            func = send_chess_vote
        else:
            func = send_chess_puzzle
        app.job_queue.run_daily(func, time=time, chat_id=chat_id,
                                name=job_name)

        continue
        if chat_id not in chat_ids:
                chat_ids.append(chat_id)
                msg = await app.bot.send_message(chat_id=chat_id, disable_notification=True,
                                        text="INFO:\nChess bot has been initialized.")
                app.job_queue.run_once(delete_msg, 60, chat_id=chat_id, data=msg.message_id)


async def stop_app(app: Application) -> None:
    """
    Inform users that telegram bot is shutting down
    """
    bot_data = app.bot_data
    r = redis.Redis(host=REDIS.hostname, port=REDIS.port, password=REDIS.password)
    bot_data_bytes = json.dumps(bot_data).encode('utf-8')
    r.set(TOKEN, bot_data_bytes)
    return
    chat_ids = []
    for schedule in bot_data.get("schedules"):
        chat_id, _, _ = schedule
        if chat_id not in chat_ids:
            chat_ids.append(chat_id)
            msg = await app.bot.send_message(chat_id=chat_id, disable_notification=True,
                                       text="INFO:\nChess bot is restarting...")
            app.job_queue.run_once(delete_msg, 60, chat_id=chat_id, data=msg.message_id)
            


# --------------------------- Main --------------------------- #


def main() -> None:
    """
    Builds telegram application and runs it.
    """
    app = ApplicationBuilder().token(TOKEN).post_init(init_app).post_stop(stop_app).build()

    app.add_handler(CommandHandler('start', start))
    app.add_handler(CommandHandler('schedule_view', schedule_view))
    app.add_handler(CommandHandler('schedule_clear', schedule_clear))
    app.add_handler(PollAnswerHandler(receive_poll_answer))

    app.add_handler(CommandHandler('puzzle', chess_puzzle))
    app.add_handler(CommandHandler('schedule_dailypuzzle', schedule_chess_puzzle))

    app.add_handler(CommandHandler('votechess', chess_vote))
    app.add_handler(CommandHandler('schedule_votechess', schedule_chess_vote))
    app.add_handler(CommandHandler('stop_votechess', stop_chess_vote))
    
    #app.run_polling()
    
    app.run_webhook(
    listen="0.0.0.0",
    port=PORT,
    secret_token=SECRET,
    webhook_url=f"https://{APPNAME}.herokuapp.com/"
    )
    

if __name__ == "__main__":
    setup.setup()
    chess_handler = ChessHandler(setup.STOCKFISH_PATH, setup.PUZZLE_PATH)
    main()