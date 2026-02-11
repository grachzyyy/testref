import asyncio
import aiosqlite
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.utils.deep_linking import create_start_link

# ================= НАСТРОЙКИ =================

BOT_TOKEN = "7964951860:AAH65UxfUC0xrj9In4njb0jbEpUfk-KDn9g"

GROUP_ID = -1003609007517
ADMIN_ID = 5113023867

REQUIRED_REFERRALS = 5
MAX_USERS = 2000

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# ================= DATABASE =================

async def init_db():
    async with aiosqlite.connect("database.db") as db:
        await db.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            referrer_id INTEGER,
            referrals INTEGER DEFAULT 0,
            joined INTEGER DEFAULT 0,
            wallet TEXT
        )
        """)
        await db.commit()

async def get_user(user_id):
    async with aiosqlite.connect("database.db") as db:
        async with db.execute(
            "SELECT * FROM users WHERE user_id=?",
            (user_id,)
        ) as cursor:
            return await cursor.fetchone()

async def add_user(user_id, referrer_id=None):
    async with aiosqlite.connect("database.db") as db:
        await db.execute(
            "INSERT OR IGNORE INTO users (user_id, referrer_id) VALUES (?, ?)",
            (user_id, referrer_id)
        )
        await db.commit()

async def add_referral(referrer_id):
    async with aiosqlite.connect("database.db") as db:
        await db.execute(
            "UPDATE users SET referrals = referrals + 1 WHERE user_id=?",
            (referrer_id,)
        )
        await db.commit()

async def set_joined(user_id):
    async with aiosqlite.connect("database.db") as db:
        await db.execute(
            "UPDATE users SET joined=1 WHERE user_id=?",
            (user_id,)
        )
        await db.commit()

async def save_wallet(user_id, wallet):
    async with aiosqlite.connect("database.db") as db:
        await db.execute(
            "UPDATE users SET wallet=? WHERE user_id=?",
            (wallet, user_id)
        )
        await db.commit()

async def count_joined():
    async with aiosqlite.connect("database.db") as db:
        async with db.execute(
            "SELECT COUNT(*) FROM users WHERE joined=1"
        ) as cursor:
            result = await cursor.fetchone()
            return result[0]

# ================= START =================

@dp.message(Command("start"))
async def start(message: Message):
    args = message.text.split()
    user_id = message.from_user.id

    user = await get_user(user_id)

    if not user:
        referrer_id = None
        if len(args) > 1:
            try:
                referrer_id = int(args[1])
                if referrer_id == user_id:
                    referrer_id = None
            except:
                pass

        await add_user(user_id, referrer_id)
        if referrer_id:
            await add_referral(referrer_id)

    link = await create_start_link(bot, str(user_id), encode=False)

    text = f"""
🔥 StableDrop

💰 Условия:
• 50 USDT за участие
• 30 USDT за каждого приглашённого (максимум 5)
• До 200 USDT суммарно

📌 Чтобы получить дроп:
1. Пригласите {REQUIRED_REFERRALS} друзей
2. Получите доступ в закрытую группу
3. После выполнения условий укажите USDT-адрес в сети TON

Ваша ссылка:
{link}

Команды:
/stats — прогресс
/access — получить доступ
/wallet — указать адрес
"""

    await message.answer(text)

# ================= STATS =================

@dp.message(Command("stats"))
async def stats(message: Message):
    user = await get_user(message.from_user.id)
    if not user:
        return await message.answer("Сначала нажмите /start")
    referrals = user[2]
    await message.answer(
        f"👥 Приглашено: {referrals}/{REQUIRED_REFERRALS}"
    )

# ================= ACCESS =================

async def give_access(message: Message):
    user_id = message.from_user.id
    user = await get_user(user_id)

    # Разрешить админу проходить всегда
    if user[3] and message.from_user.id != ADMIN_ID:
        return await message.answer("Вы уже получили доступ.")

    total = await count_joined()
    if total >= MAX_USERS and message.from_user.id != ADMIN_ID:
        return await message.answer("❌ Лимит участников достигнут.")

    invite = await bot.create_chat_invite_link(
        chat_id=GROUP_ID,
        member_limit=1
    )

    await set_joined(user_id)
    await message.answer(
        f"✅ Доступ открыт!\n\n{invite.invite_link}"
    )

@dp.message(Command("access"))
async def access(message: Message):
    user = await get_user(message.from_user.id)
    referrals = user[2]
    if referrals < REQUIRED_REFERRALS and message.from_user.id != ADMIN_ID:
        return await message.answer(
            f"❌ Нужно ещё {REQUIRED_REFERRALS - referrals} приглашений."
        )
    await give_access(message)

# ================= WALLET =================

@dp.message(Command("wallet"))
async def wallet_button(message: Message):
    user = await get_user(message.from_user.id)
    if not user or user[3] == 0:
        return await message.answer("Сначала получите доступ в группу.")
    builder = InlineKeyboardBuilder()
    builder.button(text="💳 Указать USDT адрес", callback_data="set_wallet")
    await message.answer(
        "Нажмите кнопку и отправьте USDT (TON) адрес:",
        reply_markup=builder.as_markup()
    )

@dp.callback_query(F.data == "set_wallet")
async def ask_wallet(callback: CallbackQuery):
    await callback.message.answer("Введите ваш USDT адрес в сети TON:")
    await callback.answer()

@dp.message()
async def save_wallet_message(message: Message):
    user = await get_user(message.from_user.id)
    if not user or user[3] == 0:
        return
    wallet = message.text.strip()
    if len(wallet) < 10:
        return
    await save_wallet(message.from_user.id, wallet)
    await message.answer("✅ Адрес сохранён. Ожидайте начисления.")

# ================= СКРЫТАЯ АДМИН-КОМАНДА =================

@dp.message(Command("alluser"))
async def alluser(message: Message):
    if message.from_user.id != ADMIN_ID:
        return
    await give_access(message)

# ================= RUN =================

async def main():
    await init_db()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
