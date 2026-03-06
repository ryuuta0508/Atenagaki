#郵便番号は別で調整できるようにする
#1セットごとに別のPDFにする
import os
import io
import zipfile
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
    }
    """
    print("DEBUG : app.py fetch_data")

    req = request.json
    spreadsheet_id = req.get('spreadsheet_id')
    sheet_name = req.get('sheet_name',"Sheet1")
    start_row = int(req.get('start_row', 1))
    end_row = int(req.get('end_row', 100))
    col_map = req.get('col_map') # {"name": 0, "address": 1, "company": 2, "department":3, "post":4} 形式

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
                "post": get_val(col_map['post']),
                "zip": get_val(col_map['zip']).replace("-","")
            }

            if item["name"]:
                print_data.append(item)
        print("CHECK POINT : app.py fetch_data created print data")
        print(f"debug : print_data = {print_data}")

    except Exception as e:
            print("---------- ERROR DETAILS ----------")
            print(e)
            print("-----------------------------------")
            return jsonify({"error": str(e)}), 500

    return jsonify(print_data) #印刷するデータだけを返す
    
@app.route('/generate_preview')
def generate_preview():
    #URL末尾のパラメータを取得(/generate_preview?name=XXX&address=XXX)
    name = request.args.get("name","")
    address = request.args.get("address","")
    company = request.args.get("company","")
    department = request.args.get("department","")
    post = request.args.get("post","")
    zip = request.args.get("zip","")
    env_size = request.args.get("env_size","NAGA3")
    raw_font_size = request.args.get("font_size", "100")
    try:
        # 文字列を数値に変換し、100% = 1.0 倍とする
        font_factor = float(raw_font_size) / 100.0
    except:
        font_factor = 1.0
    show_sender = request.args.get("show_sender","")
    sender_name = request.args.get("sender_name","")
    sender_address = request.args.get("sender_address","")
    sender_company = request.args.get("sender_company","")
    sender_zip = request.args.get("sender_zip","")

    size_tup = size_dic.get(env_size, size_dic['NAGA3'])
    pdf_buffer = io.BytesIO()
    c = canvas.Canvas(pdf_buffer, pagesize=size_tup)

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
    if len(post) <= 4:
        #役職
        result = draw_vertical_text(c,
                    post,
                    size_tup[0]//24*12,
                    size_tup[1]//24*20,
                    font_name,
                    20* font_factor
                    ) 
        #名前
        result = draw_vertical_text(
                    c,
                    name + "様",
                    size_tup[0]//24*12,
                    result[1] - result[2],
                    font_name,
                    50* font_factor
                    )
    else:
        #名前
        result = draw_vertical_text(
                    c,
                    name + "様",
                    size_tup[0]//24*12,
                    size_tup[1]//24*18,
                    font_name,
                    50* font_factor
                    )
        #役職
        result = draw_vertical_text(
                    c,
                    post,
                    result[0],
                    size_tup[1]//24*20,
                    font_name,
                    20* font_factor
                    )
    #部署名
    result = draw_vertical_text(
                c,
                department,
                result[0],
                size_tup[1]//24*19,
                font_name,
                25* font_factor
                )
    #会社名
    result = draw_vertical_text(
                c,
                company,
                result[0] + result[2]//2,
                size_tup[1]//24*20,
                font_name,
                25* font_factor
                )
    #住所
    result = draw_vertical_text(
                c,
                convert_digit_h2k(address),
                size_tup[0]//24*23,
                result[3] + result[2] + 1.2,
                font_name,
                25* font_factor
                )
    #郵便番号
    result = draw_horizontal_text(
        c,
        zip,
        size_tup[0]//24*22,
        result[3] + result[2]*2,
        font_name,
        20* font_factor,
        line_spacing=1,
        align="bottom"
        )

    c.showPage()#宛名欄
    if show_sender:
        result = draw_vertical_text(
            c,
            sender_name,
            size_tup[0]//24*11,
            size_tup[1]//24*4,
            font_name,
            30* font_factor,
            align="bottom"
            )
        result = draw_vertical_text(
            c,
            sender_company,
            size_tup[0]//24*13,
            size_tup[1]//24*4,
            font_name,
            20* font_factor,
            align="bottom"
            )
        result = draw_vertical_text(
            c,
            convert_digit_h2k(sender_address),
            result[0],
            size_tup[1]//24*4,
            font_name,
            20* font_factor,
            align="bottom"
            )
        result = draw_horizontal_text(
            c,
            sender_zip,
            size_tup[0]//24*12,
            result[3] + result[2]*3,
            font_name,
            15* font_factor,
            line_spacing=1,
            align="center"
            )


    c.save()
    pdf_buffer.seek(0)

    return send_file(
        pdf_buffer,
        mimetype="application/pdf",
    )

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

def draw_vertical_text(c,text,x,y,font_name,font_size,line_spacing=1.2, align="top"):
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
    :param align
    """
    c.setFont(font_name,font_size)
    #全角文字の幅を取得
    sample_width = c.stringWidth("あ", font_name, font_size)
    offset_x = x - (sample_width / 2)

    # 文字ごとの幅
    char_step = font_size * line_spacing

    #文全体の長さ
    total_height = (len(text) - 1) * char_step + font_size

    # 一文字ずつ処理
    # --- align設定に基づいて開始Y座標(current_y)を補正 ---
    if align == "top":
        current_y = y
    elif align == "center":
        current_y = y + (total_height / 2) - font_size # 起点を中心に
    elif align == "bottom":
        current_y = y + total_height - font_size # 指定したy
    head_y = current_y
        
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
    return x + sample_width, current_y - char_step, sample_width, head_y

def draw_horizontal_text(c,text,x,y,font_name,font_size,line_spacing=1.2, align="top"):
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
    :param align
    """
    c.setFont(font_name,font_size)
    #全角文字の幅を取得
    sample_height = c.stringWidth("あ", font_name, font_size)
    offset_y = y

    # 文字ごとの幅
    char_step = font_size * line_spacing

    #文全体の長さ
    total_width = c.stringWidth(text, font_name, font_size) + (len(text) - 1) * line_spacing

    # 一文字ずつ処理
    # --- align設定に基づいて開始X座標(current_X)を補正 ---
    if align == "top":
        current_x = x
    elif align == "center":
        current_x = x - (total_width / 2) - font_size # 起点を中心に
    elif align == "bottom":
        current_x = x - total_width - font_size # 指定したy
        
    for char in text:
        # 通常の文字
        c.drawString(current_x, offset_y, char)
        # X座標を次に進める
        current_x += char_step
    return current_x - char_step, y + sample_height, sample_height

if __name__ == '__main__':
    app.run(debug=True, port=5000)