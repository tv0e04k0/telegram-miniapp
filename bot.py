import logging
import os
import json
import calendar
from datetime import datetime, timedelta
from collections import defaultdict

import gspread
from oauth2client.service_account import ServiceAccountCredentials

from telegram import (
    InlineKeyboardButton, InlineKeyboardMarkup, Update
)
from telegram.ext import (
    Updater, CommandHandler, CallbackQueryHandler, MessageHandler,
    Filters, ConversationHandler, CallbackContext
)

# === НАСТРОЙКИ ===
TOKEN = '7571543010:AAGGdsowEAJOE4sVCWMNKFslo4vNSoU3SjY'
GOOGLE_SHEET_ID = '1y8vXc06xSGcOdaYYxIKQIaNkVBMJe8-qPBXyNyUujr8'
SHEET_NAME = 'Операции'
START_ROW = 5

# === Google Sheets авторизация ===
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_name("creds.json", scope)
client = gspread.authorize(creds)
sheet = client.open_by_key(GOOGLE_SHEET_ID).worksheet(SHEET_NAME)

# === Состояния ===
(
    CHOOSE_ROW, GET_DATE, GET_MAGAZIN, GET_ZABOR, GET_OPER, GET_TOVAR,
    SEARCH_TOVAR, GET_KOL, GET_FIO, SEARCH_FIO, GET_TELEFON, GET_GOROD,
    GET_TREK, GET_PRICE, GET_DOSTAVKA, GET_NZAKAZA, GET_SERNOM, GET_KOMMENT,
    PREVIEW, CONFIRM
) = range(20)

# === Память ===
user_data_store = defaultdict(dict)
# === Шаги по маршруту (в заданном порядке) ===
STEP_FLOW = [
    ("DD MM GGGG", GET_DATE, None),
    ("Magazin", GET_MAGAZIN, 3),
    ("Zabor", GET_ZABOR, 9),
    ("Oper", GET_OPER, 4),
    ("Tovar", GET_TOVAR, 7),
    ("Kol", GET_KOL, 8),
    ("FIO", GET_FIO, 10),
    ("Telefon", GET_TELEFON, 11),
    ("Gorod", GET_GOROD, 12),
    ("TrekNomer", GET_TREK, 15),
    ("Price", GET_PRICE, 19),
    ("Dostavka", GET_DOSTAVKA, 20),
    ("Nomer Zakaza", GET_NZAKAZA, 21),
    ("SerNom", GET_SERNOM, 22),
    ("Komment", GET_KOMMENT, 25),
]

def route_next_field(update: Update, context: CallbackContext, current_field=None, direction="next"):
    uid = update.effective_user.id
    stack = user_data_store[uid].get("step_stack", [])
    idx = next((i for i, (f, _, _) in enumerate(STEP_FLOW) if f == current_field), -1)
    next_idx = idx + 1 if direction == "next" else idx - 1

    if 0 <= next_idx < len(STEP_FLOW):
        next_field, next_state, col = STEP_FLOW[next_idx]
        user_data_store[uid]["step_stack"] = stack[:next_idx]
        if next_field == "DD MM GGGG":
            return send_calendar(update, context, datetime.now().year, datetime.now().month)
        elif next_field == "FIO":
            return ask_top_fio(update, context)
        else:
            return ask_top(update, context, next_field, col, next_state)
    else:
        return show_preview(update, context)
def ask_top(update: Update, context: CallbackContext, field, column_index, next_state):
    uid = update.effective_user.id
    user_data_store[uid]["current_field"] = field
    user_data_store[uid]["current_col"] = column_index
    user_data_store[uid]["next_state"] = next_state

    values = sheet.col_values(column_index)[START_ROW - 1:]
    freq = defaultdict(int)
    for v in values:
        if v.strip():
            freq[v.strip()] += 1
    top_10 = sorted(freq.items(), key=lambda x: x[1], reverse=True)[:10]

    keyboard = [[InlineKeyboardButton(v[0], callback_data=v[0])] for v in top_10]
    keyboard.append([InlineKeyboardButton("🔍 Найти", callback_data="search")])
    keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="back")])

    update.message.reply_text(f"Выбери {field} или найди:", reply_markup=InlineKeyboardMarkup(keyboard))
    return next_state

