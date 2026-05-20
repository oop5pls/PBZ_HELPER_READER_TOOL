from Transactions import Transaction, TransactionList
from Database_handling import insert_into_db
from Database_creation import create_database
from Seaborn_graph_maker import make_seaborn_graph_daily, make_seaborn_graph_monthly, make_seaborn_pie_chart
from typing import List, Dict, Any
from flask import Flask, request, jsonify, send_from_directory, abort
from flask_cors import CORS
import os
import pandas as pd
import matplotlib
import xlsxwriter
import io
import base64
import webbrowser
import threading
import time
import signal

INACTIVITY_LIMIT_SECONDS = 120
last_upload_time = time.monotonic()


matplotlib.use('agg')  # non-interactive backend
app = Flask(__name__, static_folder='.', static_url_path='')
CORS(app)  # Enable CORS for all routes

UPLOAD_FOLDER = './uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

REPORT_DIR = './reports'
os.makedirs(REPORT_DIR, exist_ok=True)


@app.route('/reports/download/<path:filename>')
def download_report(filename):
    try:
        return send_from_directory(REPORT_DIR, filename, as_attachment=True)
    except Exception as e:
        print(f"Error serving file {filename}:", e)
        abort(404, description="File not found")


@app.route('/')
def index():
    # serve the index.html in the same folder (convenient for quick testing)
    return send_from_directory('.', 'index.html')


@app.route('/upload', methods=['POST'])
def upload_file() -> Any:
    global last_upload_time
    last_upload_time = time.monotonic()

    if 'file' not in request.files:
        return jsonify({"error": "No file part"}), 400

    file = request.files.getlist('file')[0]  # limit to first file
    # will be updated to handle multiple files at a time in the future
    successful_uploads = []
    results = []
    graph_html_list = []
    graph_stats = []
    if file.filename != '':
        filepath = os.path.join(UPLOAD_FOLDER, file.filename)
        file.save(filepath)
        print(f"File uploaded successfully to: {filepath}")
        successful_uploads.append(
            {"filename": file.filename, "path": filepath})

        # Only parse Excel files for graphs
        if file.filename.lower().endswith(('.xls', '.xlsx', '.csv')):
            tx_list, stats, report_df = read_excel_file(filepath)
            # returns TrascationList ,stats is dict with avg_daily, total_spent, total_earned
            # additionally UPDATES DATABASE with parsed transactions
            # --- make sure dates are plain date objects so Excel doesn't show time ---
            # generate graphs (pie first for layout)
            pie_html, piebuf = make_seaborn_pie_chart(tx_list)
            daily_html, dailybuf = make_seaborn_graph_daily(tx_list)
            monthly_html, monthlybuf = make_seaborn_graph_monthly(tx_list)

            for h in (pie_html, daily_html, monthly_html):
                if h:
                    graph_html_list.append(h)
            # remember stats for this file so frontend can display after pie chart
            graph_stats.append(stats)
            results.append({"transactions": len(
                tx_list.transactions), **stats})

            # out of graphs and the report dataframe we will create a report.xlsx file with the graphs and the categorized transactions for the user to download
            report_filename = f"report_[{file.filename.strip()}].xlsx"

            make_excel_report(report_filename, report_df,
                              piebuf, dailybuf, monthlybuf)

        else:
            proc = process_file(filepath)
            results.append(proc)

    try:
        os.remove(filepath)
        print(f"Deleted sensitive file: {filepath}")
    except Exception as e:
        print(f"Could not delete file: {e}")

    response = {
        "message": "Files uploaded successfully",
        "files": successful_uploads,
        "processing": results,
        "graph_htmls": graph_html_list,
        "report": report_filename if graph_html_list else None
    }
    if graph_stats:
        response["graph_stats"] = graph_stats
    return jsonify(response)


