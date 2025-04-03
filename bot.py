import logging
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardRemove
from telegram.ext import (
    Updater, CommandHandler, CallbackContext, MessageHandler, Filters,
    ConversationHandler, CallbackQueryHandler
)


def start(update: Update, context: CallbackContext) -> int:
    update.message.reply_text("👋 Бот запущен! Введите /start для начала.")
    return ConversationHandler.END


TOKEN = '7571543010:AAGGdsowEAJOE4sVCWMNKFslo4vNSoU3SjY'
GOOGLE_SHEET_ID = '1y8vXc06xSGcOdaYYxIKQIaNkVBMJe8-qPBXyNyUujr8'

def get_supplier(update: Update, context: CallbackContext) -> int:
    value = update.message.text
    context.user_data['Zabor'] = value
    route = ROUTES.get(value.strip(), [])
    context.user_data['route'] = route
    context.user_data['step_index'] = 0
    return next_step(update, context)

def get_top_by_column(col_letter: str, limit: int = 10) -> list:
    try:
        ws = sheet.worksheet('Операции')
        col_index = ord(col_letter.upper()) - ord('A') + 1
        values = ws.col_values(col_index)[3:]
        values = [v.strip() for v in values if v.strip()]
        counter = Counter(values)
        return [item for item, _ in counter.most_common(limit)]
    except Exception as e:
        print(f"Ошибка в get_top_by_column({col_letter}): {e}")
        return []

def next_step(update: Update, context: CallbackContext) -> int:
    route = context.user_data.get('route', [])
    index = context.user_data.get('step_index', 0)

    if index >= len(route):
        update.message.reply_text("✅ Все данные собраны!", reply_markup=ReplyKeyboardRemove())
        return ConversationHandler.END

    current_col = route[index]
    context.user_data['step_index'] = index + 1

    if current_col == 'J':
        update.message.reply_text("Введите ФИО:")
        return FIO

    elif current_col == 'K':
        top = get_top_by_column('K')
        keyboard = [[InlineKeyboardButton(text, callback_data=text)] for text in top]
        keyboard.append([InlineKeyboardButton("✏ Ввести вручную", callback_data='manual')])
        update.message.reply_text("📱 Выберите телефон:", reply_markup=InlineKeyboardMarkup(keyboard))
        return PHONE_INLINE

    elif current_col == 'L':
        top = get_top_by_column('L')
        keyboard = [[InlineKeyboardButton(text, callback_data=text)] for text in top]
        keyboard.append([InlineKeyboardButton("✏ Ввести вручную", callback_data='manual')])
        update.message.reply_text("🏙️ Выберите город:", reply_markup=InlineKeyboardMarkup(keyboard))
        return CITY_INLINE

    elif current_col == 'S':
        top = get_top_by_column('S')
        keyboard = [[InlineKeyboardButton(text, callback_data=text)] for text in top]
        keyboard.append([InlineKeyboardButton("✏ Ввести вручную", callback_data='manual')])
        update.message.reply_text("💵 Выберите стоимость:", reply_markup=InlineKeyboardMarkup(keyboard))
        return COST_INLINE

    elif current_col == 'T':
        top = get_top_by_column('T')
        keyboard = [[InlineKeyboardButton(text, callback_data=text)] for text in top]
        keyboard.append([InlineKeyboardButton("✏ Ввести вручную", callback_data='manual')])
        update.message.reply_text("🚚 Выберите доставку:", reply_markup=InlineKeyboardMarkup(keyboard))
        return DELIVERY_INLINE

    elif current_col == 'U':
        top = get_top_by_column('U')
        keyboard = [[InlineKeyboardButton(text, callback_data=text)] for text in top]
        keyboard.append([InlineKeyboardButton("✏ Ввести вручную", callback_data='manual')])
        update.message.reply_text("🔢 Выберите № заказа:", reply_markup=InlineKeyboardMarkup(keyboard))
        return ORDER_INLINE

    elif current_col == 'V':
        top = get_top_by_column('V')
        keyboard = [[InlineKeyboardButton(text, callback_data=text)] for text in top]
        keyboard.append([InlineKeyboardButton("✏ Ввести вручную", callback_data='manual')])
        update.message.reply_text("🔐 Выберите серийный номер:", reply_markup=InlineKeyboardMarkup(keyboard))
        return SERIAL_INLINE

    update.message.reply_text(f"🛠️ Необработанная колонка: {current_col}")
    return ConversationHandler.END



