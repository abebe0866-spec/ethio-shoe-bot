import logging
import random
import sqlite3
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
)
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ConversationHandler,
    ContextTypes,
    filters,
)

# ሎጊንግ ማስተካከል
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- የአድሚን ቴሌግራም ቻት ID እዚህ ያስገቡ ---
ADMIN_CHAT_ID =   702970025

# ==========================================
# 1. ቋሚ ዳታቤዝ (SQLite Database Setup)
# ==========================================
def init_db():
    conn = sqlite3.connect("shoe_shop.db")
    cursor = conn.cursor()
    
    # የምርቶች ሠንጠረዥ (Products Table)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS products (
            product_id TEXT PRIMARY KEY,
            name TEXT,
            price REAL,
            photo TEXT,
            stock_40 INTEGER,
            stock_41 INTEGER,
            stock_42 INTEGER,
            stock_43 INTEGER,
            stock_44 INTEGER
        )
    """)
    
    # የትዕዛዞች ሠንጠረዥ (Orders Table)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            order_id TEXT PRIMARY KEY,
            user_id INTEGER,
            username TEXT,
            first_name TEXT,
            phone TEXT,
            address TEXT,
            product_id TEXT,
            size INTEGER,
            qty INTEGER,
            status TEXT
        )
    """)
    
    # የመጀመሪያ ናሙና ጫማዎችን መሙላት (ካለፉ አልተጻፉም)
    sample_products = [
        ("#SH-102", "Nike Air Jordan 4 Retro", 3900, "", 2, 3, 1, 4, 2),
        ("#SH-103", "Adidas Yeezy Boost 350", 4500, "", 1, 2, 2, 3, 0),
        ("#SH-104", "Nike Air Force 1 White", 3500, "", 4, 0, 3, 2, 1)
    ]
    cursor.executemany("INSERT OR IGNORE INTO products VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", sample_products)
    conn.commit()
    conn.close()

# የውይይት ደረጃዎች (Conversation States)
(
    MENU,
    GALLERY,
    SELECT_SIZE,
    SELECT_QTY,
    GET_PHONE,
    GET_ADDRESS,
    SELECT_PAYMENT,
    GET_RECEIPT,
) = range(8)


