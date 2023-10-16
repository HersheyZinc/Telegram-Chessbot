import datetime, logging, os, random, redis, json
from enum import Enum
from handlers.ChessHandler import ChessHandler
from handlers.OthelloHandler import OthelloHandler
from utils.utils import INTRO_TEXT, ADMIN, ANNOUNCE_TEXT
import utils.setup as setup
from urllib.parse import urlparse


TOKEN = str(os.environ['TOKEN']) # Set environment variable via Heroku
SECRET = str(os.environ['SECRET']) # Set environment variable via Heroku
APPNAME = str(os.environ['APPNAME']) # Set environment var via Heroku
PORT = int(os.environ.get('PORT', '8443'))
REDIS_URL = os.environ.get('REDISCLOUD_URL')

#from utils.config import TOKEN, REDIS_URL

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
    filters,
)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logging.getLogger().setLevel(logging.INFO)


# --------------------------- Helper Functions --------------------------- #


class Task(Enum):
    CHESS_PUZZLE = "chess_puzzle"
    CHESS_VOTE = "vote_chess"
    OTHELLO_PUZZLE = "othello_puzzle"
    OTHELLO_VOTE = "vote_othello"


def remove_queued(job_queue, job_name):
    """
    Remove jobs from job queue.
    """
    for job in job_queue.get_jobs_by_name(job_name):
        job.schedule_removal()


# --------------------------- Logic Functions --------------------------- #


async def send_puzzle(context: CallbackContext) -> None:
    """
    Sends a puzzle poll to the chat.
    """
    chat_id = context.job.chat_id
    data = context.job.data
    handler = data["handler"]
    board_img, choices, solution_ind, prompt, explanation = handler.generate_puzzle()
    await context.bot.send_photo(photo=board_img,chat_id=chat_id)
    await context.bot.send_poll(
        question = prompt, options = choices, correct_option_id=solution_ind,
        type=Poll.QUIZ, allows_multiple_answers = False, explanation=explanation,
        chat_id=chat_id, is_anonymous = True, disable_notification=True
    )


async def send_votegame(context: CallbackContext) -> None:
    chat_id = context.job.chat_id
    data = context.job.data
    handler = data["handler"]
    task = data["task"]
    try:
        vc_data = context.bot_data.get(task.value)
    except:
        vc_data = {}
    chat_data = vc_data.get(str(chat_id))

    # Case: Game has not been initialized
    if not chat_data:
        board_img, choices, solution_ind, prompt, board_state = handler.new_votechess()

    # Case: Game has been initialized
    else:
        board_state = chat_data.get("board")
        # Get the most voted move
        moves = chat_data.get("player_moves")
        choices = []
        for player_choice in moves.values():
            choices.extend(player_choice)

        # Case: Nobody voted -> generate poll from the same position
        if len(choices) == 0:
            board_img, choices, solution_ind, prompt, board_state = handler.generate_votechess(board_state, None)
        # Case: Top move exists
        else:
            top_choice = max(set(choices), key = choices.count) # If tie, selects first index
            top_move = chat_data.get("move_choices")[top_choice]
            board_img, choices, solution_ind, prompt, board_state = handler.generate_votechess(board_state, top_move)

    message = await context.bot.send_photo(photo=board_img,chat_id=chat_id)
    cleaned_choices = [choice.replace("#", "+") for choice in choices]
    # Case: Game has not ended
    if solution_ind >= 0:
        message = await context.bot.send_poll(question = prompt, options = cleaned_choices,
                                              chat_id=chat_id, is_anonymous = False,
                                              disable_notification=True)

        data = {
            str(chat_id): {
                "board": board_state,
                "current_poll_id": message.poll.id,
                "move_choices": choices,
                "player_moves": {}
            }
        }
        vc_data.update(data)

    # Case: Game has ended
    else:
        message = await context.bot.send_message(chat_id=chat_id, text=prompt)
        vc_data.pop(str(chat_id))

    context.bot_data.update({task.value: vc_data})


# --------------------------- Main User Commands --------------------------- #


async def start(update: Update, context: CallbackContext) -> None:
    """
    Inform user about what this bot can do
    """
    reply_keyboard = [["/chess", "/votechess"],["/othello", "/voteothello"]]
    reply_markup = ReplyKeyboardMarkup(
            reply_keyboard, one_time_keyboard=True, input_field_placeholder="Select command to start."
        )
    await context.bot.send_message(chat_id=update.effective_chat.id, 
                                   text=INTRO_TEXT, reply_markup=reply_markup,
                                   disable_notification=True)


async def command_chess_puzzle(update: Update, context: CallbackContext) -> None:
    chat_id = update.effective_chat.id
    handler = chess_handler
    data = {"handler":handler, "task":Task.CHESS_PUZZLE}
    context.job_queue.run_once(send_puzzle, 0, chat_id=chat_id, data=data)


