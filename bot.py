import logging
import sqlite3
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)
import os

logging.basicConfig(level=logging.INFO)

TOKEN = os.environ.get("BOT_TOKEN")

# ادمین‌ها اینجا شناسه‌شون رو اضافه کن
ADMINS = [1797890079]  # <-- به جای این عدد شناسه تلگرام خودت رو بزار

DB = "store.db"
conn = sqlite3.connect(DB, check_same_thread=False)
c = conn.cursor()
c.execute("""
CREATE TABLE IF NOT EXISTS products (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT,
    description TEXT,
    price INTEGER
)
""")
conn.commit()

# مراحل گفت‌وگو برای افزودن محصول
NAME, DESCRIPTION, PRICE = range(3)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[InlineKeyboardButton("🛍 مشاهده محصولات", callback_data="show_products")]]
    await update.message.reply_text(
        "سلام! به فروشگاه *Elphone Store Accessories* خوش آمدید.",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )

async def is_admin(user_id):
    return user_id in ADMINS

# --- مدیریت ---

async def admin_only(func):
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        if await is_admin(user_id):
            return await func(update, context)
        else:
            await update.message.reply_text("⚠️ شما ادمین نیستید و اجازه دسترسی به این بخش را ندارید.")
            return ConversationHandler.END
    return wrapper

# شروع افزودن محصول
@admin_only
async def add_product_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("لطفا نام محصول را وارد کنید:")
    return NAME

async def add_product_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['name'] = update.message.text
    await update.message.reply_text("توضیحات محصول را وارد کنید:")
    return DESCRIPTION

async def add_product_description(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['description'] = update.message.text
    await update.message.reply_text("قیمت محصول را به تومان وارد کنید:")
    return PRICE

async def add_product_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    price_text = update.message.text
    if not price_text.isdigit():
        await update.message.reply_text("قیمت باید یک عدد صحیح باشد. لطفا دوباره وارد کنید:")
        return PRICE
    context.user_data['price'] = int(price_text)

    c.execute(
        "INSERT INTO products (name, description, price) VALUES (?, ?, ?)",
        (context.user_data['name'], context.user_data['description'], context.user_data['price']),
    )
    conn.commit()
    await update.message.reply_text("✅ محصول با موفقیت اضافه شد.")
    return ConversationHandler.END

# لغو عملیات
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("عملیات لغو شد.")
    return ConversationHandler.END

# لیست محصولات با دکمه حذف برای ادمین
@admin_only
async def list_products(update: Update, context: ContextTypes.DEFAULT_TYPE):
    c.execute("SELECT id, name, price FROM products")
    rows = c.fetchall()
    if not rows:
        await update.message.reply_text("هیچ محصولی ثبت نشده.")
        return

    keyboard = []
    text = "📦 لیست محصولات:

"
    for prod_id, name, price in rows:
        text += f"{name} — {price} تومان
"
        keyboard.append([InlineKeyboardButton(f"❌ حذف {name}", callback_data=f"delete_{prod_id}")])

    await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

# هندلر حذف محصول
@admin_only
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "show_products":
        c.execute("SELECT name, price FROM products")
        rows = c.fetchall()
        if not rows:
            await query.edit_message_text("هیچ محصولی ثبت نشده.")
        else:
            text = "📦 لیست محصولات:

"
            for name, price in rows:
                text += f"{name} — {price} تومان
"
            await query.edit_message_text(text)

    elif data.startswith("delete_"):
        prod_id = int(data.split("_")[1])
        c.execute("DELETE FROM products WHERE id=?", (prod_id,))
        conn.commit()
        await query.edit_message_text("محصول با موفقیت حذف شد.")
    else:
        await query.edit_message_text("دستور نامشخص")

def main():
    app = ApplicationBuilder().token(TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("addproduct", add_product_start)],
        states={
            NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_product_name)],
            DESCRIPTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_product_description)],
            PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_product_price)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("listproducts", list_products))
    app.add_handler(conv_handler)
    app.add_handler(CallbackQueryHandler(button_handler))
    app.run_polling()

if __name__ == "__main__":
    main()