def handle_top_choice(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    uid = query.from_user.id
    field = user_data_store[uid]["current_field"]
    col = user_data_store[uid]["current_col"]

    if query.data == "search":
        query.edit_message_text(f"Введи часть значения поля {field}:")
        return SEARCH_TOVAR

    if query.data == "back":
        return route_next_field(update, context, current_field=field, direction="back")

    user_data_store[uid][field] = query.data
    query.edit_message_text(f"{field} выбрано: {query.data}")
    return route_next_field(update, context, current_field=field)

def handle_search(update: Update, context: CallbackContext):
    uid = update.effective_user.id
    field = user_data_store[uid]["current_field"]
    col = user_data_store[uid]["current_col"]
    query = update.message.text.strip().lower()

    values = sheet.col_values(col)[START_ROW - 1:]
    matches = list({v for v in values if query in v.lower()})[:10]

    if matches:
        keyboard = [[InlineKeyboardButton(v, callback_data=v)] for v in matches]
        keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="back")])
        update.message.reply_text("Вот что нашлось:", reply_markup=InlineKeyboardMarkup(keyboard))
        return user_data_store[uid]["next_state"]
    else:
        update.message.reply_text("Ничего не найдено. Введи снова:")
        return SEARCH_TOVAR
# === Календарь ===
def send_calendar(update, context, year, month):
    uid = update.effective_user.id
    context.user_data["calendar_year"] = year
    context.user_data["calendar_month"] = month

    days = calendar.monthcalendar(year, month)
    keyboard = []
    for week in days:
        row = []
        for day in week:
            row.append(InlineKeyboardButton(" " if day == 0 else str(day), callback_data=f"day_{day}"))
        keyboard.append(row)

    keyboard.append([
        InlineKeyboardButton("<<", callback_data="prev_month"),
        InlineKeyboardButton(f"{month:02d}.{year}", callback_data="ignore"),
        InlineKeyboardButton(">>", callback_data="next_month")
    ])
    markup = InlineKeyboardMarkup(keyboard)

    if update.message:
        update.message.reply_text("Выбери дату продажи:", reply_markup=markup)
    else:
        update.callback_query.edit_message_text("Выбери дату продажи:", reply_markup=markup)

    return GET_DATE

def handle_calendar(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    uid = query.from_user.id
    year = context.user_data["calendar_year"]
    month = context.user_data["calendar_month"]

    if query.data == "prev_month":
        prev = datetime(year, month, 1) - timedelta(days=1)
        return send_calendar(query, context, prev.year, prev.month)
    elif query.data == "next_month":
        next_month = datetime(year, month, 28) + timedelta(days=4)
        next_month = next_month.replace(day=1)
        return send_calendar(query, context, next_month.year, next_month.month)
    elif query.data.startswith("day_"):
        day = int(query.data.split("_")[1])
        date_str = f"{day:02d}.{month:02d}.{year % 100:02d}"
        user_data_store[uid]["DD MM GGGG"] = date_str
        query.edit_message_text(f"Дата выбрана: {date_str}")
        return route_next_field(update, context, current_field="DD MM GGGG")
    else:
        return GET_DATE

# === Шаг FIO ===
def ask_top_fio(update: Update, context: CallbackContext):
    uid = update.effective_user.id
    values = sheet.col_values(10)[START_ROW - 1:]  # колонка J: FIO
    freq = defaultdict(int)
    for val in values:
        if val.strip():
            freq[val.strip()] += 1
    top = sorted(freq.items(), key=lambda x: x[1], reverse=True)[:10]
    keyboard = [[InlineKeyboardButton(v[0], callback_data=v[0])] for v in top]
    keyboard.append([InlineKeyboardButton("🔍 Найти", callback_data="search_fio")])
    keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="back")])
    update.message.reply_text("Выбери или найди ФИО:", reply_markup=InlineKeyboardMarkup(keyboard))
    return GET_FIO

def handle_fio_choice(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    uid = query.from_user.id

    if query.data == "search_fio":
        query.edit_message_text("Введи часть ФИО:")
        return SEARCH_FIO
    if query.data == "back":
        return route_next_field(update, context, current_field="FIO", direction="back")

    user_data_store[uid]["FIO"] = query.data
    query.edit_message_text(f"ФИО выбрано: {query.data}")
    return route_next_field(update, context, current_field="FIO")

def handle_fio_search(update: Update, context: CallbackContext):
    uid = update.effective_user.id
    query = update.message.text.strip().lower()
    values = sheet.col_values(10)[START_ROW - 1:]
    matches = list({v for v in values if query in v.lower()})[:10]

    if matches:
        keyboard = [[InlineKeyboardButton(v, callback_data=v)] for v in matches]
        keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="back")])
        update.message.reply_text("Вот что нашлось:", reply_markup=InlineKeyboardMarkup(keyboard))
        return GET_FIO
    else:
        update.message.reply_text("Ничего не найдено. Попробуй снова:")
        return SEARCH_FIO
def show_preview(update: Update, context: CallbackContext):
    uid = update.effective_user.id
    data = user_data_store[uid]
    fields = [
        "DD MM GGGG", "Magazin", "Zabor", "Oper", "Tovar", "Kol",
        "FIO", "Telefon", "Gorod", "TrekNomer", "Price", "Dostavka",
        "Nomer Zakaza", "SerNom", "Komment"
    ]
    preview_text = f"Проверь данные (строка {data['row']}):\n\n"
    for f in fields:
        preview_text += f"{f}: {data.get(f, '—')}\n"

    keyboard = [
        [InlineKeyboardButton("✅ Записать", callback_data="confirm")],
        [InlineKeyboardButton("🔁 Начать заново", callback_data="restart")]
    ]
    update.message.reply_text(preview_text, reply_markup=InlineKeyboardMarkup(keyboard))
    return PREVIEW

