import logging
import random
import sqlite3
from threading import Thread
from flask import Flask
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

# --- Flask Server Setup for Render (24/7 Uptime) ---
app = Flask('')

@app.route('/')
def home():
    return "Bot is running! / ቦቱ በትክክል እየሰራ ነው!"

def run():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run)
    t.start()


# ሎጊንግ ማስተካከል
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- የአድሚን ቴሌግራም ቻት ID እዚህ ያስገቡ ---
ADMIN_CHAT_ID = 702970025

# ==========================================
# 1. ዳታቤዝ ማዋቀር (SQLite Database Setup)
# ==========================================
def init_db():
    conn = sqlite3.connect("shoe_shop.db")
    cursor = conn.cursor()
    
    # የምርቶች ሠንጠረዥ
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
    
    # የትዕዛዞች ሠንጠረዥ
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
    LANG_SELECT,
    MENU,
    GALLERY,
    SELECT_SIZE,
    SELECT_QTY,
    GET_PHONE,
    GET_ADDRESS,
    SELECT_PAYMENT,
    GET_RECEIPT,
) = range(9)


# ==========================================
# 2. /start እና የቋንቋ ምርጫ
# ==========================================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    keyboard = [
        [
            InlineKeyboardButton("🇪🇹 አማርኛ", callback_data="lang_am"),
            InlineKeyboardButton("🇬🇧 English", callback_data="lang_en"),
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    text = "እባክዎን የሚፈልጉትን ቋንቋ ይምረጡ፦\nPlease choose your language:"

    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.message.reply_text(text, reply_markup=reply_markup)
    else:
        await update.message.reply_text(text, reply_markup=reply_markup)

    return LANG_SELECT


async def set_language(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    
    lang = "am" if query.data == "lang_am" else "en"
    context.user_data["lang"] = lang

    user = update.effective_user
    
    if lang == "am":
        welcome_text = (
            f"ሰላም {user.first_name}! 👋✨\n"
            "እንኳን ወደ ጫማ ሱቃችን በደህና መጡ! 👟\n\n"
            "የእርስዎን ስታይል የሚገልጹ ጥራት ያላቸው ጫማዎችን በጥሩ ዋጋ ያግኙ።\n"
            "ከታች ካሉት አማራጮች አንዱን ይምረጡ፦"
        )
        keyboard = [
            [InlineKeyboardButton("👟 ጫማዎችን ይመልከቱ", callback_data="view_shoes")],
            [InlineKeyboardButton("📐 የሳይዝ መለኪያ መመሪያ", callback_data="size_guide")],
            [InlineKeyboardButton("⭐️ የደንበኞች ምስክርነት", callback_data="reviews")],
            [InlineKeyboardButton("📍 አድራሻ እና ስልክ", callback_data="location")],
        ]
    else:
        welcome_text = (
            f"Hello {user.first_name}! 👋✨\n"
            "Welcome to our Online Shoe Store! 👟\n\n"
            "Find high quality shoes at the best price.\n"
            "Please choose an option below:"
        )
        keyboard = [
            [InlineKeyboardButton("👟 View Shoes", callback_data="view_shoes")],
            [InlineKeyboardButton("📐 Size Guide", callback_data="size_guide")],
            [InlineKeyboardButton("⭐️ Customer Reviews", callback_data="reviews")],
            [InlineKeyboardButton("📍 Address & Phone", callback_data="location")],
        ]

    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.message.edit_text(text=welcome_text, reply_markup=reply_markup)
    return MENU


# ==========================================
# 3. ዋና ሜኑ (Main Menu)
# ==========================================
async def main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    lang = context.user_data.get("lang", "am")
    user = update.effective_user

    if lang == "am":
        welcome_text = f"ሰላም {user.first_name}! ወደ ዋናው ሜኑ ተመልሰዋል። ከታች ካሉት አማራጮች ይምረጡ፦"
        keyboard = [
            [InlineKeyboardButton("👟 ጫማዎችን ይመልከቱ", callback_data="view_shoes")],
            [InlineKeyboardButton("📐 የሳይዝ መለኪያ መመሪያ", callback_data="size_guide")],
            [InlineKeyboardButton("⭐️ የደንበኞች ምስክርነት", callback_data="reviews")],
            [InlineKeyboardButton("📍 አድራሻ እና ስልክ", callback_data="location")],
        ]
    else:
        welcome_text = f"Hello {user.first_name}! You are back to the main menu. Choose an option:"
        keyboard = [
            [InlineKeyboardButton("👟 View Shoes", callback_data="view_shoes")],
            [InlineKeyboardButton("📐 Size Guide", callback_data="size_guide")],
            [InlineKeyboardButton("⭐️ Customer Reviews", callback_data="reviews")],
            [InlineKeyboardButton("📍 Address & Phone", callback_data="location")],
        ]

    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.message.edit_text(text=welcome_text, reply_markup=reply_markup)
    return MENU


# ==========================================
# 4. የጫማ ማሳያ ጋለሪ (Gallery & Pagination)
# ==========================================
async def view_shoes(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    lang = context.user_data.get("lang", "am")

    if "product_index" not in context.user_data:
        context.user_data["product_index"] = 0

    conn = sqlite3.connect("shoe_shop.db")
    cursor = conn.cursor()
    cursor.execute("SELECT product_id, name, price FROM products")
    products = cursor.fetchall()
    conn.close()

    if not products:
        msg = "እቃ አልተገኘም!" if lang == "am" else "No products found!"
        await query.message.reply_text(msg)
        return MENU

    idx = context.user_data["product_index"] % len(products)
    p_id, name, price = products[idx]
    context.user_data["current_product_id"] = p_id

    if lang == "am":
        text = (
            f"👟 <b>{name}</b>\n\n"
            f"💵 <b>ዋጋ፦</b> {price} ETB\n"
            f"🎨 <b>ቀለም:</b> ጥራት ያለው\n"
            f"🆔 <b>የምርት መለያ:</b> {p_id}\n\n"
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
    else:
        text = (
            f"👟 <b>{name}</b>\n\n"
            f"💵 <b>Price:</b> {price} ETB\n"
            f"🎨 <b>Quality:</b> Premium Quality\n"
            f"🆔 <b>Product Code:</b> {p_id}\n\n"
            f"Item ({idx + 1}/{len(products)})"
        )
        keyboard = [
            [InlineKeyboardButton("🛒 Order Now", callback_data="order_now")],
            [
                InlineKeyboardButton("⬅️ Prev", callback_data="prev_product"),
                InlineKeyboardButton("Next ➡️", callback_data="next_product")
            ],
            [InlineKeyboardButton("🔙 Back to Menu", callback_data="back_to_menu")],
        ]

    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.message.edit_text(text=text, parse_mode="HTML", reply_markup=reply_markup)
    return GALLERY


async def navigate_products(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    
    if query.data == "next_product":
        context.user_data["product_index"] += 1
    elif query.data == "prev_product":
        context.user_data["product_index"] -= 1
        
    return await view_shoes(update, context)


# ==========================================
# 5. ሳይዝ እና ብዛት መምረጫ
# ==========================================
async def select_size(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    lang = context.user_data.get("lang", "am")

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
        if lang == "am":
            btn_text = f"ሳይዝ {size} (አለ)" if qty > 0 else f"ሳይዝ {size} (አልቋል ❌)"
        else:
            btn_text = f"Size {size} (Available)" if qty > 0 else f"Size {size} (Sold Out ❌)"
            
        callback_data = f"size_{size}" if qty > 0 else "sold_out"
        row.append(InlineKeyboardButton(btn_text, callback_data=callback_data))
        if len(row) == 3:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)

    back_btn_text = "🔙 ተመለስ" if lang == "am" else "🔙 Back"
    keyboard.append([InlineKeyboardButton(back_btn_text, callback_data="view_shoes")])
    reply_markup = InlineKeyboardMarkup(keyboard)

    prompt_text = "እባክዎን የሚፈልጉትን <b>የጫማ ሳይዝ</b> ይምረጡ፦" if lang == "am" else "Please select your <b>Shoe Size</b>:"
    await query.message.reply_text(prompt_text, parse_mode="HTML", reply_markup=reply_markup)
    return SELECT_SIZE


async def select_quantity(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    lang = context.user_data.get("lang", "am")
    
    if query.data == "sold_out":
        alert_text = "ይህ ሳይዝ አልቋል! ሌላ ሳይዝ ይምረጡ።" if lang == "am" else "This size is sold out! Please choose another."
        await query.answer(alert_text, show_alert=True)
        return SELECT_SIZE

    size = int(query.data.split("_")[1])
    context.user_data["selected_size"] = size

    if lang == "am":
        keyboard = [[InlineKeyboardButton("1 ጥንድ", callback_data="qty_1"), InlineKeyboardButton("2 ጥንድ", callback_data="qty_2"), InlineKeyboardButton("3+ ጥንድ", callback_data="qty_3")]]
        text = f"መረጡት ሳይዝ፦ <b>{size}</b>\nስንት ጥንድ መገዛት ይፈልጋሉ?"
    else:
        keyboard = [[InlineKeyboardButton("1 Pair", callback_data="qty_1"), InlineKeyboardButton("2 Pairs", callback_data="qty_2"), InlineKeyboardButton("3+ Pairs", callback_data="qty_3")]]
        text = f"Selected Size: <b>{size}</b>\nHow many pairs would you like to buy?"

    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.message.reply_text(text, parse_mode="HTML", reply_markup=reply_markup)
    return SELECT_QTY


# ==========================================
# 6. ስልክ እና አድራሻ መጠየቂያ
# ==========================================
async def request_phone(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    lang = context.user_data.get("lang", "am")
    qty = int(query.data.split("_")[1])
    context.user_data["selected_qty"] = qty

    btn_text = "📱 ስልክ ቁጥር አጋራ" if lang == "am" else "📱 Share Phone Number"
    contact_button = KeyboardButton(text=btn_text, request_contact=True)
    reply_markup = ReplyKeyboardMarkup([[contact_button]], one_time_keyboard=True, resize_keyboard=True)

    text = "ትዕዛዝዎን ለመከታተል እባክዎን ስልክ ቁጥርዎን ያጋሩን፦" if lang == "am" else "Please share your phone number to track your order:"
    await query.message.reply_text(text, reply_markup=reply_markup)
    return GET_PHONE


async def get_address(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    lang = context.user_data.get("lang", "am")
    contact = update.message.contact
    if contact:
        context.user_data["phone"] = contact.phone_number
    else:
        context.user_data["phone"] = update.message.text

    text = "📍 ጫማው የሚላክበትን <b>አድራሻ/ሰፈር</b> በጽሁፍ ይላኩልን (ለምሳሌ፦ ቦሌ)፦" if lang == "am" else "📍 Please send your delivery <b>Address/Location</b> in text (e.g., Bole):"
    await update.message.reply_text(text, parse_mode="HTML", reply_markup=ReplyKeyboardRemove())
    return GET_ADDRESS


# ==========================================
# 7. ክፍያ እና ደረሰኝ
# ==========================================
async def select_payment(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    lang = context.user_data.get("lang", "am")
    context.user_data["address"] = update.message.text

    keyboard = [
        [
            InlineKeyboardButton("📱 Telebirr", callback_data="pay_telebirr"),
            InlineKeyboardButton("🏦 CBE (ንግድ ባንክ)" if lang == "am" else "🏦 CBE (Bank)", callback_data="pay_cbe"),
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    text = "💳 ክፍያ የሚፈጽሙበትን አማራጭ ይምረጡ፦" if lang == "am" else "💳 Please select your payment method:"
    await update.message.reply_text(text, reply_markup=reply_markup)
    return SELECT_PAYMENT


async def request_receipt(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    lang = context.user_data.get("lang", "am")
    payment_method = query.data

    if payment_method == "pay_telebirr":
        pay_info = "📱 <b>Telebirr ቁጥር፦</b> 0953618630\n👤 <b>ስም፦</b> አበበ አለሙ" if lang == "am" else "📱 <b>Telebirr Number:</b> 0953618630\n👤 <b>Name:</b> Abebe Alemu"
    else:
        pay_info = "🏦 <b>ንግድ ባንክ (CBE)፦</b> 1000XXXXXXXXX\n👤 <b>ስም፦</b> አበበ አለሙ" if lang == "am" else "🏦 <b>CBE Account:</b> 1000XXXXXXXXX\n👤 <b>Name:</b> Abebe Alemu"

    if lang == "am":
        text = f"የክፍያ መረጃ፦\n{pay_info}\n\n🧾 <b>መጨረሻ፦</b> ክፍያ ከፈጸሙ በኋላ <b>የደረሰኙን ፎቶ (Screenshot)</b> እዚህ ይላኩልን።"
    else:
        text = f"Payment Details:\n{pay_info}\n\n🧾 <b>Final Step:</b> After payment, please send the <b>Payment Receipt (Screenshot)</b> here."

    await query.message.reply_text(text, parse_mode="HTML")
    return GET_RECEIPT


# ==========================================
# 8. ትዕዛዝ ማረጋገጫ
# ==========================================
async def confirm_order(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.effective_user
    lang = context.user_data.get("lang", "am")
    photo_file = update.message.photo[-1].file_id

    order_id = f"#SH-{random.randint(1000, 9999)}"
    product_id = context.user_data.get("current_product_id", "#SH-102")
    size = context.user_data.get("selected_size")
    qty = context.user_data.get("selected_qty")
    phone = context.user_data.get("phone")
    address = context.user_data.get("address")

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

    if lang == "am":
        confirmation_text = (
            f"እናመሰግናለን <b>{user.first_name}</b>! 👟🙏\n"
            f"የክፍያ ደረሰኝዎ ደርሶናል።\n\n"
            f"🆔 <b>የትዕዛዝ መለያ ቁጥር:</b> {order_id}\n"
            "⏳ <b>ሂደት፦</b> አረጋግጠን በ <b>15-30 ደቂቃ</b> ውስጥ እናደርሳለን።"
        )
        menu_btn = "🏠 ወደ ዋና ሜኑ መመለስ"
    else:
        confirmation_text = (
            f"Thank you <b>{user.first_name}</b>! 👟🙏\n"
            f"We have received your payment receipt.\n\n"
            f"🆔 <b>Order ID:</b> {order_id}\n"
            "⏳ <b>Status:</b> We will verify and deliver within <b>15-30 minutes</b>."
        )
        menu_btn = "🏠 Back to Main Menu"

    keyboard = [[InlineKeyboardButton(menu_btn, callback_data="back_to_menu")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(confirmation_text, parse_mode="HTML", reply_markup=reply_markup)
    return MENU


# ==========================================
# 9. አድሚን ክትትል እና ተጨማሪ ገጾች
# ==========================================
async def handle_admin_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    data = query.data
    parts = data.split("_")
    action = parts[1]
    order_id = f"#SH-{parts[2]}"

    conn = sqlite3.connect("shoe_shop.db")
    cursor = conn.cursor()
    cursor.execute("SELECT user_id, product_id, size, qty FROM orders WHERE order_id = ?", (order_id,))
    order_data = cursor.fetchone()

    if order_data:
        user_id, product_id, size, qty = order_data

        if action == "approve":
            cursor.execute("UPDATE orders SET status = 'Approved' WHERE order_id = ?", (order_id,))
            stock_col = f"stock_{size}"
            cursor.execute(f"UPDATE products SET {stock_col} = {stock_col} - ? WHERE product_id = ?", (qty, product_id))
            conn.commit()

            await context.bot.send_message(chat_id=user_id, text=f"✅ <b>መልካም ዜና!</b> ትዕዛዝዎ ({order_id}) ጸድቋል፣ እቃዎ በመንገድ ላይ ነው! 🚚", parse_mode="HTML")
            await query.edit_message_caption(caption=query.message.caption + "\n\n<b>[✅ STATUS: APPROVED]</b>", parse_mode="HTML")
        elif action == "cancel":
            cursor.execute("UPDATE orders SET status = 'Cancelled' WHERE order_id = ?", (order_id,))
            conn.commit()

            await context.bot.send_message(chat_id=user_id, text=f"❌ ይቅርታ፣ ትዕዛዝዎ ({order_id}) ተሰርዟል።", parse_mode="HTML")
            await query.edit_message_caption(caption=query.message.caption + "\n\n<b>[❌ STATUS: CANCELLED]</b>", parse_mode="HTML")
    conn.close()


async def size_guide(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    lang = context.user_data.get("lang", "am")
    
    if lang == "am":
        text = "📐 <b>ትክክለኛ የጫማ ሳይዝ መመሪያ፦</b>\n• 40 Size: 25 cm\n• 41 Size: 26 cm\n• 42 Size: 26.5 cm"
        btn = "🔙 ወደ ዋና ሜኑ"
    else:
        text = "📐 <b>Shoe Size Guide:</b>\n• Size 40: 25 cm\n• Size 41: 26 cm\n• Size 42: 26.5 cm"
        btn = "🔙 Back to Menu"

    keyboard = [[InlineKeyboardButton(btn, callback_data="back_to_menu")]]
    await query.message.reply_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(keyboard))
    return MENU


async def shop_location(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    lang = context.user_data.get("lang", "am")

    if lang == "am":
        text = "📍 <b>የሱቁ አድራሻ፦</b>\n🏢 አዲስ አበባ፣ 22\n📞 ስልክ፦ 0953618630"
        btn = "🔙 ወደ ዋና ሜኑ"
    else:
        text = "📍 <b>Store Location:</b>\n🏢 Addis Ababa, 22\n📞 Phone: 0953618630"
        btn = "🔙 Back to Menu"

    keyboard = [[InlineKeyboardButton(btn, callback_data="back_to_menu")]]
    await query.message.reply_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(keyboard))
    return MENU


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("ግዢው ተሰርዟል። /start በመጫን እንደገና ይጀምሩ።")
    return ConversationHandler.END


# ==========================================
# 10. ዋና ማስኬጃ (Main)
# ==========================================
def main():
    keep_alive()
    init_db()

    TOKEN = 
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
            LANG_SELECT: [
                CallbackQueryHandler(set_language, pattern="^lang_")
            ],
            MENU: [
                CallbackQueryHandler(view_shoes, pattern="^view_shoes$"),
                CallbackQueryHandler(size_guide, pattern="^size_guide$"),
                CallbackQueryHandler(shop_location, pattern="^location$"),
                CallbackQueryHandler(main_menu, pattern="^back_to_menu$"),
            ],
            GALLERY: [
                CallbackQueryHandler(select_size, pattern="^order_now$"),
                CallbackQueryHandler(navigate_products, pattern="^(next|prev)_product$"),
                CallbackQueryHandler(main_menu, pattern="^back_to_menu$"),
            ],
            SELECT_SIZE: [
                CallbackQueryHandler(select_quantity, pattern="^size_"),
                CallbackQueryHandler(select_quantity, pattern="^sold_out$"),
                CallbackQueryHandler(view_shoes, pattern="^view_shoes$"),
            ],
            SELECT_QTY: [CallbackQueryHandler(request_phone, pattern="^qty_")],
            GET_PHONE: [MessageHandler(filters.CONTACT | filters.TEXT & ~filters.COMMAND, get_address)],
            GET_ADDRESS: [MessageHandler(filters.TEXT & ~filters.COMMAND, select_payment)],
            SELECT_PAYMENT: [CallbackQueryHandler(request_receipt, pattern="^pay_")],
            GET_RECEIPT: [MessageHandler(filters.PHOTO, confirm_order)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        per_message=False,
    )

    application.add_handler(conv_handler)
    application.add_handler(CallbackQueryHandler(handle_admin_action, pattern="^adm_"))

    application.run_polling()


if __name__ == "__main__":
    main()