async def command_othello_puzzle(update: Update, context: CallbackContext) -> None:
    chat_id = update.effective_chat.id
    handler = othello_handler
    data = {"handler":handler, "task":Task.OTHELLO_PUZZLE}
    context.job_queue.run_once(send_puzzle, 0, chat_id=chat_id, data=data)
            

async def command_othello_vote(update: Update, context: CallbackContext) -> None:
    chat_id = update.effective_chat.id
    task = Task.OTHELLO_VOTE
    if context.args and context.args[0] == "resign":
        vc_data = context.bot_data.get(task.value)
        if vc_data and vc_data.get(str(chat_id)):
            vc_data.pop(str(chat_id))
        await context.bot.send_message(chat_id=chat_id, text= f"Terminated current game of {task.value}.")
    else:
        data = {"handler":othello_handler, "task":task}
        context.job_queue.run_once(send_votegame, 0, chat_id=chat_id, data=data)


async def command_chess_vote(update: Update, context: CallbackContext) -> None:
    chat_id = update.effective_chat.id
    task = Task.CHESS_VOTE
    if context.args and context.args[0] == "resign":
        vc_data = context.bot_data.get(task.value)
        if vc_data and vc_data.get(str(chat_id)):
            vc_data.pop(str(chat_id))
        await context.bot.send_message(chat_id=chat_id, text= f"Terminated current game of {task.value}.")
    else:
        data = {"handler":chess_handler, "task":task}
        context.job_queue.run_once(send_votegame, 0, chat_id=chat_id, data=data)


# --------------------------- Schedule Commands --------------------------- #


async def command_set_schedule(update: Update, context: CallbackContext) -> None:
    chat_id = update.effective_chat.id
    schedules = context.bot_data.get("schedules")
    handler, time_str, reply = None, None, ""

    # Parse user arguments
    if len(context.args) >= 2:
        # Game type
        game = context.args[0]
        if game == "chess":
            handler, task = chess_handler, Task.CHESS_PUZZLE
            send_game = send_puzzle
        elif game == "votechess":
            handler, task = chess_handler, Task.CHESS_VOTE
            send_game = send_votegame
        elif game == "othello" or game == "reversi":
            handler, task = othello_handler, Task.OTHELLO_PUZZLE
            send_game = send_puzzle
        elif game == "voteothello" or game == "votereversi":
            handler, task = othello_handler, Task.OTHELLO_VOTE
            send_game = send_votegame
        

        # Schedule time
        time_str = context.args[1]
        if context.args[1].isdigit() and len(context.args[1]) == 4:
            time_str = context.args[1]

    # Check if user arguments are valid
    if not handler or not time_str:
        reply = "Unrecognized arguments! Please follow the syntax: /schedule_puzzle <game> <time>"
        await context.bot.send_message(chat_id=chat_id, text=reply)
        return
    schedule = (chat_id, task.value, time_str)
    if schedule in schedules:
        reply = f"Invalid time - another instance of {task.value} is already running at {time_str}H"
        await context.bot.send_message(chat_id=chat_id, text=reply)
        return
        
    # Perform scheduling
    hour = (int(time_str[:2]) - 8)%24 # Convert SGT to UTC
    minute = min(int(time_str[2:]),59)
    time = datetime.time(hour=hour, minute=minute, second=random.randint(0,15))
    job_name = task.value + str(chat_id)
    data = {"handler":handler, "task":task,}
    job = context.job_queue.run_daily(send_game, time=time, data=data,
                                        chat_id=chat_id, name=job_name,)
    
    if job:
        reply = f"Scheduling {task.value} at {time_str}H (SGT) everyday."
        schedules.append(schedule)
    else:
        reply = "Scheduling failed, please try again!"
    
    await context.bot.send_message(chat_id=chat_id, text=reply)


async def command_get_schedule(update: Update, context: CallbackContext) -> None:
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


async def command_clear_schedule(update: Update, context: CallbackContext) -> None:
    """
    Clears all scheduled tasks for the chat.
    """
    chat_id = update.effective_chat.id
    job_names = [task.value+str(chat_id) for task in Task]
    for job_name in job_names:
        remove_queued(context.job_queue, job_name)
    
    schedules = context.bot_data.get("schedules")
    cleared_schedules = [sched for sched in schedules if sched[0]!=chat_id]
    context.bot_data.update({"schedules":cleared_schedules})

    reply = "All scheduled tasks have been cleared."
    await context.bot.send_message(chat_id=chat_id, text=reply, disable_notification=True)

# --------------------------- Admin Functions --------------------------- #

async def admin_reset_schedule(update: Update, context: CallbackContext) -> None:
    chat_id = update.effective_chat.id
    context.bot_data.update({"schedules": []})
    await context.bot.send_message(chat_id=chat_id, text="All scheduling reset. Effective next restart.", disable_notification=True)

