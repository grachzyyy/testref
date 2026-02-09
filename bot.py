import asyncio
import os
import aiosqlite
from aiogram import Bot, Dispatcher
from aiogram.types import Message
from aiogram.filters import Command
from aiogram.utils.deep_linking import create_start_link

# =========================
# НАСТРОЙКИ
# =========================

BOT_TOKEN = os.getenv("BOT_TOKEN")

GROUP_ID = -1003609007517
ADMIN_ID = 5113023867

REQUIRED_REFERRALS = 5
MAX_USERS = 2000

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# =========================
# DATABASE
# =========================

async def init_db():
    async with aiosqlite.connect("database.db") as db:
        await db.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            referrer_id INTEGER,
            referrals INTEGER DEFAULT 0,
            joined INTEGER DEFAULT 0
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


async def count_joined():
    async with aiosqlite.connect("database.db") as db:
        async with db.execute(
            "SELECT COUNT(*) FROM users WHERE joined=1"
        ) as cursor:
            result = await cursor.fetchone()
            return result[0]


async def top_referrers():
    async with aiosqlite.connect("database.db") as db:
        async with db.execute("""
            SELECT user_id, referrals
            FROM users
            ORDER BY referrals DESC
            LIMIT 10
        """) as cursor:
            return await cursor.fetchall()


# =========================
# START
# =========================

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
                referrer_id = None

        await add_user(user_id, referrer_id)

        if referrer_id:
            await add_referral(referrer_id)

    link = await create_start_link(bot, str(user_id), encode=False)

    await message.answer(
        f"👋 Добро пожаловать!\n\n"
        f"Для доступа в закрытую группу нужно {REQUIRED_REFERRALS} рефералов.\n\n"
        f"Ваша ссылка:\n{link}\n\n"
        f"Проверить прогресс: /stats\n"
        f"Получить доступ: /access\n\n"
        f"(Тестовая команда: /alluser)"
    )


# =========================
# СТАТИСТИКА
# =========================

@dp.message(Command("stats"))
async def stats(message: Message):
    user = await get_user(message.from_user.id)

    if not user:
        return await message.answer("Сначала нажмите /start")

    referrals = user[2]

    await message.answer(
        f"👥 Вы пригласили: {referrals}/{REQUIRED_REFERRALS}"
    )


# =========================
# ДОСТУП ПО РЕФЕРАЛАМ
# =========================

async def give_access(message: Message):
    user_id = message.from_user.id
    user = await get_user(user_id)

    if not user:
        return await message.answer("Сначала нажмите /start")

    joined = user[3]

    if joined:
        return await message.answer("Вы уже получили ссылку.")

    total = await count_joined()

    if total >= MAX_USERS:
        return await message.answer("❌ Лимит 2000 участников достигнут.")

    invite = await bot.create_chat_invite_link(
        chat_id=GROUP_ID,
        member_limit=1
    )

    await set_joined(user_id)

    await message.answer(
        f"✅ Доступ открыт!\n\n"
        f"Ваша одноразовая ссылка:\n{invite.invite_link}"
    )


@dp.message(Command("access"))
async def access(message: Message):
    user = await get_user(message.from_user.id)

    if not user:
        return await message.answer("Сначала нажмите /start")

    referrals = user[2]

    if referrals < REQUIRED_REFERRALS:
        return await message.answer(
            f"❌ Нужно ещё {REQUIRED_REFERRALS - referrals} приглашений."
        )

    await give_access(message)


# =========================
# ТЕСТОВЫЙ ПРОПУСК
# =========================

@dp.message(Command("alluser"))
async def alluser(message: Message):
    await give_access(message)


# =========================
# АДМИН
# =========================

@dp.message(Command("admin"))
async def admin(message: Message):
    if message.from_user.id != ADMIN_ID:
        return

    total = await count_joined()
    top = await top_referrers()

    text = f"📊 Участников: {total}/{MAX_USERS}\n\n🏆 ТОП 10:\n"

    for user_id, refs in top:
        text += f"{user_id} — {refs}\n"

    await message.answer(text)


# =========================
# ЗАПУСК
# =========================

async def main():
    await init_db()
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