def save_to_log(user_id):
    data = user_data_store[user_id]
    now = datetime.now().strftime("%d.%m.%Y %H:%M:%S")
    user_name = data.get("user_name", "—")

    fields = [
        "DD MM GGGG", "FIO", "Magazin", "Oper", "Zabor", "Tovar", "Kol",
        "Gorod", "Price", "Dostavka", "Telefon", "Nomer Zakaza", "SerNom", "TrekNomer", "Komment"
    ]
    entry = {
        "timestamp": now,
        "user": user_name,
        "fields": {f: data.get(f, "") for f in fields}
    }

    log_path = "log.json"
    if os.path.exists(log_path):
        with open(log_path, "r", encoding="utf-8") as f:
            log = json.load(f)
    else:
        log = []

    log.append(entry)

    with open(log_path, "w", encoding="utf-8") as f:
        json.dump(log, f, ensure_ascii=False, indent=2)

def handle_preview_actions(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    uid = query.from_user.id
    data = user_data_store[uid]
    row = data["row"]

    if query.data == "confirm":
        field_to_col = {
            "DD MM GGGG": 2, "Magazin": 3, "Oper": 4, "Zabor": 9, "Tovar": 7,
            "Kol": 8, "FIO": 10, "Telefon": 11, "Gorod": 12, "TrekNomer": 15,
            "Price": 19, "Dostavka": 20, "Nomer Zakaza": 21, "SerNom": 22, "Komment": 25
        }
        for field, col in field_to_col.items():
            sheet.update_cell(row, col, data.get(field, ""))
        user_data_store[uid]["user_name"] = query.from_user.full_name
        save_to_log(uid)
        query.edit_message_text("✅ Данные записаны и добавлены в log.json!")
        return ConversationHandler.END

    elif query.data == "restart":
        user_data_store[uid] = {}
        query.edit_message_text("Начнём заново. Введи номер строки:")
        return CHOOSE_ROW

def start(update: Update, context: CallbackContext):
    update.message.reply_text(
        "Привет! Введи номер строки для записи (например, 5, 6, 7...):"
    )
    return CHOOSE_ROW

def choose_row(update: Update, context: CallbackContext):
    uid = update.effective_user.id
    text = update.message.text.strip()
    if not text.isdigit() or int(text) < START_ROW:
        update.message.reply_text("Номер строки должен быть числом от 5 и выше.")
        return CHOOSE_ROW

    user_data_store[uid]["row"] = int(text)
    user_data_store[uid]["step_stack"] = []
    return route_next_field(update, context, current_field=None)

def cancel(update: Update, context: CallbackContext):
    update.message.reply_text("Действие отменено.")
    return ConversationHandler.END

def main():
    updater = Updater(TOKEN, use_context=True)
    dp = updater.dispatcher

    conv = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            CHOOSE_ROW: [MessageHandler(Filters.text & ~Filters.command, choose_row)],
            GET_DATE: [CallbackQueryHandler(handle_calendar)],
            GET_MAGAZIN: [CallbackQueryHandler(handle_top_choice)],
            GET_ZABOR: [CallbackQueryHandler(handle_top_choice)],
            GET_OPER: [CallbackQueryHandler(handle_top_choice)],
            GET_TOVAR: [CallbackQueryHandler(handle_top_choice)],
            SEARCH_TOVAR: [MessageHandler(Filters.text & ~Filters.command, handle_search)],
            GET_KOL: [CallbackQueryHandler(handle_top_choice)],
            GET_FIO: [CallbackQueryHandler(handle_fio_choice)],
            SEARCH_FIO: [MessageHandler(Filters.text & ~Filters.command, handle_fio_search)],
            GET_TELEFON: [CallbackQueryHandler(handle_top_choice)],
            GET_GOROD: [CallbackQueryHandler(handle_top_choice)],
            GET_TREK: [CallbackQueryHandler(handle_top_choice)],
            GET_PRICE: [CallbackQueryHandler(handle_top_choice)],
            GET_DOSTAVKA: [CallbackQueryHandler(handle_top_choice)],
            GET_NZAKAZA: [CallbackQueryHandler(handle_top_choice)],
            GET_SERNOM: [CallbackQueryHandler(handle_top_choice)],
            GET_KOMMENT: [CallbackQueryHandler(handle_top_choice)],
            PREVIEW: [CallbackQueryHandler(handle_preview_actions)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    dp.add_handler(conv)
    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()
