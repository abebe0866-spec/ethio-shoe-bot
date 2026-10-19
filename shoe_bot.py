import os
import logging
import random
import sqlite3
import re
import json
from threading import Thread
from flask import Flask
import datetime
import gspread
from google.oauth2.service_account import Credentials
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
# 1. Google Sheets እና ዳታቤዝ ማዋቀር (Environment Variable ድጋፍ ያለው)
# ==========================================
scopes = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

try:
    google_creds_json = os.environ.get("GOOGLE_CREDENTIALS")
    if google_creds_json:
        creds_dict = json.loads(google_creds_json)
        creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
    else:
        creds = Credentials.from_service_account_file("credentials.json", scopes=scopes)
    
    gc = gspread.authorize(creds)
    spreadsheet = gc.open("Ethio_Shoe_Shop")
except Exception as e:
    logger.error(f"Google Sheet ማገናኘት አልተቻለም: {e}")
    spreadsheet = None

# -------------------------------------------------------------
# ሀ) የጫማዎች ካታሎግ መረጃን ከ "Products" ታብ ለማንበብ የሚረዳ ፋንክሽን
# -------------------------------------------------------------
def get_all_products():
    if spreadsheet:
        try:
            products_sheet = spreadsheet.worksheet("Products")
            all_products = products_sheet.get_all_records()
            if all_products:
                return all_products
        except Exception as e:
            logger.error(f"ከጎግል ሺት ማንበብ አልተቻለም: {e}")

    conn = sqlite3.connect("shoe_shop.db")
    cursor = conn.cursor()
    cursor.execute("SELECT product_id, name, price, photo, available_sizes FROM products")
    rows = cursor.fetchall()
    conn.close()

    db_products = []
    for r in rows:
        db_products.append({
            'Product_ID': r[0],
            'Shoe_Name': r[1],
            'Price': r[2],
            'Photo_URL': r[3],
            'Available_Sizes': r[4]
        })
    return db_products

# -------------------------------------------------------------
# ለ) የደንበኞች ምስክርነት ቻናል ሊንክ ከ "Settings" ወይም "Products" ታብ ለማንበብ
# -------------------------------------------------------------
def get_reviews_link():
    default_link = "https://t.me/telegram"
    if spreadsheet:
        try:
            try:
                settings_sheet = spreadsheet.worksheet("Settings")
                records = settings_sheet.get_all_records()
                for row in records:
                    if str(row.get("Key", "")).strip().lower() == "reviews_link":
                        return str(row.get("Value", "")).strip() or default_link
            except Exception:
                pass

            products_sheet = spreadsheet.worksheet("Products")
            records = products_sheet.get_all_records()
            if records and "Reviews_Link" in records[0]:
                link = str(records[0].get("Reviews_Link", "")).strip()
                if link:
                    return link
        except Exception as e:
            logger.error(f"የምስክርነት ሊንክ ከጎግል ሺት ማንበብ አልተቻለም: {e}")

    return default_link

# -------------------------------------------------------------
# ሐ) አዲስ ትዕዛዝ ሲገባ ወደ "Orders" ታብ ለመመዝገብ የሚረዳ ፋንክሽን
# -------------------------------------------------------------
def save_order(customer_name, phone, username, shoe_name, gender, size, color, quantity, total_price, delivery_address):
    if spreadsheet:
        try:
            orders_sheet = spreadsheet.worksheet("Orders")
            now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
            order_id = f"ORD-{int(datetime.datetime.now().timestamp())}"
            
            orders_sheet.append_row([
                order_id,             # Order_ID
                now,                  # Date_Time
                customer_name,        # Customer_Name
                phone,                # Phone_Number
                username,             # Telegram_Username
                shoe_name,            # Shoe_Name
                gender,               # Gender (የወንድ / የሴት)
                size,                 # Size
                color,                # Color
                quantity,             # Quantity
                total_price,          # Total_Price
                delivery_address,     # Delivery_Address
                'Pending',            
                'Unpaid'              
            ])
            return order_id
        except Exception as e:
            logger.error(f"ወደ ጎግል ሺት መጻፍ አልተቻለም: {e}")
            return f"ORD-{int(datetime.datetime.now().timestamp())}"
    else:
        return f"ORD-{int(datetime.datetime.now().timestamp())}"


