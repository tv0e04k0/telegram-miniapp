import logging
from telegram import (
    Update, ReplyKeyboardMarkup, ReplyKeyboardRemove,
    InlineKeyboardMarkup, InlineKeyboardButton
)
from telegram.ext import (
    Updater, CommandHandler, CallbackContext, MessageHandler, Filters,
    ConversationHandler, CallbackQueryHandler
)
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from googleapiclient.discovery import build
from datetime import datetime
import calendar
from collections import Counter
import os

# Этапы
(
    SHEET, ROW, OPERATION, DATE, NAME, QUANTITY, SUPPLIER, FIO, NAME_SEARCH,
    PHONE, CITY, TRACK, COST, DELIVERY, ORDER, SERIAL, COMMENT, SHOP, STOCK_SEARCH
) = range(19)


BACK = '◀ Назад'

# Токены
TOKEN = os.getenv('T7571543010:AAGGdsowEAJOE4sVCWMNKFslo4vNSoU3SjYЫ')
GOOGLE_SHEET_ID = os.getenv('1y8vXc06xSGcOdaYYxIKQIaNkVBMJe8-qPBXyNyUujr8'')

# Авторизация
scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
creds = ServiceAccountCredentials.from_json_keyfile_name('creds.json', scope)
client = gspread.authorize(creds)
sheet = client.open_by_key(GOOGLE_SHEET_ID)


logging.basicConfig(level=logging.INFO)

# Утилита: задать формат ячейки
def set_cell_format(sheet_id, tab_id, row_idx, col_idx, fmt_type):
    service = build('sheets', 'v4', credentials=creds)
    pattern = '0' if fmt_type == 'NUMBER' else '@'
    requests = [{
        "repeatCell": {
            "range": {
                "sheetId": tab_id,
                "startRowIndex": row_idx,
                "endRowIndex": row_idx + 1,
                "startColumnIndex": col_idx,
                "endColumnIndex": col_idx + 1
            },
            "cell": {
                "userEnteredFormat": {
                    "numberFormat": {
                        "type": fmt_type,
                        "pattern": pattern
                    }
                }
            },
            "fields": "userEnteredFormat.numberFormat"
        }
    }]
    service.spreadsheets().batchUpdate(
        spreadsheetId=sheet_id,
        body={"requests": requests}
    ).execute()

# ТОП-10 товаров
def get_top_items():
    try:
        ws = sheet.worksheet('Операции')
        names = ws.col_values(7)
        counter = Counter(n.strip() for n in names if n.strip())
        return [item for item, _ in counter.most_common(10)]
    except Exception as e:
        logging.error(f"Ошибка в get_top_items: {e}")
        return []

def get_top_fields():
    try:
        ws = sheet.worksheet('Операции')
        data = ws.get_all_values()[3:]  # строки с 4-й
        columns = [2, 3, 7, 8, 11, 18, 19, 20]  # индексы: C, D, H, I, L, S, T, U
        values = []

        for row in data:
            for col in columns:
                if len(row) > col and row[col].strip():
                    values.append(row[col].strip())

        counter = Counter(values)
        return [item for item, _ in counter.most_common(10)]
    except Exception as e:
        logging.error(f"Ошибка в get_top_fields: {e}")
        return []

# Поиск товара
def search_items(query):
    try:
        ws = sheet.worksheet('Остатки')
        all_items = ws.col_values(1)[5:]
        return [i for i in all_items if query.lower() in i.lower()][:10]
    except Exception as e:
        logging.error(f"Ошибка в search_items: {e}")
        return []

class InlineCalendar:
    def __init__(self, year=None, month=None):
        now = datetime.now()
        self.year = year or now.year
        self.month = month or now.month
        self.month_names = ['Январь', 'Февраль', 'Март', 'Апрель', 'Май', 'Июнь',
                            'Июль', 'Август', 'Сентябрь', 'Октябрь', 'Ноябрь', 'Декабрь']
        self.week_days = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс']

    def create(self):
        markup = []
        markup.append([InlineKeyboardButton(f"{self.month_names[self.month-1]} {self.year}", callback_data="ignore")])
        markup.append([InlineKeyboardButton(day, callback_data="ignore") for day in self.week_days])

        for week in calendar.monthcalendar(self.year, self.month):
            row = []
            for day in week:
                if day == 0:
                    row.append(InlineKeyboardButton(" ", callback_data="ignore"))
                else:
                    row.append(InlineKeyboardButton(str(day), callback_data=f"date_{self.year}_{self.month}_{day}"))
            markup.append(row)

        markup.append([
            InlineKeyboardButton("<", callback_data="prev_month"),
            InlineKeyboardButton(">", callback_data="next_month")
        ])

        return InlineKeyboardMarkup(markup)

# Utility function to create reply keyboard markup
def create_reply_keyboard(buttons_list):
    return ReplyKeyboardMarkup(buttons_list, resize_keyboard=True)

# Старт
def start(update: Update, context: CallbackContext) -> int:
    keyboard = [['Операции'], ['Остатки'], ['Справочник']]
    update.message.reply_text('Привет! Выбери лист для работы:', reply_markup=create_reply_keyboard(keyboard))
    return SHEET

def select_sheet(update: Update, context: CallbackContext) -> int:
    context.user_data.clear()
    context.user_data['sheet_name'] = update.message.text
    update.message.reply_text('В какую строку внести данные?', reply_markup=ReplyKeyboardRemove())
    return ROW

def get_row(update: Update, context: CallbackContext) -> int:
    if update.message.text == BACK:
        return start(update, context)

    context.user_data['row'] = int(update.message.text)
    keyboard = [['Приход', 'Продажа'], ['Резерв', 'Списание'], ['Инвентаризация', 'Перемещение'], [BACK]]
    update.message.reply_text('Выбери операцию:', reply_markup=create_reply_keyboard(keyboard))
    return OPERATION

def get_operation(update: Update, context: CallbackContext) -> int:
    if update.message.text == BACK:
        return select_sheet(update, context)

    context.user_data['operation'] = update.message.text
    keyboard = [
        [InlineKeyboardButton("✅ Сегодня", callback_data="date_today")],
        [InlineKeyboardButton("📅 Выбрать дату", callback_data="date_custom")]
    ]
    update.message.reply_text("📆 Выбери дату:", reply_markup=InlineKeyboardMarkup(keyboard))
    return DATE

def handle_date_buttons(update: Update, context: CallbackContext) -> int:
    query = update.callback_query
    query.answer()

    if query.data == "date_today":
        context.user_data['date'] = datetime.today().strftime('%d.%m.%y')
        query.edit_message_text(f"📅 Дата выбрана: {context.user_data['date']}")

    elif query.data == "date_custom":
        now = datetime.now()
        context.user_data['calendar'] = {'year': now.year, 'month': now.month}
        query.edit_message_text("📅 Выберите дату:", reply_markup=InlineCalendar().create())
        return DATE

    elif query.data.startswith("date_"):
        _, y, m, d = query.data.split("_")
        context.user_data['date'] = datetime(int(y), int(m), int(d)).strftime('%d.%m.%y')
        query.edit_message_text(f"📅 Дата выбрана: {context.user_data['date']}")

    elif query.data in ["prev_month", "next_month"]:
        cal = context.user_data['calendar']
        y, m = cal['year'], cal['month']
        if query.data == "prev_month":
            m -= 1
            if m == 0:
                m, y = 12, y - 1
        else:
            m += 1
            if m == 13:
                m, y = 1, y + 1
        context.user_data['calendar'] = {'year': y, 'month': m}
        query.edit_message_reply_markup(reply_markup=InlineCalendar(y, m).create())
        return DATE

    # После выбора даты — показать ТОП или поиск
    top_items = get_top_items()
    keyboard = [[item] for item in top_items] + [["🔍 Найти товар"], [BACK]]
    context.bot.send_message(
        chat_id=query.message.chat_id,
        text="Выберите наименование или воспользуйтесь поиском:",
        reply_markup=create_reply_keyboard(keyboard)
    )
    return NAME

def get_name(update: Update, context: CallbackContext) -> int:
    if update.message.text == BACK:
        update.message.reply_text("📆 Повторно выберите дату:", reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Сегодня", callback_data="date_today")],
            [InlineKeyboardButton("📅 Выбрать дату", callback_data="date_custom")]
        ]))
        return DATE

    if update.message.text == "🔍 Найти товар":
        context.user_data['search_attempts'] = 0
        update.message.reply_text("🔎 Введите часть названия товара:")
        return NAME_SEARCH

    context.user_data['name'] = update.message.text
    update.message.reply_text("Введите количество:", reply_markup=create_reply_keyboard([[BACK]]))
    return QUANTITY