# 1. /start ትዕዛዝ እና ዋናው ሜኑ (Step 1)
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.effective_user
    welcome_text = (
        f"ሰላም {user.first_name}! 👋✨\n"
        "እንኳን ወደ [የጫማ ብራንዱ ስም] የመስመር ላይ ሱቅ በደህና መጡ! 👟\n\n"
        "የእርስዎን ስታይል የሚገልጹ ጥራት ያላቸው ጫማዎችን በጥሩ ዋጋ ያግኙ።\n"
        "ከታች ካሉት አማራጮች አንዱን ይምረጡ፦"
    )

    keyboard = [
        [InlineKeyboardButton("👟 ጫማዎችን ይመልከቱ", callback_data="view_shoes")],
        [InlineKeyboardButton("📐 የሳይዝ መለኪያ Guide", callback_data="size_guide")],
        [InlineKeyboardButton("⭐️ የደንበኞች ምስክርነት", callback_data="reviews")],
        [InlineKeyboardButton("📍 አድራሻ እና ስልክ", callback_data="location")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    if update.callback_query:
        await update.callback_query.answer()
        # መልእክት ሳያጠፋ አዲስ መልእክት ይልካል
        await update.callback_query.message.reply_text(welcome_text, reply_markup=reply_markup)
    else:
        await update.message.reply_text(welcome_text, reply_markup=reply_markup)

    return MENU



# ==========================================
# 2. የጫማ ማሳያ ጋለሪ እና ፔጂኔሽን (Pagination - Next/Prev)
# ==========================================
async def view_shoes(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    if "product_index" not in context.user_data:
        context.user_data["product_index"] = 0

    conn = sqlite3.connect("shoe_shop.db")
    cursor = conn.cursor()
    cursor.execute("SELECT product_id, name, price FROM products")
    products = cursor.fetchall()
    conn.close()

    if not products:
        await query.message.reply_text("እቃ አልተገኘም!")
        return MENU

    idx = context.user_data["product_index"] % len(products)
    p_id, name, price = products[idx]
    context.user_data["current_product_id"] = p_id

    text = (
        f"👟 <b>{name}</b>\n\n"
        f"💵 <b>ዋጋ፦</b> {price} ETB\n"
        f"🎨 <b>Color:</b> Premium Quality\n"
        f"🆔 <b>Product Code:</b> {p_id}\n\n"
        f"ምርት ({idx + 1}/{len(products)})"
    )

    keyboard = [
        [InlineKeyboardButton("🛒 አሁኑኑ ይዘዙ", callback_data="order_now")],
        [
            InlineKeyboardButton("⬅️ ቀድሞ", callback_data="prev_product"),
            InlineKeyboardButton("ቀጣይ ➡️", callback_data="next_product")
        ],
        [InlineKeyboardButton("🔙 ወደ ዋና ሜኑ", callback_data="back_to_menu")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.message.edit_text(
        text=text,
        parse_mode="HTML",
        reply_markup=reply_markup,
    )
    return GALLERY


# የምርት መቀየሪያ (Next/Prev handlers)
async def navigate_products(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    
    if query.data == "next_product":
        context.user_data["product_index"] += 1
    elif query.data == "prev_product":
        context.user_data["product_index"] -= 1
        
    return await view_shoes(update, context)


# ==========================================
# 3. ሳይዝ መምረጫ እና ከዳታቤዝ ስቶክ ማንበብ
# ==========================================
async def select_size(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    product_id = context.user_data.get("current_product_id", "#SH-102")
    
    conn = sqlite3.connect("shoe_shop.db")
    cursor = conn.cursor()
    cursor.execute("SELECT stock_40, stock_41, stock_42, stock_43, stock_44 FROM products WHERE product_id = ?", (product_id,))
    stock_row = cursor.fetchone()
    conn.close()

    sizes = [40, 41, 42, 43, 44]
    stock_dict = dict(zip(sizes, stock_row))

    keyboard = []
    row = []
    for size, qty in stock_dict.items():
        if qty > 0:
            btn_text = f"{size} (አለ)"
            callback_data = f"size_{size}"
        else:
            btn_text = f"{size} (አልቀዋል ❌)"
            callback_data = f"sold_out"   
        
        row.append(InlineKeyboardButton(btn_text, callback_data=callback_data))
        if len(row) == 3:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)

    keyboard.append([InlineKeyboardButton("🔙 ተመለስ", callback_data="view_shoes")])
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.message.reply_text(
        "እባክዎን የሚፈልጉትን <b>የጫማ ሳይዝ (Size)</b> ይምረጡ፦",
        parse_mode="HTML",
        reply_markup=reply_markup,
    )
    return SELECT_SIZE


# 4. ብዛት መምረጫ (Step 3 - Part B)
async def select_quantity(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    
    if query.data == "sold_out":
        await query.answer("ይህ ሳይዝ አልቋል! እባክዎን ሌላ ሳይዝ ይምረጡ።", show_alert=True)
        return SELECT_SIZE

    size = int(query.data.split("_")[1])
    context.user_data["selected_size"] = size

    keyboard = [
        [
            InlineKeyboardButton("1 ጥንድ", callback_data="qty_1"),
            InlineKeyboardButton("2 ጥንድ", callback_data="qty_2"),
            InlineKeyboardButton("3+ ጥንድ", callback_data="qty_3"),
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.message.reply_text(
        f"መረጡት ሳይዝ፦ <b>{size}</b>\nስንት ጥንድ መገዛት ይፈልጋሉ?",
        parse_mode="HTML",
        reply_markup=reply_markup,
    )
    return SELECT_QTY


# 5. ስልክ ቁጥር መጠየቂያ (Step 4 - Form 1)
async def request_phone(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    qty = int(query.data.split("_")[1])
    context.user_data["selected_qty"] = qty

    contact_button = KeyboardButton(
        text="📱 ስልክ ቁጥር አጋራ (Share Contact)", request_contact=True
    )
    reply_markup = ReplyKeyboardMarkup(
        [[contact_button]], one_time_keyboard=True, resize_keyboard=True
    )

    await query.message.reply_text(
        "ትዕዛዝዎን ለመከታተል እባክዎን ከታች ያለውን አዝራር በመጫን ስልክ ቁጥርዎን ያጋሩን፦",
        reply_markup=reply_markup,
    )
    return GET_PHONE


# 6. አድራሻ መጠየቂያ (Step 4 - Form 2)
async def get_address(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    contact = update.message.contact
    if contact:
        context.user_data["phone"] = contact.phone_number
    else:
        context.user_data["phone"] = update.message.text

    await update.message.reply_text(
        "📍 ጫማው የሚላክበትን <b>አድራሻ/ሰፈር</b> በጽሁፍ ይላኩልን (ለምሳሌ፦ ቦሌ፣ መድኃኔዓለም ህንፃ አጠገብ)፦",
        parse_mode="HTML",
        reply_markup=ReplyKeyboardRemove(),
    )
    return GET_ADDRESS


# 7. የክፍያ አማራጭ መምረጫ (Step 4 - Form 3)
async def select_payment(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["address"] = update.message.text

    keyboard = [
        [
            InlineKeyboardButton("📱 Telebirr", callback_data="pay_telebirr"),
            InlineKeyboardButton("🏦 CBE (ንግድ ባንክ)", callback_data="pay_cbe"),
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        "💳 ክፍያ የሚፈጽሙበትን ባንክ/አማራጭ ይምረጡ፦", reply_markup=reply_markup
    )
    return SELECT_PAYMENT


# 8. የባንክ ዝርዝር ማሳያ እና የደረሰኝ ጥያቄ (Step 4 - Final)
async def request_receipt(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    payment_method = query.data

    if payment_method == "pay_telebirr":
        pay_info = (
            "📱 <b>Telebirr ቁጥር፦</b> 0953618630\n"
            "👤 <b>አበበ አለሙ፦</b> [የሱቁ ስም]\n"
            "💵 <b>መጠን፦</b> ክፍያውን ያስተካክሉ"
        )
    else:
        pay_info = (
            "🏦 <b>ንግድ ባንክ (CBE)፦</b> 1000XXXXXXXXX\n"
            "👤 <b>ስም፦</b> [የሱቁ ስም]\n"
            "💵 <b>መጠን፦</b> ክፍያውን ያስተካክሉ"
        )

    text = (
        f"ተጨማሪ መረጃ፦\n{pay_info}\n\n"
        "🧾 <b>መጨረሻ፦</b> ክፍያ ፈጽመው ሲጨርሱ <b>የደረሰኙን ፎቶ (Screenshot)</b> እዚህ ይላኩልን።"
    )
    await query.message.reply_text(text, parse_mode="HTML")
    return GET_RECEIPT


# ==========================================
# 9. የክፍያ ማረጋገጫ እና ትዕዛዝ በዳታቤዝ መመዝገብ
# ==========================================
async def confirm_order(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.effective_user
    photo_file = update.message.photo[-1].file_id

    order_id = f"#SH-{random.randint(1000, 9999)}"
    product_id = context.user_data.get("current_product_id", "#SH-102")
    size = context.user_data.get("selected_size")
    qty = context.user_data.get("selected_qty")
    phone = context.user_data.get("phone")
    address = context.user_data.get("address")

    # ትዕዛዙን በ SQLite ዳታቤዝ ውስጥ ማስቀመጥ (Permanent Storage)
    conn = sqlite3.connect("shoe_shop.db")
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO orders VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (order_id, user.id, user.username, user.first_name, phone, address, product_id, size, qty, "Pending"))
    conn.commit()
    conn.close()

    admin_text = (
        f"🚨 <b>አዲስ የጫማ ትዕዛዝ ደርሷል! ({order_id})</b>\n\n"
        f"👤 <b>ደንበኛ:</b> {user.full_name} (@{user.username if user.username else 'የለውም'})\n"
        f"📱 <b>ስልክ:</b> {phone}\n"
        f"📍 <b>አድራሻ:</b> {address}\n"
        f"🆔 <b>Product ID:</b> {product_id}\n"
        f"📏 <b>ሳይዝ:</b> {size} | 📦 <b>ብዛት:</b> {qty} ጥንድ"
    )

    admin_keyboard = [
        [
            InlineKeyboardButton("✅ ትዕዛዝ አረጋግጥ", callback_data=f"adm_approve_{order_id}"),
            InlineKeyboardButton("❌ ሰርዝ", callback_data=f"adm_cancel_{order_id}")
        ]
    ]
    admin_reply_markup = InlineKeyboardMarkup(admin_keyboard)

    try:
        await context.bot.send_photo(
            chat_id=ADMIN_CHAT_ID,
            photo=photo_file,
            caption=admin_text,
            parse_mode="HTML",
            reply_markup=admin_reply_markup
        )
    except Exception as e:
        logger.error(f"አድሚኑን ማሳወቅ አልተቻለም: {e}")

    confirmation_text = (
        f"እናመሰግናለን <b>{user.first_name}</b>! 👟🙏\n"
        f"የክፍያ ደረሰኝዎ ደርሶናል።\n\n"
        f"🆔 <b>የትዕዛዝ መለያ ቁጥር (Order ID):</b> {order_id}\n"
        "⏳ <b>ሂደት፦</b> የክፍያ መረጃዎን አረጋግጠን በ <b>15-30 ደቂቃ</b> ውስጥ እናደርሳለን።\n\n"
        "📞 ለተጨማሪ ጥያቄ፦ 0953-61-86-30"
    )

    keyboard = [[InlineKeyboardButton("🏠 ወደ ዋና ሜኑ መመለስ", callback_data="back_to_menu")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        confirmation_text, parse_mode="HTML", reply_markup=reply_markup
    )
    return MENU


# ==========================================
# 10. የአድሚን አዝራሮች እና ዳታቤዝ ስቶክ ማስተካከያ
# ==========================================
async def handle_admin_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    data = query.data
    parts = data.split("_")
    action = parts[1] # approve ወይም cancel
    order_id = f"#SH-{parts[2]}"

    conn = sqlite3.connect("shoe_shop.db")
    cursor = conn.cursor()
    
    # ትዕዛዙን ከዳታቤዝ መፈለግ
    cursor.execute("SELECT user_id, product_id, size, qty FROM orders WHERE order_id = ?", (order_id,))
    order_data = cursor.fetchone()

    if order_data:
        user_id, product_id, size, qty = order_data

        if action == "approve":
            cursor.execute("UPDATE orders SET status = 'Approved' WHERE order_id = ?", (order_id,))
            
            # ከስቶክ ላይ መቀነስ (Dynamic Stock Reduction in DB)
            stock_col = f"stock_{size}"
            cursor.execute(f"UPDATE products SET {stock_col} = {stock_col} - ? WHERE product_id = ?", (qty, product_id))
            conn.commit()

            await context.bot.send_message(
                chat_id=user_id,
                text=f"✅ <b>መልካም ዜና!</b> የክፍያ ደረሰኝዎ እና ትዕዛዝዎ ({order_id}) ጸድቋል። እቃዎ በጉዞ ላይ ነው! 🚚",
                parse_mode="HTML"
            )
            await query.edit_message_caption(
                caption=query.message.caption + "\n\n<b>[✅ STATUS: APPROVED]</b>",
                parse_mode="HTML"
            )
        elif action == "cancel":
            cursor.execute("UPDATE orders SET status = 'Cancelled' WHERE order_id = ?", (order_id,))
            conn.commit()

            await context.bot.send_message(
                chat_id=user_id,
                text=f"❌ ይቅርታ፣ የትዕዛዝዎ ክፍያ አለመረጋገጡን/እቃው ማልቁን ተከትሎ ትዕዛዝዎ ({order_id}) ተሰርዟል።",
                parse_mode="HTML"
            )
            await query.edit_message_caption(
                caption=query.message.caption + "\n\n<b>[❌ STATUS: CANCELLED]</b>",
                parse_mode="HTML"
            )
    conn.close()


# ተጨማሪ አጋዥ ገጾች (Size Guide, Location)
async def size_guide(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    text = "📐 <b>ትክክለኛ የጫማ ሳይዝዎን ለማወቅ፦</b>\n• 40 Size: 25 cm\n• 41 Size: 26 cm\n• 42 Size: 26.5 cm"
    keyboard = [[InlineKeyboardButton("🔙 ወደ ዋና ሜኑ", callback_data="back_to_menu")]]
    await query.message.reply_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(keyboard))
    return MENU

async def shop_location(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    text = (
        "📍 <b>የሱቁ አድራሻ፦</b>\n"
        "🏢 ቦታ፦ አዲስ አበባ፣ 22 ማዞሪያ፣ ሰንሻይን ህንፃ 1ኛ ፎቅ ሱቅ ቁጥር 12\n"
        "📞 ስልክ፦ 0953-61-86-30\n"
        "⏰ የስራ ሰዓት፦ ከሰኞ - እሁድ (ከጠዋቱ 2:30 እስከ ማታ 2:30)\n"
        "🚚 ዴሊቨሪ፦ አዲስ አበባ ውስጥ በራሳችን ሞተር ባሉበት ቦታ እናደርሳለን!"
    )

    keyboard = [[InlineKeyboardButton("🔙 ወደ ዋና ሜኑ", callback_data="back_to_menu")]]
    await query.message.reply_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(keyboard))
    return MENU


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("ግዢው ተሰርዟል። /start በመጫን እንደገና መጀመር ይችላሉ።")
    return ConversationHandler.END


def main():
    # ዳታቤዙን በጅምር ላይ ማዘጋጀት
    init_db()

    TOKEN = "8686401024:AAHR6jGeCvFuWwgDHlJGODnQ6qQS0IGA470"

    application = (
        Application.builder()
        .token(TOKEN)
        .connect_timeout(60.0)
        .read_timeout(60.0)
        .write_timeout(60.0)
        .build()
    )

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            MENU: [
                CallbackQueryHandler(view_shoes, pattern="^view_shoes$"),
                CallbackQueryHandler(size_guide, pattern="^size_guide$"),
                CallbackQueryHandler(shop_location, pattern="^location$"),
                CallbackQueryHandler(start, pattern="^back_to_menu$"),
            ],
            GALLERY: [
                CallbackQueryHandler(select_size, pattern="^order_now$"),
                CallbackQueryHandler(navigate_products, pattern="^(next|prev)_product$"),
                CallbackQueryHandler(start, pattern="^back_to_menu$"),
            ],
            SELECT_SIZE: [
                CallbackQueryHandler(select_quantity, pattern="^size_"),
                CallbackQueryHandler(select_quantity, pattern="^sold_out$"),
                CallbackQueryHandler(view_shoes, pattern="^view_shoes$"),
            ],
            SELECT_QTY: [CallbackQueryHandler(request_phone, pattern="^qty_")],
            GET_PHONE: [
                MessageHandler(filters.CONTACT | filters.TEXT & ~filters.COMMAND, get_address)
            ],
            GET_ADDRESS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, select_payment)
            ],
            SELECT_PAYMENT: [
                CallbackQueryHandler(request_receipt, pattern="^pay_")
            ],
            GET_RECEIPT: [
                MessageHandler(filters.PHOTO, confirm_order),
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        per_message=False,
    )

    application.add_handler(conv_handler)
    application.add_handler(CallbackQueryHandler(handle_admin_action, pattern="^adm_"))

    application.run_polling()


if __name__ == "__main__":
    main()