def get_fio(update: Update, context: CallbackContext) -> int:
    context.user_data['FIO'] = update.message.text
    return next_step(update, context)

def handle_inline(update: Update, context: CallbackContext, key: str, next_state: int) -> int:
    query = update.callback_query
    value = query.data
    query.answer()

    if value == 'manual':
        context.bot.send_message(chat_id=query.message.chat_id, text="✏ Введите вручную:")
        return next_state
    else:
        context.user_data[key] = value
        return next_step(update, context)

def get_phone(update: Update, context: CallbackContext) -> int:
    context.user_data['Telefon'] = update.message.text
    return next_step(update, context)

def get_city(update: Update, context: CallbackContext) -> int:
    context.user_data['Gorod'] = update.message.text
    return next_step(update, context)

def get_track(update: Update, context: CallbackContext) -> int:
    context.user_data['TrekNomer'] = update.message.text
    return next_step(update, context)

def get_cost(update: Update, context: CallbackContext) -> int:
    context.user_data['Price'] = update.message.text
    return next_step(update, context)

def get_delivery(update: Update, context: CallbackContext) -> int:
    context.user_data['Dostavka'] = update.message.text
    return next_step(update, context)

def get_order(update: Update, context: CallbackContext) -> int:
    context.user_data['NomerZakaza'] = update.message.text
    return next_step(update, context)

def get_serial(update: Update, context: CallbackContext) -> int:
    context.user_data['SerNom'] = update.message.text
    return next_step(update, context)

def get_comment(update: Update, context: CallbackContext) -> int:
    context.user_data['Komment'] = update.message.text
    update.message.reply_text("✅ Все данные собраны!", reply_markup=ReplyKeyboardRemove())
    save_to_sheet(context)
    return ConversationHandler.END

# CallbackQueryHandlers для inline кнопок
def phone_inline(update: Update, context: CallbackContext) -> int:
    return handle_inline(update, context, 'Telefon', PHONE)

def city_inline(update: Update, context: CallbackContext) -> int:
    return handle_inline(update, context, 'Gorod', CITY)

def cost_inline(update: Update, context: CallbackContext) -> int:
    return handle_inline(update, context, 'Price', COST)

def delivery_inline(update: Update, context: CallbackContext) -> int:
    return handle_inline(update, context, 'Dostavka', DELIVERY)

def order_inline(update: Update, context: CallbackContext) -> int:
    return handle_inline(update, context, 'NomerZakaza', ORDER)

def serial_inline(update: Update, context: CallbackContext) -> int:
    return handle_inline(update, context, 'SerNom', SERIAL)



def save_to_sheet(context: CallbackContext) -> None:
    data = context.user_data
    ws = sheet.worksheet('Операции')
    row = data.get('row', 4)

    def val(k): return [[data.get(k, '')]]

    ws.update(f'B{row}', val('DD MM GGGG'))      # Дата
    ws.update(f'C{row}', val('Magazin'))         # Магазин
    ws.update(f'D{row}', val('Oper'))            # Операция
    ws.update(f'G{row}', val('Tovar'))           # Наименование
    ws.update(f'H{row}', val('Kol'))             # Кол-во
    ws.update(f'I{row}', val('Zabor'))           # Поставщик
    ws.update(f'J{row}', val('FIO'))             # ФИО
    ws.update(f'K{row}', val('Telefon'))         # Телефон
    ws.update(f'L{row}', val('Gorod'))           # Город
    ws.update(f'O{row}', val('TrekNomer'))       # Трек
    ws.update(f'S{row}', val('Price'))           # Стоимость
    ws.update(f'T{row}', val('Dostavka'))        # Доставка
    ws.update(f'U{row}', val('NomerZakaza'))     # № заказа
    ws.update(f'V{row}', val('SerNom'))          # Серийник
    ws.update(f'W{row}', val('NUMBERTEXT'))      # Число прописью
    ws.update(f'X{row}', val('Summa'))           # Итого
    ws.update(f'Y{row}', val('Komment'))         # Комментарий


def main():
    print("⏳ Запуск финального бота...")
    try:
        updater = Updater(TOKEN)
        dp = updater.dispatcher
        dp.add_handler(CommandHandler("start", start))
        updater.start_polling()
        print("🚀 Бот запущен. Готов к приёму команд.")
        updater.idle()
    except Exception as e:
        print(f"❌ Ошибка при запуске: {e}")


if __name__ == '__main__':
    main()
