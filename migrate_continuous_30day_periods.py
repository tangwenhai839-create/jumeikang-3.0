"""按第1期入营日连续划分30天一期，并重归属早晚体重。"""

import argparse
import sqlite3

import models


parser = argparse.ArgumentParser()
parser.add_argument('--db', default=models.DB_PATH)
parser.add_argument('--reference-date', default=None)
args = parser.parse_args()

models.DB_PATH = args.db
models.init_db()

connection = sqlite3.connect(args.db)
connection.row_factory = sqlite3.Row
users = connection.execute('''
    SELECT id, name FROM users
    WHERE period_count>1
    ORDER BY id
''').fetchall()
connection.close()

results = []
for user in users:
    result = models.apply_continuous_period_schedule(
        user['id'], reference_date=args.reference_date, reassign_weights=True,
    )
    results.append(result)
    print(
        'PERIOD_30DAY', result['name'],
        f"current={result['active_period'] or 'overflow'}",
        f"calculated={result['calculated_period']}",
        f"morning_moved={result['moved_morning']}",
        f"evening_moved={result['moved_evening']}",
        f"outside={result['outside_records']}",
    )

connection = sqlite3.connect(args.db)
integrity = connection.execute('PRAGMA integrity_check').fetchone()[0]
active_above_one = connection.execute(
    "SELECT COUNT(*) FROM enrollment_periods WHERE status='active' AND period_number>1"
).fetchone()[0]
connection.close()
assert integrity == 'ok'
print(f'CONTINUOUS_30DAY_MIGRATION_OK users={len(results)} active_above_one={active_above_one} integrity={integrity}')
