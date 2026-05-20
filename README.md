# PBZ Bank Reader

A small local Flask tool for reading PBZ bank statements and generating spending summaries, charts, Excel reports and in case you use PostgreSQL you can also add the uploads to your database by filling out your local database info.

## Features

- Upload PBZ statements
- Parse transaction data
- Categorize expenses
- Generate spending charts
- Upload data to your local database
- Export an Excel report
- Runs locally for privacy

## Setup

```bash
pip install -r requirements.txt
python app.py
```

Then open:

'''text
http://127.0.0.1:5000
'''

## Privacy

This app is intended to run locally on the user's machine. It does not intentionally send uploaded statements or transaction data to any external server.

Users are responsible for keeping their own financial files, generated reports, database files, and credentials private.

## Database Notice

Database support is optional and intended only for local use. If users enable PostgreSQL storage, the database runs under their own control and responsibility. This project does not provide hosted storage and does not collect or receive user banking data.

## Disclaimer

This project is provided as-is for personal finance analysis and educational purposes. It is not financial, legal, accounting, or tax advice. Results may be inaccurate or incomplete, and users are responsible for verifying their own data before making decisions.

The author is not responsible for any loss, damage, incorrect categorization, incorrect report, privacy issue, or other consequence resulting from use of this software.

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.
