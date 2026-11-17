"""一次性把当前住宿安排写入新建的活动期次快照。"""

import argparse
import sqlite3


parser = argparse.ArgumentParser()
parser.add_argument("--weight-db", required=True)
parser.add_argument("--lodging-db", required=True)
args = parser.parse_args()


lodging = sqlite3.connect(f"file:{args.lodging_db}?mode=ro", uri=True)
lodging.row_factory = sqlite3.Row
assignments = lodging.execute('''
    SELECT r.camp_user_id, r.exclusive_use, room.id AS room_id,
           room.room_number, room.room_type, room.has_air_conditioner
    FROM residents r
    JOIN rooms room ON room.id=r.room_id
    WHERE r.status='CHECKED_IN' AND r.camp_user_id IS NOT NULL
''').fetchall()
lodging.close()

weight = sqlite3.connect(args.weight_db)
weight.row_factory = sqlite3.Row
updated = 0
for assignment in assignments:
    cursor = weight.execute('''
        UPDATE enrollment_periods SET
            room_id=?, room_number=?, room_type=?, has_air_conditioner=?,
            exclusive_use=?, updated_at=datetime('now','localtime')
        WHERE user_id=? AND status='active'
    ''', (
        assignment['room_id'], assignment['room_number'], assignment['room_type'],
        int(bool(assignment['has_air_conditioner'])),
        int(bool(assignment['exclusive_use'])), assignment['camp_user_id'],
    ))
    updated += cursor.rowcount
weight.commit()
integrity = weight.execute("PRAGMA integrity_check").fetchone()[0]
weight.close()
print(f"PERIOD_ACCOMMODATION_SYNC_OK updated={updated} integrity={integrity}")
