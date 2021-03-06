from random import randint
from os import getenv
from dotenv import load_dotenv
import logging
from aiogram import Bot, Dispatcher, executor, types, exceptions
from asyncio import sleep
from peewee import *
from playhouse.db_url import connect
import time

load_dotenv()
bot = Bot(token=getenv('TG_TOKEN'))
dp = Dispatcher(bot)
db = connect(getenv('DATABASE_URL'))
logging.basicConfig(level=logging.INFO)
log = logging.getLogger('broadcast')
msg_counter = 0
global MSG_PER_SECOND
MSG_PER_SECOND = 5

class User(Model):
    id = IntegerField(null=False, unique=True, primary_key=True)
    nickname = CharField(null=False, unique=True, max_length=16)
    class Meta:
        database = db
        db_table = 'users'


async def msg_counter_reset():
    global msg_counter
    while True:
        await sleep(1)
        msg_counter = 0


async def send_message(user_id: int, text: str, disable_notif: bool=False):
    global msg_counter
    while msg_counter > MSG_PER_SECOND:
        print('Too many msgs!')
        log.warning('Too many msgs!')
        await sleep(0.1)
    msg_counter += 1
    try:
        await bot.send_message(user_id, text, 
                               disable_notification=disable_notif)
    except exceptions.BotBlocked:
        log.error(f"Target [ID:{user_id}]: blocked by user")
    except exceptions.ChatNotFound:
        log.error(f"Target [ID:{user_id}]: invalid user ID")
    except exceptions.RetryAfter as e:
        log.error(f"Target [ID:{user_id}]: Flood limit is exceeded." +
                                        "Sleep {e.timeout} seconds.")
        await sleep(e.timeout)
        return await send_message(user_id, text, disable_notif)
    except exceptions.UserDeactivated:
        log.error(f"Target [ID:{user_id}]: user is deactivated")
    except exceptions.TelegramAPIError:
        log.exception(f"Target [ID:{user_id}]: failed")
    else:
        return True
    return False


@dp.message_handler(commands=['flood']) # test sender
async def flood(message: types.Message):
    start = time.time()
    args = message.text.split()
    if len(args) > 2 and args[2].isdigit():
        MSG_PER_SECOND = args[2]
    if len(args) >= 2 and args[1].isdigit():
        for i in range(int(args[1])):
            await send_message(message.from_user.id, str(i))
    total_time = time.time() - start
    print(f'Общее время: {total_time}')
    print(f'Сообщений в секунду: {(int(args[1]))/total_time}')


@dp.message_handler(commands=['sleep']) # TMP TEST
async def sleeping(message: types.Message):
    for i in range(30, 0, -10):
        await message.answer(i)
        await sleep(10)
    await message.answer(0)


@dp.message_handler(commands=['start'])
async def start(message: types.Message):
    id = message.from_user.id
    if len(message.text.split()) > 2: # tmp to test db
        try:
            id = int(message.text.split()[1])
        except:
            message.answer('Error!')
            return
    reply = ''
    user = User.select().where(User.id == id)
    if user.exists():
        await send_message(message.from_user.id, f'{user.get().nickname}, ' +
                                             'you are already exist in db!')
    else:
        if len(message.text.split()) > 2: # tmp to test db
            try:
                nickname = ''.join(message.text.split()[2:])[:16]
            except:
                nickname = nickname_generator('Player') # end test
        elif type(message.from_user.username) is str:
            nickname = message.from_user.username[:16]
        elif type(message.from_user.first_name) is str:
            nickname = message.from_user.first_name[:16]
        elif type(message.from_user.last_name) is str:
            nickname = message.from_user.last_name[:16]
        else:
            nickname = nickname_generator('Player')
        user = User.select().where(User.nickname == nickname)
        if user.exists():
            reply += f'{nickname}, your name has already been taken.\n'
            nickname = nickname_generator(nickname)
            reply += f'We will call you {nickname}.\n'
        User.create(id=id, nickname=nickname)
        await send_message(message.from_user.id, reply+ f'Hello, {nickname}!')


@dp.message_handler(commands=['rename'])
async def rename(message: types.Message):
    await message.answer('WIP...') # TO DO


@dp.message_handler(commands=['roll']) # tmp
async def roll(message: types.Message):
    await message.answer('🎲 ' + str(randint(1, 6)))


@dp.message_handler(commands=['whoiam']) # userstat
async def whoami(message: types.Message):
    userinfo = 'id: ' + str(message.from_user.id)
    if type(message.from_user.username) is str:
        userinfo += '\n' + 'Nickname: ' + message.from_user.username
    if type(message.from_user.first_name) is str:
        userinfo += '\n' + 'F.Name: ' + message.from_user.first_name
    if type(message.from_user.last_name) is str:
        userinfo += '\n' + 'L.Name: ' + message.from_user.last_name
    await message.answer(userinfo)


@dp.message_handler(commands=['db']) # test
async def print_db(message: types.Message):
    text = ''
    for user in User.select():
        text += str(user.id) + ' ' + user.nickname + '\n'
    await message.answer(text)


@dp.message_handler(commands=['remove']) # test
async def db_remove(message: types.Message):
    try:
        id_list = [int(i) for i in message.text.split()[1:]]
        for id in id_list:
            user = User.select().where(User.id == id)
            if user.exists():
                user.get().delete_instance()
    except:
        await message.answer('Error!')
    await print_db(message)


@dp.message_handler(commands=['w']) # test, i think
async def whisper(message: types.Message):
    if len(message.text.split()) < 3:
        await message.answer('Usage: /w username message')
        return
    await bot.delete_message(chat_id=message.chat.id,
                             message_id=message.message_id)
    input_text = message.text.split()[1:]
    target = User.select().where(User.nickname == input_text[0])
    if target.exists():
        target = target.get().id
        sender = User.get(User.id == message.from_user.id).nickname
        text_to_send = sender +': ' + ' '.join(input_text[1:])
        try:
            await bot.send_message(chat_id=target, text=text_to_send)
            await message.answer(text_to_send)
        except:
            await message.answer('Error :(\nTarget user stoped the bot?')
    else:
        await message.answer('User not found.')


@dp.message_handler() # test?
async def echo(message: types.Message):
    await message.answer(message.text)


def nickname_generator(nickname):
    counter = 1
    check_name = User.select().where(User.nickname == nickname + str(counter))
    while check_name.exists():
        counter += 1
        if len(nickname + str(counter)) > 16:
            return nickname_generator('Player')
        check_name = User.select().where(User.nickname == nickname
                                                        + str(counter))
    return nickname + str(counter)


if __name__ == '__main__':
    dp.loop.create_task(msg_counter_reset())
    executor.start_polling(dp)