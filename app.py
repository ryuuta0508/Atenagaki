import os
import io
from flask import Flask, render_template, request, jsonify, send_file
from google.oauth2 import service_account
from googleapiclient.discovery import build
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.pagesizes import portrait
from reportlab.lib.units import mm

font_path = r"font\ZenAntique-Regular.ttf"
font_name = "zen_antique"

pdfmetrics.registerFont(TTFont(font_name,font_path))

##sheet id 1JkXjOgzII2-XkB6XUEBGyQ2w9g96jLkHyVfQb4BsIeA
app = Flask(__name__)
KEY_FILE = r'key\atenagaki-5ff2e53418b1.json'
SCOPES = ['https://www.googleapis.com/auth/spreadsheets.readonly']

size_dic = {
    "NAGA3": (120*mm, 235*mm),
    "KAKU2": (240*mm, 332*mm)
}

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
        "col_map": {"name": 0, "address": 1, "company": 2, "department":3,"post":4}
        "env_size": NAGA3 $$ KAKU2
    }
    """
    print("DEBUG : app.py fetch_data")

    req = request.json
    spreadsheet_id = req.get('spreadsheet_id')
    sheet_name = req.get('sheet_name',"Sheet1")
    start_row = int(req.get('start_row', 1))
    end_row = int(req.get('end_row', 100))
    col_map = req.get('col_map') # {"name": 0, "address": 1, "company": 2, "department":3, "post":4} 形式
    size_tup = size_dic[req.get('env_size')]

    try:
        service = get_sheets_service()
        range_name = f"{sheet_name}!A:Z"
        result = service.spreadsheets().values().get(
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
                "department": get_val(col_map['department']),
                "post": get_val(col_map['post'])
            }

            if item["name"]:
                print_data.append(item)
        print("CHECK POINT : app.py fetch_data created print data")
        print(f"debug : print_data = {print_data}")
        
        pdf_buffer = io.BytesIO()
        c = canvas.Canvas(pdf_buffer, pagesize=size_tup)

        for item in print_data:
            # --- 描画ロジック
            # もし[役職の文字数] <= 4
            # ・中央に役職を書く＝＞ケツのY座標取得
            # ・役職の下に名前を書く＝＞右隣のX座標を取得
            # でなければ
            # ・中央に名前を書く＝＞右隣のX座標を取得
            # ・名前の右に役職を書く＝＞右隣のX座標を取得
            # 右に部署名を書く＝＞右隣のX座標を取得
            # 右に会社名を書く
            # 右端に住所を書く

            #役職名
            #4文字以下 => 名前の上
            #5文字以上 => 名前の右
            if len(item["post"]) <= 4:
                #役職
                result = draw_vertical_text(c,
                            item["post"],
                            size_tup[0]//24*12,
                            size_tup[1]//24*20,
                            font_name,
                            20
                            ) 
                #名前
                result = draw_vertical_text(
                            c,
                            item["name"] + "様",
                            size_tup[0]//24*12,
                            result[1] - result[2],
                            font_name,
                            50
                            )
            else:
                #名前
                result = draw_vertical_text(
                            c,
                            item["name"] + "様",
                            size_tup[0]//24*12,
                            size_tup[1]//24*18,
                            font_name,
                            50
                                )
                #役職
                result = draw_vertical_text(
                            c,
                            item["post"],
                            result[0],
                            size_tup[1]//24*20,
                            font_name,
                            20
                            )

            #部署名
            result = draw_vertical_text(
                        c,
                        item["department"],
                        result[0],
                        size_tup[1]//24*19,
                        font_name,
                        20
                        )
            #会社名
            result = draw_vertical_text(
                        c,
                        item["company"],
                        result[0] + result[2]//2,
                        size_tup[1]//24*20,
                        font_name,
                        25
                        )
            
            #住所
            result = draw_vertical_text(
                        c,
                        convert_digit_h2k(item["address"]),
                        size_tup[0]//24*22,
                        size_tup[1]//24*21 + result[2],
                        font_name,
                        20
                        )

            c.showPage()
            
        c.save()
        pdf_buffer.seek(0)

        return send_file(
            pdf_buffer,
            mimetype="application/pdf",
            as_attachment=False
        )

    except Exception as e:
            # 詳細なエラー内容をプリントする
            print("---------- ERROR DETAILS ----------")
            print(e)
            print("-----------------------------------")
            return jsonify({"error": str(e)}), 500
    
def convert_digit_h2z(text:str):
    """
    半角数字を全角数字に変換
    """
    trans_table = str.maketrans("0123456789","０１２３４５６７８９")

    return text.translate(trans_table)

def convert_digit_h2k(input:str):
    """
    全角数字を漢数字に変換
    """
    trans_table = str.maketrans("０１２３４５６７８９","〇一二三四五六七八九")

    text = convert_digit_h2z(input)
    return text.translate(trans_table)

def draw_vertical_text(c,text,x,y,font_name,font_size,line_spacing=1.2):
    """
    指定座標(x,y)を起点にした方向の縦書きで描画。
    return:ケツのY座標
    
    :param c: canvasオブジェクト
    :param text: 描画する文字列
    :param x: 起点X
    :param y: 起点Y
    :param font_name: 使用するフォント名
    :param font_size: 使用するフォントサイズ
    :param line_spacing: 行間
    """
    c.setFont(font_name,font_size)
    #全角文字の幅を取得
    sample_width = c.stringWidth("あ", font_name, font_size)
    offset_x = x - (sample_width / 2)

    # 文字ごとの幅
    char_step = font_size * line_spacing

    # 一文字ずつ処理
    current_y = y
    for char in text:
        # 特殊記号置換
        if char in "ー－-": # 長音やハイフン
            # 90度回転させて描画
            c.saveState()
            # 文字の中心を軸に回転させるための補正
            c.translate(x - font_size * 0.4, current_y + font_size * 1)
            c.rotate(-90)
            c.drawString(0, 0, "ー" if char == "ー" else "—") 
            c.restoreState()  
        elif char in "（）()": # 括弧
            c.saveState()
            c.translate(offset_x + font_size * 0.8, current_y + font_size * 0.2)
            c.rotate(-90)
            c.drawString(0, 0, char)
            c.restoreState()
        elif char in "。、": # 句読点（右上に寄せる）
            c.drawString(offset_x + font_size * 0.4, current_y + font_size * 0.4, char)
        else:
            # 通常の文字
            c.drawString(offset_x, current_y, char)
        # Y座標を次に進める（ReportLabは下が0なのでマイナスする）
        current_y -= char_step
    return x + sample_width, current_y - char_step, sample_width


if __name__ == '__main__':
    app.run(debug=True, port=5000)