def handle_search_query(update: Update, context: CallbackContext) -> int:
    query = update.message.text
    matches = search_items(query)
    if matches:
        buttons = [[m] for m in matches] + [[BACK]]
        update.message.reply_text("🔎 Найдено:", reply_markup=create_reply_keyboard(buttons))
        return NAME
    else:
        context.user_data['search_attempts'] += 1
        if context.user_data['search_attempts'] >= 2:
            update.message.reply_text("❌ Ничего не найдено. Введите вручную:")
            return NAME
        else:
            update.message.reply_text("❌ Не найдено. Попробуйте ещё раз:")
            return NAME_SEARCH

def get_quantity(update: Update, context: CallbackContext) -> int:
    if update.message.text == BACK:
        return get_name(update, context)

    context.user_data['quantity'] = update.message.text
    update.message.reply_text("Введите поставщика:", reply_markup=create_reply_keyboard([[BACK]]))
    return SUPPLIER

def get_supplier(update: Update, context: CallbackContext) -> int:
    if update.message.text == BACK:
        return get_quantity(update, context)

    context.user_data['supplier'] = update.message.text
    update.message.reply_text("Введите ФИО:", reply_markup=create_reply_keyboard([[BACK]]))
    return FIO

def get_fio(update: Update, context: CallbackContext) -> int:
    if update.message.text == BACK:
        return get_supplier(update, context)

    context.user_data['fio'] = update.message.text
    update.message.reply_text("Введите магазин:", reply_markup=create_reply_keyboard([[BACK]]))
    return SHOP

