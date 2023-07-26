import asyncio
import aiohttp
import logging
from aiogram import Bot, Dispatcher, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters import Command
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.types import ParseMode
from aiogram.utils import executor

logging.basicConfig(level=logging.INFO)

API_TOKEN = 'BOT_TOKEN'

bot = Bot(token=API_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

class MonitorTransaction(StatesGroup):
    waiting_for_hash = State()
    waiting_for_confirmations = State()

async def get_transaction_data(tx_hash):
    url = f'https://xmrchain.net/api/transaction/{tx_hash}'
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            if response.status == 200:
                data = await response.json()
                return data
            else:
                return None

async def track_transaction(tx_hash, confirmations, chat_id):
    while True:
        data = await get_transaction_data(tx_hash)
        if data is None:
            await bot.send_message(chat_id, "Неверный хэш транзакции. Пожалуйста, попробуй еще раз.")
            return
        confirmations_received = data['data']['confirmations']
        if confirmations_received >= confirmations:
            await bot.send_message(chat_id, f"Транзакция {tx_hash} получила {confirmations} подтверждений.")
            await bot.send_message(chat_id, "Эта транзакция больше не будет отслеживаться. Для отслеживания новой транзакции нужно обязательно перезапустить бота командой /start")
            return
        await asyncio.sleep(5)

@dp.message_handler(Command('start'))
async def start_monitoring(message: types.Message):
    await message.answer("Введи хеш транзакции, которую хочешь отслеживать:")
    await MonitorTransaction.waiting_for_hash.set()

@dp.message_handler(state=MonitorTransaction.waiting_for_hash)
async def hash_received(message: types.Message, state: FSMContext):
    tx_hash = message.text.strip()
    if len(tx_hash) != 64:
        await message.answer("Неверный хеш транзакции. Попробуй ещё раз")
        return
    await state.update_data(tx_hash=tx_hash)
    await message.answer("Введи количество подтверждений (от 1 до 10), после которых хочешь получить уведомление:")
    await MonitorTransaction.waiting_for_confirmations.set()

@dp.message_handler(state=MonitorTransaction.waiting_for_confirmations)
async def confirmations_received(message: types.Message, state: FSMContext):
    confirmations = message.text.strip()
    if not confirmations.isdigit() or int(confirmations) < 1 or int(confirmations) > 10:
        await message.answer("Неверно. Введи значение от 1 до 10.")
        return
    async with state.proxy() as data:
        tx_hash = data['tx_hash']
        chat_id = message.chat.id
        await bot.send_message(chat_id, f"Я начал отслеживать транзакцию {tx_hash}. Я уведомлю тебя, когда она получит {confirmations} подтверждений.")
        asyncio.ensure_future(track_transaction(tx_hash, int(confirmations), chat_id))
    await state.finish()

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True) 