def init_db():
    conn = sqlite3.connect("shoe_shop.db")
    cursor = conn.cursor()
    
    cursor.execute("DROP TABLE IF EXISTS products")
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS products (
            product_id TEXT PRIMARY KEY,
            name TEXT,
            price REAL,
            photo TEXT,
            available_sizes TEXT
        )
    """)
    
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
        ("#SH-102", "Nike Air Jordan 4 Retro", 3900, "https://images.unsplash.com/photo-1552346154-21d32810aba3?w=500", "39, 40, 41, 42, 43"),
        ("#SH-103", "Adidas Yeezy Boost 350", 4500, "https://images.unsplash.com/photo-1584735935682-2f2b69dff9d2?w=500", "36, 37, 38, 39, 40"),
        ("#SH-104", "Nike Air Force 1 White", 3500, "https://images.unsplash.com/photo-1595950653106-6c9ebd614d3a?w=500", "36, 37, 38, 39, 40, 41, 42, 43")
    ]
    cursor.executemany("INSERT OR IGNORE INTO products VALUES (?, ?, ?, ?, ?)", sample_products)
    conn.commit()
    conn.close()

# የውይይት ደረጃዎች (Conversation States)
(
    LANG_SELECT,
    MENU,
    GALLERY,
    SELECT_GENDER,
    SELECT_COLOR,
    SELECT_SIZE,
    SELECT_QTY,
    GET_PHONE,
    GET_ADDRESS,
    SELECT_PAYMENT,
    GET_RECEIPT,
) = range(11)


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

    try:
        products = get_all_products()
    except Exception as e:
        logger.error(f"ምርቶችን ማንበብ አልተቻለም: {e}")
        products = []

    if not products:
        msg = "እቃ አልተገኘም!" if lang == "am" else "No products found!"
        await query.message.reply_text(msg)
        return MENU

    idx = context.user_data["product_index"] % len(products)
    p = products[idx]
    
    p_id = p.get('Product_ID', '#SH-102')
    name = p.get('Shoe_Name', 'Unknown Shoe')
    price = p.get('Price', 0)
    photo_url = p.get('Photo_URL', '')
    raw_sizes = p.get('Available_Sizes', '')
    
    context.user_data["current_product_id"] = p_id
    context.user_data["current_shoe_name"] = name
    context.user_data["current_shoe_price"] = price
    context.user_data["current_available_sizes"] = str(raw_sizes)

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

    if photo_url and photo_url.strip():
        try:
            await context.bot.send_photo(
                chat_id=query.message.chat_id,
                photo=photo_url,
                caption=text,
                parse_mode="HTML",
                reply_markup=reply_markup
            )
            return GALLERY
        except Exception as e:
            logger.error(f"ፎቶ መላክ አልተቻለም: {e}")

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
# 5. የወንድ/የሴት (Gender Selection) + የስቶክ ማረጋገጫ
# ==========================================
async def select_gender(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    lang = context.user_data.get("lang", "am")

    raw_sizes = context.user_data.get("current_available_sizes", "")
    sizes_list = [s.strip() for s in re.split(r'[, ]+', str(raw_sizes)) if s.strip()]

    if not sizes_list:
        out_msg = "❌ ይቅርታ፣ ይህ ምርት በአሁኑ ሰዓት ያልቀ ስለሆነ መግዛት አይችሉም!" if lang == "am" else "❌ Sorry, this item is currently Out of Stock!"
        await query.answer(out_msg, show_alert=True)
        return GALLERY

    await query.answer()

    if lang == "am":
        keyboard = [
            [
                InlineKeyboardButton("👨 የወንድ (Men's)", callback_data="gender_Men"),
                InlineKeyboardButton("👩 የሴት (Women's)", callback_data="gender_Women")
            ],
            [InlineKeyboardButton("👫 የሁለቱም (Unisex)", callback_data="gender_Unisex")],
            [InlineKeyboardButton("🔙 ተመለስ", callback_data="view_shoes")]
        ]
        prompt_text = "እባክዎን <b>የጫማውን አይነት (የወንድ/የሴት)</b> ይምረጡ፦"
    else:
        keyboard = [
            [
                InlineKeyboardButton("👨 Men's", callback_data="gender_Men"),
                InlineKeyboardButton("👩 Women's", callback_data="gender_Women")
            ],
            [InlineKeyboardButton("👫 Unisex", callback_data="gender_Unisex")],
            [InlineKeyboardButton("🔙 Back", callback_data="view_shoes")]
        ]
        prompt_text = "Please select <b>Shoe Type (Men's/Women's)</b>:"

    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.message.reply_text(prompt_text, parse_mode="HTML", reply_markup=reply_markup)
    return SELECT_GENDER


# ==========================================
# 6. ቀለም መምረጫ (Color Selection)
# ==========================================
async def select_color(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    lang = context.user_data.get("lang", "am")

    if query.data.startswith("gender_"):
        gender = query.data.split("_")[1]
        context.user_data["selected_gender"] = gender
    else:
        gender = context.user_data.get("selected_gender", "Unisex")

    if lang == "am":
        keyboard = [
            [
                InlineKeyboardButton("⚫️ ጥቁር (Black)", callback_data="color_Black"),
                InlineKeyboardButton("⚪️ ነጭ (White)", callback_data="color_White")
            ],
            [
                InlineKeyboardButton("🔴 ቀይ (Red)", callback_data="color_Red"),
                InlineKeyboardButton("🔵 ሰማያዊ (Blue)", callback_data="color_Blue")
            ],
            [InlineKeyboardButton("🔙 ተመለስ", callback_data="order_now")]
        ]
        prompt_text = f"መረጡት አይነት፦ <b>{gender}</b>\nእባክዎን የሚፈልጉትን <b>የጫማ ቀለም</b> ይምረጡ፦"
    else:
        keyboard = [
            [
                InlineKeyboardButton("⚫️ Black", callback_data="color_Black"),
                InlineKeyboardButton("⚪️ White", callback_data="color_White")
            ],
            [
                InlineKeyboardButton("🔴 Red", callback_data="color_Red"),
                InlineKeyboardButton("🔵 Blue", callback_data="color_Blue")
            ],
            [InlineKeyboardButton("🔙 Back", callback_data="order_now")]
        ]
        prompt_text = f"Selected Category: <b>{gender}</b>\nPlease select your preferred <b>Shoe Color</b>:"

    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.message.reply_text(prompt_text, parse_mode="HTML", reply_markup=reply_markup)
    return SELECT_COLOR


# ==========================================
# 7. ሳይዝ መምረጫ (select_size)
# ==========================================
async def select_size(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    lang = context.user_data.get("lang", "am")

    if query.data.startswith("color_"):
        color = query.data.split("_")[1]
        context.user_data["selected_color"] = color
    else:
        color = context.user_data.get("selected_color", "Default")

    raw_sizes = context.user_data.get("current_available_sizes", "")
    sizes_list = [s.strip() for s in re.split(r'[, ]+', str(raw_sizes)) if s.strip()]

    if not sizes_list:
        sizes_list = ["36", "37", "38", "39", "40", "41", "42", "43", "44"]

    keyboard = []
    row = []
    
    for size in sizes_list:
        btn_text = f"ሳይዝ {size}" if lang == "am" else f"Size {size}"
        row.append(InlineKeyboardButton(btn_text, callback_data=f"size_{size}"))
        if len(row) == 3:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)

    back_btn_text = "🔙 ተመለስ" if lang == "am" else "🔙 Back"
    keyboard.append([InlineKeyboardButton(back_btn_text, callback_data="gender_back")])
    reply_markup = InlineKeyboardMarkup(keyboard)

    prompt_text = f"መረጡት ቀለም፦ <b>{color}</b>\nእባክዎን የሚፈልጉትን <b>የጫማ ሳይዝ</b> ይምረጡ፦" if lang == "am" else f"Selected Color: <b>{color}</b>\nPlease select your <b>Shoe Size</b>:"
    await query.message.reply_text(prompt_text, parse_mode="HTML", reply_markup=reply_markup)
    return SELECT_SIZE


async def select_quantity(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    lang = context.user_data.get("lang", "am")

    size = query.data.split("_")[1]
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
# 8. ስልክ እና አድራሻ መጠየቂያ
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
# 9. ክፍያ እና ደረሰኝ
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
# 10. ትዕዛዝ ማረጋገጫ እና ወደ ጎግል ሺት መጻፍ
# ==========================================
async def confirm_order(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.effective_user
    lang = context.user_data.get("lang", "am")
    photo_file = update.message.photo[-1].file_id

    shoe_name = context.user_data.get("current_shoe_name", "Unknown Shoe")
    shoe_price = context.user_data.get("current_shoe_price", 0)
    gender = context.user_data.get("selected_gender", "Unisex")
    color = context.user_data.get("selected_color", "Default")
    size = context.user_data.get("selected_size")
    qty = context.user_data.get("selected_qty", 1)
    phone = context.user_data.get("phone", "N/A")
    address = context.user_data.get("address", "N/A")
    total_price = shoe_price * qty
    username = f"@{user.username}" if user.username else "የለውም"

    try:
        order_id = save_order(
            customer_name=user.full_name,
            phone=phone,
            username=username,
            shoe_name=shoe_name,
            gender=gender,
            size=size,
            color=color,
            quantity=qty,
            total_price=total_price,
            delivery_address=address
        )
    except Exception as e:
        logger.error(f"ትዕዛዙን ወደ ጎግል ሺት መጻፍ አልተቻለም: {e}")
        order_id = f"ORD-{random.randint(1000, 9999)}"

    conn = sqlite3.connect("shoe_shop.db")
    cursor = conn.cursor()
    cursor.execute("""
        INSERT OR IGNORE INTO orders VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (order_id, user.id, user.username, user.first_name, phone, address, shoe_name, size, qty, "Pending"))
    conn.commit()
    conn.close()

    admin_text = (
        f"🚨 <b>አዲስ የጫማ ትዕዛዝ ደርሷል! ({order_id})</b>\n\n"
        f"👤 <b>ደንበኛ:</b> {user.full_name} ({username})\n"
        f"📱 <b>ስልክ:</b> {phone}\n"
        f"📍 <b>አድራሻ:</b> {address}\n"
        f"👟 <b>ምርት:</b> {shoe_name}\n"
        f"👤 <b>አይነት:</b> {gender} | 🎨 <b>ቀለም:</b> {color} | 📏 <b>ሳይዝ:</b> {size}\n"
        f"📦 <b>ብዛት:</b> {qty} ጥንድ | 💵 <b>ጠቅላላ ዋጋ:</b> {total_price} ETB"
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
# 11. አድሚን ክትትል፣ የምስክርነት ሊንክ እና ተጨማሪ ገጾች
# ==========================================
async def handle_admin_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    data = query.data
    parts = data.split("_")
    action = parts[1]
    order_id = f"ORD-{parts[2]}" if len(parts) > 2 else "ORD"

    if action == "approve":
        await query.edit_message_caption(caption=query.message.caption + "\n\n<b>[✅ STATUS: APPROVED]</b>", parse_mode="HTML")
    elif action == "cancel":
        await query.edit_message_caption(caption=query.message.caption + "\n\n<b>[❌ STATUS: CANCELLED]</b>", parse_mode="HTML")


async def size_guide(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    lang = context.user_data.get("lang", "am")
    
    if lang == "am":
        text = "📐 <b>ትክክለኛ የጫማ ሳይዝ መመሪያ፦</b>\n• 36-39 Size: የሴት ሳይዝ\n• 40-44 Size: የወንድ ሳይዝ"
        btn = "🔙 ወደ ዋና ሜኑ"
    else:
        text = "📐 <b>Shoe Size Guide:</b>\n• Size 36-39: Women's Size\n• Size 40-44: Men's Size"
        btn = "🔙 Back to Menu"

    keyboard = [[InlineKeyboardButton(btn, callback_data="back_to_menu")]]
    await query.message.reply_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(keyboard))
    return MENU


async def show_reviews(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    lang = context.user_data.get("lang", "am")
    
    reviews_link = get_reviews_link()

    if lang == "am":
        text = "⭐️ <b>የደንበኞቻችን ምስክርነት፦</b>\n\nደስተኛ የሆኑ ደንበኞቻችን የሰጡንን አስተያየትና ምስክርነት ከታች ያለውን አዝራር በመጫን በቴሌግራም ቻናላችን ላይ መመልከት ይችላሉ፦"
        btn_text = "🔗 ምስክርነቶችን ይመልከቱ"
        back_text = "🔙 ወደ ዋና ሜኑ"
    else:
        text = "⭐️ <b>Customer Reviews:</b>\n\nYou can view feedback and reviews from our happy customers on our Telegram channel by clicking the button below:"
        btn_text = "🔗 View Reviews"
        back_text = "🔙 Back to Menu"

    keyboard = [
        [InlineKeyboardButton(btn_text, url=reviews_link)],
        [InlineKeyboardButton(back_text, callback_data="back_to_menu")]
    ]
    
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
# 12. ዋና ማስኬጃ (Main)
# ==========================================
def main():
    keep_alive()
    init_db()

    TOKEN = "8686401024:AAFtTF24ncEWVNuDDF2qQtiSP3NTMlzB2n0"
    
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
                CallbackQueryHandler(show_reviews, pattern="^reviews$"),
                CallbackQueryHandler(shop_location, pattern="^location$"),
                CallbackQueryHandler(main_menu, pattern="^back_to_menu$"),
            ],
            GALLERY: [
                CallbackQueryHandler(select_gender, pattern="^order_now$"),
                CallbackQueryHandler(navigate_products, pattern="^(next|prev)_product$"),
                CallbackQueryHandler(main_menu, pattern="^back_to_menu$"),
            ],
            SELECT_GENDER: [
                CallbackQueryHandler(select_color, pattern="^gender_"),
                CallbackQueryHandler(view_shoes, pattern="^view_shoes$"),
            ],
            SELECT_COLOR: [
                CallbackQueryHandler(select_size, pattern="^color_"),
                CallbackQueryHandler(select_gender, pattern="^order_now$"),
            ],
            SELECT_SIZE: [
                CallbackQueryHandler(select_quantity, pattern="^size_"),
                CallbackQueryHandler(select_color, pattern="^gender_back$"),
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
