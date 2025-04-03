import os
import logging
from telegram import Update
from telegram.ext import Updater, CommandHandler, CallbackContext
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

# Токены
TOKEN = "7571543010:AAGGdsowEAJOE4sVCWMNKFslo4vNSoU3SjY"
GOOGLE_SHEET_ID = "1y8vXc06xSGcOdaYYxIKQIaNkVBMJe8-qPBXyNyUujr8"

# Настройка логирования
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Авторизация в Google Sheets API
def authenticate_google_sheets():
    creds = Credentials.from_service_account_file("creds.json", scopes=["https://www.googleapis.com/auth/spreadsheets"])
    service = build('sheets', 'v4', credentials=creds)
    return service.spreadsheets()

# Команда старт
def start(update: Update, context: CallbackContext) -> None:
    update.message.reply_text('Привет! Давайте начнем.')

# Команда для записи данных в таблицу
def write_to_sheet(update: Update, context: CallbackContext) -> None:
    service = authenticate_google_sheets()
    values = [
        ['Дата', 'Магазин', 'Операция'],
        ['2025-04-01', 'Gadgetlab24', 'Продажа']
    ]
    body = {'values': values}
    service.values().update(spreadsheetId=GOOGLE_SHEET_ID, range="Sheet1!A1", body=body, valueInputOption="RAW").execute()
    update.message.reply_text("Данные добавлены в таблицу.")

# Основная функция
def main() -> None:
    updater = Updater(TOKEN)
    dispatcher = updater.dispatcher

    dispatcher.add_handler(CommandHandler("start", start))
    dispatcher.add_handler(CommandHandler("write", write_to_sheet))

    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()