def get_shop(update: Update, context: CallbackContext) -> int:
    if update.message.text == BACK:
        return get_fio(update, context)

    context.user_data['shop'] = update.message.text
    update.message.reply_text("Введите телефон:", reply_markup=create_reply_keyboard([[BACK]]))
    return PHONE

def get_phone(update: Update, context: CallbackContext) -> int:
    if update.message.text == BACK:
        return get_shop(update, context)

    context.user_data['phone'] = update.message.text
    update.message.reply_text("Введите город:", reply_markup=create_reply_keyboard([[BACK]]))
    return CITY

def get_city(update: Update, context: CallbackContext) -> int:
    if update.message.text == BACK:
        return get_phone(update, context)

    context.user_data['city'] = update.message.text
    update.message.reply_text("Введите трек номер:", reply_markup=create_reply_keyboard([[BACK]]))
    return TRACK

def get_track(update: Update, context: CallbackContext) -> int:
    if update.message.text == BACK:
        return get_city(update, context)

    context.user_data['track'] = update.message.text
    update.message.reply_text("Введите стоимость:", reply_markup=create_reply_keyboard([[BACK]]))
    return COST

def get_cost(update: Update, context: CallbackContext) -> int:
    if update.message.text == BACK:
        return get_track(update, context)

    context.user_data['cost'] = update.message.text
    update.message.reply_text("Введите доставку:", reply_markup=create_reply_keyboard([[BACK]]))
    return DELIVERY

def get_delivery(update: Update, context: CallbackContext) -> int:
    if update.message.text == BACK:
        return get_cost(update, context)

    context.user_data['delivery'] = update.message.text
    update.message.reply_text("Введите № заказа:", reply_markup=create_reply_keyboard([[BACK]]))
    return ORDER