# reading excel file------------------------------------------------------------------------------------------------------------------------------------------
def get_dataframe(filepath: str) -> tuple[pd.DataFrame, int]:
    try:
        # Read everything without assuming a header
        df_raw = pd.read_excel(filepath, header=None)

        # Find the row containing 'DATUM'
        header_idx = None
        for i in range(min(20, len(df_raw))):
            first = str(df_raw.iat[i, 0]).strip().upper(
            ) if not pd.isna(df_raw.iat[i, 0]) else ""
            if first == 'DATUM':
                header_idx = i
                break

        if header_idx is None:
            header_idx = 0  # fallback

        # Re-read with detected header
        df = pd.read_excel(filepath, header=header_idx)
        return df, header_idx + 1  # return start_row (first data row)

    except Exception as e:
        print(f"Error: {e}")
        return None, 0


def clean_data(df: pd.DataFrame) -> pd.DataFrame:
    df['DATUM'] = pd.to_datetime(df['DATUM'], dayfirst=True, errors='coerce')
    df['DATUM'] = df['DATUM'].dt.date
    df['IZNOS'] = pd.to_numeric(df['IZNOS'], errors='coerce')
    df['OPIS PLAĆANJA'] = df['OPIS PLAĆANJA'].str.strip().fillna('')
    df['VRSTA TRANSAKCIJE'] = df['VRSTA TRANSAKCIJE'].str.strip().fillna('')
    df['VALUTA'] = df['VALUTA'].str.strip().fillna('')
    df = df.dropna(subset=['DATUM', 'IZNOS'])
    return df


def read_excel_file(filepath: str) -> tuple[TransactionList, Dict[str, float], pd.DataFrame]:
    transactions = TransactionList()

    # get dataframe and starting row
    df, start_row = get_dataframe(filepath)
    # remove header rows and clean dataframe
    df = df.iloc[start_row:]
    df.reset_index(drop=True, inplace=True)
    df = clean_data(df)
    df = update_database(df)

    spent_money = 0.0
    earned_money = 0.0

    # New: accumulator for "average" computation and set of unique days
    avarage_daily_spend = 0.0   # sum of negative amounts that are > -200
    unique_days = set()

    # iterate all subsequent rows and try to parse (use itertuples to avoid Series indexing warnings)
    for i, row in enumerate(df.iloc[0:].itertuples(index=False, name=None), start=0):
        # row is a tuple: date, transaction_type, transaction_description, amount, currency,expense_type
        raw_date = row[0] if len(row) > 0 else None
        raw_type = row[1] if len(row) > 1 else ''
        raw_payment = row[2] if len(row) > 2 else ''
        raw_amount = row[3] if len(row) > 3 else None
        raw_currency = row[4] if len(row) > 4 else ''
        raw_category = row[5] if len(row) > 5 else None

        # periodic progress log
        processed = i - start_row + 1
        if processed % 100 == 0:
            print(f"Processed {processed} rows...")

        # parse date
        try:
            # use pandas to parse and coerce
            datetime_obj = pd.to_datetime(
                raw_date, dayfirst=True, errors='coerce')
            if pd.isna(datetime_obj):
                # skip rows that are not actual transaction rows
                continue
            date_obj = datetime_obj.date()
        except Exception as date_e:
            print(f"DATUM exception in row {i}:", date_e)
            continue

        # parse amount
        try:
            # handle strings with commas, spaces etc.
            if isinstance(raw_amount, str):
                cleaned = raw_amount.replace('\xa0', '').replace(
                    ' ', '').replace(',', '.')
            else:
                cleaned = raw_amount
            amount_float = float(cleaned)
        except Exception as amount_e:
            print(f"IZNOS error in row {i}:", amount_e)
            continue

        # update totals
        if amount_float < 0:
            spent_money += abs(amount_float)
            # nested check requested: include only negatives larger than -200 (i.e. -200 < amount < 0)
            if amount_float > -200:
                avarage_daily_spend += amount_float   # keep negative sign
        else:
            earned_money += amount_float

        # record unique day
        unique_days.add(date_obj)

        trans_type = str(raw_type) if not pd.isna(raw_type) else ''
        payment_des = str(raw_payment) if not pd.isna(raw_payment) else ''
        currency = str(raw_currency) if not pd.isna(raw_currency) else ''
        category = str(raw_category) if not pd.isna(raw_category) else None

        transactions.addTransaction(Transaction(
            date_obj, trans_type, payment_des, amount_float, currency, category))

    print(f"Total spent money: {spent_money:.2f}")
    print(f"Total earned money: {earned_money:.2f}")

    # compute average per-day from avarage_daily_spend over unique days count
    try:
        num_days = len(unique_days)
        if num_days > 0:
            avarage_daily_spend_per_day = avarage_daily_spend / num_days
        else:
            avarage_daily_spend_per_day = 0.0
    except Exception as e:
        print("Error computing average daily spend:", e)
        avarage_daily_spend_per_day = 0.0

    print(
        f"Average daily spend (sum of negatives > -200 divided by unique days): {avarage_daily_spend_per_day:.2f}")

    stats = {
        "avg_daily": avarage_daily_spend_per_day,
        "total_spent": spent_money,
        "total_earned": earned_money
    }
    return transactions, stats, df


