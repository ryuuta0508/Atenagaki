import os
from flask import Flask, render_template, request, jsonify
from google.oauth2 import service_account
from googleapiclient.discovery import build

##sheet id 1JkXjOgzII2-XkB6XUEBGyQ2w9g96jLkHyVfQb4BsIeA
app = Flask(__name__)
KEY_FILE = 'atenagaki-c787416ab74f.json'
SCOPES = ['https://www.googleapis.com/auth/spreadsheets.readonly']

def get_sheets_service():
    """Google Sheets APIサービスオブジェクト作成"""
    creds = service_account.Credentials.from_service_account_file(KEY_FILE,scopes=SCOPES)
    return build('sheets','v4',credentials=creds)

@app.route('/')
def index():
    return render_template('index.html')


@app.route('/fetch_data', methods=['POST'])
def fetch_data():
    """
    UIから送信された情報を元にデータを取得・整形する
    リクエストボディ例:
    {
        "spreadsheet_id": "1abc123...",
        "sheet_name": "シート1",
        "start_row": 2,
        "end_row": 10,
        "col_map": {"name": 0, "address": 1, "company": 2, "title":3}
    }
    """
    req = request.json
    spreadsheet_id = req.get('spreadsheet_id')
    sheet_name = req.get('sheet_name',"Sheet1")
    start_row = int(req.get('start_row', 1))
    end_row = int(req.get('end_row', 100))
    col_map = req.get('col_map') # {"name": 0, "address": 1, "company": 2, "title":3} 形式

    try:
        service = get_sheets_service()
        range_name = f"{sheet_name}!A:Z"
        result = service.spreadsheets().value().get(
            spreadsheetId=spreadsheet_id, range=range_name
        ).execute()

        rows = result.get('values',[])
        if not rows:
            return jsonify({"error":"データが見つかりませんでした"}),404

        print_data = []

        for i in range(start_row - 1, min(len(rows), end_row)):
            row = rows[i]

            def get_val(idx):
                return row[idx] if len(row) > idx else ""
            
            item = {
                "name": get_val(col_map['name']),
                "address": get_val(col_map['address']),
                "company": get_val(col_map['company']),
                "title": get_val(col_map['title'])
            }

            if item["name"]:
                print_data.append(item)
        
        return jsonify(print_data)

    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5000)