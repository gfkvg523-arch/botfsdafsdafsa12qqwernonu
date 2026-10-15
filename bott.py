import asyncio
import secrets
import aiosqlite
from aiogram import Bot, Dispatcher, F, Router
from aiogram.filters import Command, CommandStart, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, KeyboardButton, KeyboardButtonRequestUsers,
)
 
TOKEN = "8820474648:AAEb31XQxB1ltnl2YaFN3tPsVN3NFVIgoRM"
BOT_USERNAME = "anposlaniya_bot"          # без @
DB = "bot.db"
FOREVER_PREMIUM = {2086008732}      # вечный премиум
 
router = Router()
 
 
class St(StatesGroup):
    sending = State()   # пишем анонимку
    replying = State()  # отвечаем на анонимку
 
 
# ---------- БД ----------
async def init_db():
    async with aiosqlite.connect(DB) as db:
        await db.execute("""CREATE TABLE IF NOT EXISTS users(
            id INTEGER PRIMARY KEY, code TEXT UNIQUE, premium INTEGER DEFAULT 0)""")
        await db.execute("""CREATE TABLE IF NOT EXISTS msgs(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            from_id INTEGER, to_id INTEGER, replies INTEGER DEFAULT 0)""")
        await db.commit()
 
 
async def get_code(uid: int) -> str:
    async with aiosqlite.connect(DB) as db:
        cur = await db.execute("SELECT code FROM users WHERE id=?", (uid,))
        row = await cur.fetchone()
        if row:
            return row[0]
        code = secrets.token_urlsafe(6)
        await db.execute("INSERT INTO users(id, code) VALUES(?,?)", (uid, code))
        await db.commit()
        return code
 
 
async def user_by_code(code: str):
    async with aiosqlite.connect(DB) as db:
        cur = await db.execute("SELECT id FROM users WHERE code=?", (code,))
        row = await cur.fetchone()
        return row[0] if row else None
 
 
async def user_exists(uid: int) -> bool:
    async with aiosqlite.connect(DB) as db:
        cur = await db.execute("SELECT 1 FROM users WHERE id=?", (uid,))
        return bool(await cur.fetchone())
 
 
async def is_premium(uid: int) -> bool:
    if uid in FOREVER_PREMIUM:
        return True
    async with aiosqlite.connect(DB) as db:
        cur = await db.execute("SELECT premium FROM users WHERE id=?", (uid,))
        row = await cur.fetchone()
        return bool(row and row[0])
 
 
# ---------- клавиатуры ----------
def main_kb():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="💬 Начать получать послания")],
            [KeyboardButton(text="💌 Отправить послание"), KeyboardButton(text="❓ Как получать послания?")],
        ],
        resize_keyboard=True,
    )
 
 
def pick_user_kb():
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(
            text="👤 Выбрать получателя",
            request_users=KeyboardButtonRequestUsers(request_id=1, user_is_bot=False, max_quantity=1),
        )], [KeyboardButton(text="⬅️ Назад")]],
        resize_keyboard=True,
    )
 
 
# ---------- тексты ----------
async def link_text(uid: int):
    code = await get_code(uid)
    link = f"t.me/{BOT_USERNAME}?start={code}"
    share = f"https://t.me/share/url?url=https://{link}&text=По этой ссылке можно отправить мне анонимное сообщение 👉 💌"
    text = (f"💬 Начни получать анонимные сообщения прямо сейчас!\n\n"
            f"Твоя ссылка:\n👉 {link}\n\n"
            f"Добавь эту ссылку в описание профиля Telegram/TikTok/Instagram и в истории, "
            f"чтобы получать послания 💌")
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="📤 Поделиться ссылкой", url=share)]])
    return text, kb
 
 
# ---------- команды ----------
@router.message(CommandStart())
async def start(m: Message, command: CommandObject, state: FSMContext):
    await state.clear()
    await get_code(m.from_user.id)
 
    if command.args:
        target = await user_by_code(command.args)
        if target and target != m.from_user.id:
            await state.set_state(St.sending)
            await state.update_data(target=target)
            return await m.answer(
                "✍️ Напиши анонимное сообщение — я передам его человеку.\n"
                "Можно текст, фото, голосовое, стикер.\n\n"
                "ℹ️ Владельцы премиума могут видеть отправителей.",
                reply_markup=main_kb())
        if target == m.from_user.id:
            await m.answer("Это твоя собственная ссылка 🙂")
 
    text, kb = await link_text(m.from_user.id)
    await m.answer(text, reply_markup=kb)
    await m.answer("Выбери действие 👇", reply_markup=main_kb())
 
 
@router.message(F.text == "💬 Начать получать послания")
async def get_link(m: Message, state: FSMContext):
    await state.clear()
    text, kb = await link_text(m.from_user.id)
    await m.answer(text, reply_markup=kb)
 
 
@router.message(F.text == "❓ Как получать послания?")
async def how(m: Message):
    await m.answer("🤫 Чтобы получать сообщения — добавь свою ссылку в профиль и истории.\n"
                   "Любой, кто перейдёт по ней, сможет написать тебе анонимно.")
 
 