# read the Database handling comment
# the user inserts their own postgreSQL database credentials in the get_db_connection function if they want to use a database at all
# the excel files will be created regardless of database usage

# returns categorised dataframe for graphing, and number of rows inserted into database
def update_database(df: pd.DataFrame) -> pd.DataFrame:
    try:
        if not df.empty:
            print(f"Attempting to insert {len(df)} parsed rows into DB...")
            create_database()  # ensure table exists before inserting
            inserted, df = insert_into_db(df)
            print(f"Inserted {inserted} rows into bankingstatement table")
    except Exception as e:
        import traceback
        print("Error during database update:", e)
        traceback.print_exc()

    return df


# Transaction class to hold individual transaction data--------------------------------------------------------------------------------------------------------------------------------------

def process_file(filepath: str) -> Dict[str, Any]:
    try:
        with open(filepath, 'rb') as f:
            data = f.read()
    except Exception as e:
        return {"path": filepath, "error": str(e)}

    preview = data[:200].decode('utf-8', errors='replace')
    return {"path": filepath, "size": len(data), "preview": preview}


def make_excel_report(report_filename: str, report_df: pd.DataFrame, piebuf: io.BytesIO, dailybuf: io.BytesIO, monthlybuf: io.BytesIO) -> None:
    # out of graphs and the report dataframe we will create a report.xlsx file with the graphs and the categorized transactions for the user to download

    if 'DATUM' in report_df.columns:
        try:
            report_df['DATUM'] = pd.to_datetime(report_df['DATUM']).dt.date
        except Exception:
            pass

    full_path = os.path.join(REPORT_DIR, report_filename)

    with pd.ExcelWriter(full_path, engine='xlsxwriter') as writer:
        report_df.to_excel(
            writer, index=False, sheet_name='Categorized Transactions', header=True, startrow=1)
        ws_data = writer.sheets['Categorized Transactions']

        # adjust column widths for important fields
        ws_data.set_column('A:A', 15)
        ws_data.set_column('C:C', 40)
        ws_data.set_column('B:B', 15)
        ws_data.set_column('F:F', 50)

        ws_data.insert_image('J2', piebuf)
        ws_data.insert_image('J35', dailybuf)
        ws_data.insert_image('J65', monthlybuf)

# graph crafting----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------


def open_browser():
    webbrowser.open("http://127.0.0.1:5000")


def shutdown_after_inactivity():
    while True:
        time.sleep(5)
        inactive_for = time.monotonic() - last_upload_time

        if inactive_for >= INACTIVITY_LIMIT_SECONDS:
            print("No uploads for 2 minutes. Shutting down Flask server.")
            os.kill(os.getpid(), signal.SIGTERM)


if __name__ == '__main__':
    # disable reloader to avoid double-process / long restarts during debugging
    threading.Timer(1, open_browser).start()

    inactivity_thread = threading.Thread(
        target=shutdown_after_inactivity,
        daemon=True
    )
    inactivity_thread.start()
    app.run(host='127.0.0.1', port=5000, debug=False, use_reloader=False)