async def admin_announcement(update: Update, context: CallbackContext) -> None:
    """
    Sends announcement to all chats with scheduled tasks
    """
    chat_ids = []
    for schedule in context.bot_data.get("schedules"):
        chat_id, _, _ = schedule
        if chat_id not in chat_ids:
            chat_ids.append(chat_id)
            await context.bot.send_message(chat_id=chat_id, disable_notification=False,
                                    text=ANNOUNCE_TEXT)


# --------------------------- Background Functions --------------------------- #


async def delete_msg(context: CallbackContext) -> None:
    """
    Deletes a message from chat
    """
    chat_id = context.job.chat_id
    msg_id = context.job.data
    await context.bot.delete_message(chat_id=chat_id, message_id=msg_id)


async def save_bot_data(context: CallbackContext) -> None:
    bot_data = context.bot_data
    r = redis.Redis(host=REDIS.hostname, port=REDIS.port, password=REDIS.password)
    bot_data_bytes = json.dumps(bot_data).encode('utf-8')
    r.set(TOKEN, bot_data_bytes)


async def receive_poll_answer(update: Update, context: CallbackContext) -> None:
    """
    Updates bot data whenever a user submits a poll vote.
    """
    answer = update.poll_answer
    poll_id = answer.poll_id
    user_id = answer["user"]['id']
    option_ids = answer["option_ids"]

    games_to_check = [Task.CHESS_VOTE, Task.OTHELLO_VOTE]
    for task in games_to_check:
        vc_data = context.bot_data.get(task.value)
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
    bot_data = {Task.CHESS_VOTE.value: {}, Task.OTHELLO_VOTE.value: {}, "schedules": []}
    app.bot_data.update(bot_data)
    r = redis.Redis(host=REDIS.hostname, port=REDIS.port, password=REDIS.password)
    try:
        bot_data_bytes = r.get(TOKEN)
        bot_data = json.loads(bot_data_bytes.decode('utf-8'))
        app.bot_data.update(bot_data)
    except Exception:
        logging.warning("No previous data discovered. Initializing empty bot data.")
        return
    
    for schedule in bot_data.get("schedules"):
        chat_id, task, time_str = schedule
        job_name = task + str(chat_id)

        hour = (int(time_str[:2]) - 8)%24 # Convert SGT to UTC
        minute = min(int(time_str[2:]),59)
        time = datetime.time(hour=hour, minute=minute, second=random.randint(0,30))
        if task == Task.CHESS_PUZZLE.value:
            data = {"handler":chess_handler, "task":Task.CHESS_PUZZLE,}
            func = send_puzzle
        elif task == Task.CHESS_VOTE.value:
            data = {"handler":chess_handler, "task":Task.CHESS_VOTE,}
            func = send_votegame
        elif task == Task.OTHELLO_PUZZLE.value:
            data = {"handler":othello_handler, "task":Task.OTHELLO_PUZZLE,}
            func = send_puzzle
        elif task == Task.OTHELLO_VOTE.value:
            data = {"handler":othello_handler, "task":Task.OTHELLO_VOTE,}
            func = send_votegame
        else:
            continue
        app.job_queue.run_daily(func, time=time, chat_id=chat_id,
                                name=job_name, data=data)
    
    
    time = datetime.time(hour=3)
    app.job_queue.run_daily(save_bot_data, time=time, name="maintenance")
    



async def stop_app(app: Application) -> None:
    """
    Inform users that telegram bot is shutting down
    """
    bot_data = app.bot_data
    r = redis.Redis(host=REDIS.hostname, port=REDIS.port, password=REDIS.password)
    bot_data_bytes = json.dumps(bot_data).encode('utf-8')
    r.set(TOKEN, bot_data_bytes)
    

# --------------------------- Main --------------------------- #


def main() -> None:
    """
    Builds telegram application and runs it.
    """
    app = ApplicationBuilder().token(TOKEN).post_init(init_app).post_stop(stop_app).build()

    # Utility
    app.add_handler(CommandHandler('start', start))

    # Scheduling
    app.add_handler(CommandHandler('schedule_view', command_get_schedule))
    app.add_handler(CommandHandler('schedule_clear', command_clear_schedule))
    app.add_handler(CommandHandler('schedule', command_set_schedule))
    
    # Vote games
    app.add_handler(CommandHandler('votechess', command_chess_vote))
    app.add_handler(CommandHandler('voteothello', command_othello_vote))

    # Puzzle games
    app.add_handler(CommandHandler('chess', command_chess_puzzle))
    app.add_handler(CommandHandler('othello', command_othello_puzzle))
    
    # Admin
    app.add_handler(CommandHandler("announcement", admin_announcement, filters.Chat(username=ADMIN)))
    app.add_handler(CommandHandler("schedule_clearall", admin_reset_schedule, filters.Chat(username=ADMIN)))

    # Background tasks
    app.add_handler(PollAnswerHandler(receive_poll_answer))

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
    othello_handler = OthelloHandler("data/othello_puzzles.csv")
    main()