def get_order(update: Update, context: CallbackContext) -> int:
    if update.message.text == BACK:
        return get_delivery(update, context)

    context.user_data['order'] = update.message.text
    update.message.reply_text("Введите серийный номер:", reply_markup=create_reply_keyboard([[BACK]]))
    return SERIAL

def get_serial(update: Update, context: CallbackContext) -> int:
    if update.message.text == BACK:
        return get_order(update, context)

    context.user_data['serial'] = update.message.text
    update.message.reply_text("Введите комментарий:", reply_markup=create_reply_keyboard([[BACK]]))
    return COMMENT

def get_comment(update: Update, context: CallbackContext) -> int:
    if update.message.text == BACK:
        return get_serial(update, context)

    context.user_data['comment'] = update.message.text
    data = context.user_data
    ws = sheet.worksheet(data['sheet_name'])
    row = data['row']

    # Числа
    def get_num(key): return float(data[key].replace(',', '.')) if data[key] else 0

    ws.update(f'B{row}', [[data['date']]])
    ws.update(f'D{row}', [[data['operation']]])
    ws.update(f'G{row}', [[data['name']]])
    ws.update(f'H{row}', [[get_num("quantity")]])
    ws.update(f'I{row}', [[data['supplier']]])
    ws.update(f'J{row}', [[data['fio']]])
    ws.update(f'C{row}', [[data['shop']]])
    ws.update(f'K{row}', [[data['phone']]]),  # без get_num
    ws.update(f'L{row}', [[data['city']]])
    ws.update(f'O{row}', [[data['track']]])
    ws.update(f'S{row}', [[get_num("cost")]])
    ws.update(f'T{row}', [[get_num("delivery")]])
    ws.update(f'U{row}', [[data['order']]])
    ws.update(f'V{row}', [[data['serial']]])
    ws.update(f'Y{row}', [[data['comment']]])

    # Формат
    tab_id = ws._properties['sheetId']
    row_i = row - 1
    formats = {
        'S': 'NUMBER', 'T': 'NUMBER',  # ← только эти остаются числами
        'C': 'TEXT', 'K': 'TEXT', 'L': 'TEXT', 'O': 'TEXT', 'U': 'TEXT', 'V': 'TEXT', 'Y': 'TEXT'
    }
    col_map = {'A': 0, 'B': 1, 'C': 2, 'D': 3, 'E': 4, 'F': 5, 'G': 6, 'H': 7,
               'I': 8, 'J': 9, 'K': 10, 'L': 11, 'M': 12, 'N': 13, 'O': 14,
               'P': 15, 'Q': 16, 'R': 17, 'S': 18, 'T': 19, 'U': 20, 'V': 21, 'Y': 24}
    for col, fmt in formats.items():
        set_cell_format(GOOGLE_SHEET_ID, tab_id, row_i, col_map[col], fmt)

    update.message.reply_text("✅ Все данные записаны!", reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END

def cancel(update: Update, context: CallbackContext) -> int:
    update.message.reply_text("❌ Операция отменена.", reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END

def stock_start(update: Update, context: CallbackContext) -> int:
    update.message.reply_text("🔍 Введите часть названия товара для поиска по остаткам:")
    return STOCK_SEARCH

def stock_search(update: Update, context: CallbackContext) -> int:
    query = update.message.text.strip().lower()
    ws = sheet.worksheet("Остатки")
    data = ws.get_all_values()[5:]  # A6:E

    results = []
    for row in data:
        name = row[0].strip().lower()
        if query in name:
            results.append(row[:5])

    if not results:
        update.message.reply_text("❌ Ничего не найдено. Попробуйте снова:")
        return STOCK_SEARCH

    msg = "\n".join([" | ".join(r) for r in results])
    update.message.reply_text(f"📦 Найдено: {msg}")
    return ConversationHandler.END

def main():
    updater = Updater(TOKEN)
    dp = updater.dispatcher

    conv = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            SHEET: [MessageHandler(Filters.text & ~Filters.command, select_sheet
