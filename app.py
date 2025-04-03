
from flask import Flask, request, jsonify
from flask_cors import CORS
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from num2words import num2words

app = Flask(__name__)
CORS(app)

scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
creds = ServiceAccountCredentials.from_json_keyfile_name('creds.json', scope)
client = gspread.authorize(creds)
sheet = client.open_by_key('1y8vXc06xSGcOdaYYxIKQIaNkVBMJe8-qPBXyNyUujr8').worksheet('Операции')

@app.route('/submit', methods=['POST'])
def submit():
    data = request.get_json()
    row = len(sheet.col_values(1)) + 1

    def num(x): return float(x.replace(",", ".")) if x else 0
    price = num(data.get("price", "0"))
    dostavka = num(data.get("dostavka", "0"))
    summa = price + dostavka
    words = num2words(summa, lang='ru').replace(" и", "").replace(",", "")

    sheet.update(f'B{row}:Z{row}', [[
        data.get("date"), data.get("magazin"), data.get("oper"), "", data.get("tovar"), "", "", data.get("kol"),
        data.get("zabor"), data.get("fio"), data.get("telefon"), data.get("gorod"), "", "", data.get("trek"),
        "", "", "", price, dostavka, data.get("zakaz"), data.get("sernom"), "", words, summa, data.get("komment"), ""
    ]])

    return jsonify({"status": "ok"})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