@router.message(Command("send"))
@router.message(F.text == "💌 Отправить послание")
async def send_cmd(m: Message, state: FSMContext):
    await state.clear()
    await m.answer("📬 Теперь можно отправить послание любому человеку, даже если его нет в боте.\n\n"
                   "👇 Выбери, кому отправить анонимное сообщение 👇",
                   reply_markup=pick_user_kb())
 
 
@router.message(F.text == "⬅️ Назад")
async def back(m: Message, state: FSMContext):
    await state.clear()
    await m.answer("Главное меню", reply_markup=main_kb())
 
 
@router.message(F.users_shared)
async def user_picked(m: Message, state: FSMContext, bot: Bot):
    target = m.users_shared.users[0].user_id
    if await user_exists(target):
        await state.set_state(St.sending)
        await state.update_data(target=target)
        return await m.answer("✍️ Напиши анонимное сообщение:", reply_markup=main_kb())
    # человека нет в боте — даём приглашение
    await m.answer(
        "😕 Этого человека ещё нет в боте, я не могу написать ему первым.\n"
        f"Перешли ему приглашение: https://t.me/{BOT_USERNAME}\n"
        "Как только он запустит бота — сможешь отправить послание.",
        reply_markup=main_kb())
 
 
@router.message(Command("premium"))
async def premium(m: Message):
    if await is_premium(m.from_user.id):
        return await m.answer("💎 У тебя активен Премиум-статус!\n\n"
                              "💌 Ты видишь, кто отправляет послания\n"
                              "💬 Ответы без ограничений")
    await m.answer("💎 Премиум-статус даёт новые возможности:\n\n"
                   "💌 Знать имена, кто отправляет послания\n"
                   "💬 Ответы без ограничений")
    # сюда можно прикрутить оплату через Telegram Stars (send_invoice, currency="XTR")
 
 
@router.message(Command("info"))
async def info(m: Message):
    await m.answer("ℹ️ Информация\n\n"
                   "💌 В этом боте можно получать анонимные послания. "
                   "Вам пишут, а имя отправителя скрывается ✨")
 
 
# ---------- доставка сообщений ----------
async def deliver(bot: Bot, m: Message, target: int, title: str):
    """Отправляет сообщение m пользователю target как анонимку/ответ.
    Если target в премиуме, добавляет данные отправителя."""
    async with aiosqlite.connect(DB) as db:
        cur = await db.execute("INSERT INTO msgs(from_id, to_id) VALUES(?,?)", (m.from_user.id, target))
        mid = cur.lastrowid
        await db.commit()
 
    header = title
    if await is_premium(target):
        u = m.from_user
        uname = f"@{u.username}" if u.username else "нет юзернейма"
        header += f"\n\n👤 Отправитель: {u.full_name} ({uname})\n🆔 {u.id}"
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="↩️ Ответить", callback_data=f"reply:{mid}")]])
 
    await bot.send_message(target, header)
    await bot.copy_message(target, m.chat.id, m.message_id, reply_markup=kb)
 
 
# ---------- отправка анонимки ----------
@router.message(St.sending)
async def do_send(m: Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    target = data["target"]
    try:
        await deliver(bot, m, target, "💌 Новое анонимное послание:")
        await m.answer("✅ Послание отправлено!", reply_markup=main_kb())
    except Exception:
        await m.answer("❌ Не удалось доставить (человек заблокировал бота).", reply_markup=main_kb())
    await state.clear()
 
 
# ---------- ответ на анонимку ----------
@router.callback_query(F.data.startswith("reply:"))
async def reply_cb(c: CallbackQuery, state: FSMContext):
    mid = int(c.data.split(":")[1])
    async with aiosqlite.connect(DB) as db:
        cur = await db.execute("SELECT to_id, replies FROM msgs WHERE id=?", (mid,))
        row = await cur.fetchone()
    if not row or row[0] != c.from_user.id:
        return await c.answer("Недоступно", show_alert=True)
    if row[1] >= 1 and not await is_premium(c.from_user.id):
        return await c.answer("💎 Ответы без ограничений — только в Премиуме (/premium)", show_alert=True)
    await state.set_state(St.replying)
    await state.update_data(mid=mid)
    await c.message.answer("✍️ Напиши ответ (он тоже будет анонимным):")
    await c.answer()
 
 
@router.message(St.replying)
async def do_reply(m: Message, state: FSMContext, bot: Bot):
    mid = (await state.get_data())["mid"]
    async with aiosqlite.connect(DB) as db:
        cur = await db.execute("SELECT from_id FROM msgs WHERE id=?", (mid,))
        row = await cur.fetchone()
        await db.execute("UPDATE msgs SET replies=replies+1 WHERE id=?", (mid,))
        await db.commit()
    try:
        await deliver(bot, m, row[0], "💬 Тебе ответили на послание:")
        await m.answer("✅ Ответ отправлен!", reply_markup=main_kb())
    except Exception:
        await m.answer("❌ Не удалось доставить ответ.", reply_markup=main_kb())
    await state.clear()
 
 
async def main():
    await init_db()
    bot = Bot(TOKEN)
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(router)
    await dp.start_polling(bot)
 
 
if __name__ == "__main__":
    asyncio.run(main())

