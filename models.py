import sqlite3
import os
from datetime import datetime, date, timedelta
from contextlib import contextmanager

from config import DB_PATH, WEEK_START_DAY, LIVENESS_ENABLED


@contextmanager
def get_db():
    """获取数据库连接 (上下文管理器)"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA journal_mode=WAL')
    conn.execute('PRAGMA foreign_keys=ON')
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    """初始化数据库表结构"""
    with get_db() as db:
        db.executescript('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                phone TEXT DEFAULT '',
                initial_weight REAL DEFAULT 0,
                tice_weight REAL DEFAULT 0,
                note TEXT DEFAULT '',
                enroll_date TEXT DEFAULT '',
                period_count INTEGER DEFAULT 1,
                camp_status TEXT DEFAULT 'active',
                exit_date TEXT DEFAULT '',
                exit_note TEXT DEFAULT '',
                created_at TEXT DEFAULT (datetime('now','localtime'))
            );

            CREATE TABLE IF NOT EXISTS face_features (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL UNIQUE,
                feature BLOB,
                face_image TEXT DEFAULT '',
                created_at TEXT DEFAULT (datetime('now','localtime')),
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS weights (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                weigh_date TEXT NOT NULL,
                weight REAL NOT NULL,
                note TEXT DEFAULT '',
                recorded_at TEXT DEFAULT (datetime('now','localtime')),
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                UNIQUE(user_id, weigh_date)
            );

            CREATE TABLE IF NOT EXISTS evening_weights (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                weigh_date TEXT NOT NULL,
                weight REAL NOT NULL,
                recorded_at TEXT DEFAULT (datetime('now','localtime')),
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                UNIQUE(user_id, weigh_date)
            );

            CREATE TABLE IF NOT EXISTS enrollment_periods (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                period_number INTEGER NOT NULL,
                status TEXT NOT NULL DEFAULT 'planned',
                enroll_date TEXT DEFAULT '',
                planned_end_date TEXT DEFAULT '',
                exit_date TEXT DEFAULT '',
                initial_weight REAL DEFAULT 0,
                tice_weight REAL DEFAULT 0,
                coach_id INTEGER DEFAULT 0,
                exit_note TEXT DEFAULT '',
                room_id INTEGER DEFAULT 0,
                room_number TEXT DEFAULT '',
                room_type TEXT DEFAULT '',
                has_air_conditioner INTEGER DEFAULT 0,
                exclusive_use INTEGER DEFAULT 0,
                created_at TEXT DEFAULT (datetime('now','localtime')),
                updated_at TEXT DEFAULT (datetime('now','localtime')),
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                UNIQUE(user_id, period_number)
            );

            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS coaches (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                phone TEXT DEFAULT '',
                created_at TEXT DEFAULT (datetime('now','localtime'))
            );

            CREATE TABLE IF NOT EXISTS coach_face_features (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                coach_id INTEGER NOT NULL UNIQUE,
                feature BLOB,
                face_image TEXT DEFAULT '',
                created_at TEXT DEFAULT (datetime('now','localtime')),
                FOREIGN KEY (coach_id) REFERENCES coaches(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS coach_accounts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                coach_id INTEGER NOT NULL UNIQUE,
                username TEXT NOT NULL COLLATE NOCASE UNIQUE,
                password_hash TEXT DEFAULT '',
                role TEXT NOT NULL DEFAULT 'coach' CHECK(role IN ('admin', 'coach')),
                is_active INTEGER NOT NULL DEFAULT 1,
                last_login_at TEXT DEFAULT '',
                created_at TEXT DEFAULT (datetime('now','localtime')),
                updated_at TEXT DEFAULT (datetime('now','localtime')),
                FOREIGN KEY (coach_id) REFERENCES coaches(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS operation_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                account_id INTEGER,
                coach_id INTEGER,
                actor_username TEXT DEFAULT '',
                actor_name TEXT DEFAULT '',
                actor_role TEXT DEFAULT '',
                action TEXT NOT NULL,
                target_type TEXT DEFAULT '',
                target_id TEXT DEFAULT '',
                detail TEXT DEFAULT '',
                method TEXT DEFAULT '',
                path TEXT DEFAULT '',
                status_code INTEGER DEFAULT 0,
                ip_address TEXT DEFAULT '',
                created_at TEXT DEFAULT (datetime('now','localtime')),
                FOREIGN KEY (account_id) REFERENCES coach_accounts(id) ON DELETE SET NULL,
                FOREIGN KEY (coach_id) REFERENCES coaches(id) ON DELETE SET NULL
            );

            CREATE INDEX IF NOT EXISTS idx_weights_user_date
                ON weights(user_id, weigh_date);
            CREATE INDEX IF NOT EXISTS idx_weights_date
                ON weights(weigh_date);
            CREATE INDEX IF NOT EXISTS idx_periods_user_status
                ON enrollment_periods(user_id, status, period_number);
            CREATE INDEX IF NOT EXISTS idx_accounts_coach
                ON coach_accounts(coach_id);
            CREATE INDEX IF NOT EXISTS idx_operation_logs_created
                ON operation_logs(created_at DESC);
            CREATE INDEX IF NOT EXISTS idx_operation_logs_coach_created
                ON operation_logs(coach_id, created_at DESC);
        ''')

        # 兼容已有数据库: 自动补充缺失的列
        cols = [r['name'] for r in db.execute('PRAGMA table_info(users)').fetchall()]
        if 'tice_weight' not in cols:
            db.execute('ALTER TABLE users ADD COLUMN tice_weight REAL DEFAULT 0')
        if 'coach_id' not in cols:
            db.execute('ALTER TABLE users ADD COLUMN coach_id INTEGER DEFAULT 0')
        if 'enroll_date' not in cols:
            db.execute("ALTER TABLE users ADD COLUMN enroll_date TEXT DEFAULT ''")
        if 'period_count' not in cols:
            db.execute('ALTER TABLE users ADD COLUMN period_count INTEGER DEFAULT 1')
        if 'camp_status' not in cols:
            db.execute("ALTER TABLE users ADD COLUMN camp_status TEXT DEFAULT 'active'")
        if 'exit_date' not in cols:
            db.execute("ALTER TABLE users ADD COLUMN exit_date TEXT DEFAULT ''")
        if 'exit_note' not in cols:
            db.execute("ALTER TABLE users ADD COLUMN exit_note TEXT DEFAULT ''")
        db.execute("UPDATE users SET enroll_date=substr(created_at,1,10) WHERE coalesce(enroll_date,'')='' ")
        db.execute("UPDATE users SET period_count=1 WHERE period_count IS NULL OR period_count < 1")
        db.execute("UPDATE users SET camp_status='active' WHERE coalesce(camp_status,'')='' ")

        weight_cols = [r['name'] for r in db.execute('PRAGMA table_info(weights)').fetchall()]
        if 'note' not in weight_cols:
            db.execute("ALTER TABLE weights ADD COLUMN note TEXT DEFAULT ''")
        if 'period_id' not in weight_cols:
            db.execute('ALTER TABLE weights ADD COLUMN period_id INTEGER DEFAULT 0')

        evening_cols = [r['name'] for r in db.execute('PRAGMA table_info(evening_weights)').fetchall()]
        if 'period_id' not in evening_cols:
            db.execute('ALTER TABLE evening_weights ADD COLUMN period_id INTEGER DEFAULT 0')

        # 将旧的“报名期数”数字迁移为每一期一条记录。已知信息只放入第1期，
        # 其余期次保留为待安排，绝不编造未来入营日期。
        users = db.execute('SELECT * FROM users ORDER BY id').fetchall()
        for user in users:
            existing = db.execute(
                'SELECT COUNT(*) FROM enrollment_periods WHERE user_id=?', (user['id'],)
            ).fetchone()[0]
            if existing:
                continue
            total = max(1, int(user['period_count'] or 1))
            enroll_date = str(user['enroll_date'] or '')[:10]
            planned_end = ''
            if enroll_date:
                try:
                    planned_end = (date.fromisoformat(enroll_date) + timedelta(days=29)).isoformat()
                except ValueError:
                    planned_end = ''
            first_status = 'active' if user['camp_status'] == 'active' else 'completed'
            db.execute('''
                INSERT OR IGNORE INTO enrollment_periods
                    (user_id, period_number, status, enroll_date, planned_end_date,
                     exit_date, initial_weight, tice_weight, coach_id, exit_note)
                VALUES (?, 1, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                user['id'], first_status, enroll_date, planned_end,
                str(user['exit_date'] or '')[:10], float(user['initial_weight'] or 0),
                float(user['tice_weight'] or 0), int(user['coach_id'] or 0),
                str(user['exit_note'] or ''),
            ))
            for period_number in range(2, total + 1):
                db.execute('''
                    INSERT OR IGNORE INTO enrollment_periods (user_id, period_number, status)
                    VALUES (?, ?, 'planned')
                ''', (user['id'], period_number))

        for user in users:
            _schedule_period_dates(db, user['id'])

        # 旧体重没有期次信息，只能可靠归入唯一有明确入营日期的第1期。
        db.execute('''
            UPDATE weights SET period_id=(
                SELECT id FROM enrollment_periods p
                WHERE p.user_id=weights.user_id AND p.period_number=1
            ) WHERE coalesce(period_id,0)=0
        ''')
        db.execute('''
            UPDATE evening_weights SET period_id=(
                SELECT id FROM enrollment_periods p
                WHERE p.user_id=evening_weights.user_id AND p.period_number=1
            ) WHERE coalesce(period_id,0)=0
        ''')

        # 默认设置：活体开关
        db.execute('''
            INSERT INTO settings (key, value) VALUES ('liveness_enabled', ?)
            ON CONFLICT(key) DO NOTHING
        ''', ('1' if LIVENESS_ENABLED else '0',))
        db.execute('PRAGMA optimize')


# ─── 学员管理 ───────────────────────────────────────

PERIOD_STATUS_LABELS = {
    'planned': '待安排',
    'active': '在营',
    'completed': '已完成',
    'cancelled': '已取消',
}
PERIOD_DAYS = 30


def _default_period_end(enroll_date):
    if not enroll_date:
        return ''
    try:
        return (date.fromisoformat(str(enroll_date)[:10]) + timedelta(days=PERIOD_DAYS - 1)).isoformat()
    except (TypeError, ValueError):
        return ''


def _period_window(anchor_date, period_number):
    anchor = date.fromisoformat(str(anchor_date)[:10])
    start = anchor + timedelta(days=(int(period_number) - 1) * PERIOD_DAYS)
    end = start + timedelta(days=PERIOD_DAYS - 1)
    return start.isoformat(), end.isoformat()


def _schedule_period_dates(db, user_id, force=False):
    """以第1期入营日为基准，为每期生成连续30天的日期范围。"""
    first = db.execute('''
        SELECT enroll_date FROM enrollment_periods
        WHERE user_id=? AND period_number=1
    ''', (user_id,)).fetchone()
    if not first or not str(first['enroll_date'] or '')[:10]:
        return False
    anchor = str(first['enroll_date'])[:10]
    date.fromisoformat(anchor)
    periods = db.execute('''
        SELECT id, period_number, enroll_date, planned_end_date
        FROM enrollment_periods
        WHERE user_id=? AND status<>'cancelled'
        ORDER BY period_number
    ''', (user_id,)).fetchall()
    for period in periods:
        start, end = _period_window(anchor, period['period_number'])
        if force or not period['enroll_date'] or not period['planned_end_date']:
            db.execute('''
                UPDATE enrollment_periods
                SET enroll_date=?, planned_end_date=?,
                    updated_at=datetime('now','localtime')
                WHERE id=?
            ''', (start, end, period['id']))
    return True


def _sync_period_count(db, user_id, total_count):
    """让期次占位记录与报名总期数一致；历史期次只取消、不删除。"""
    total_count = max(1, int(total_count or 1))
    rows = db.execute('''
        SELECT id, period_number, status FROM enrollment_periods
        WHERE user_id=? ORDER BY period_number
    ''', (user_id,)).fetchall()
    started_numbers = [
        int(row['period_number']) for row in rows
        if row['status'] in ('active', 'completed')
    ]
    if started_numbers and total_count < max(started_numbers):
        raise ValueError('报名总期数不能少于已经开始的期次')

    by_number = {int(row['period_number']): row for row in rows}
    for period_number in range(1, total_count + 1):
        row = by_number.get(period_number)
        if row is None:
            db.execute('''
                INSERT INTO enrollment_periods (user_id, period_number, status)
                VALUES (?, ?, 'planned')
            ''', (user_id, period_number))
        elif row['status'] == 'cancelled':
            db.execute('''
                UPDATE enrollment_periods
                SET status='planned', updated_at=datetime('now','localtime')
                WHERE id=?
            ''', (row['id'],))

    db.execute('''
        UPDATE enrollment_periods
        SET status='cancelled', updated_at=datetime('now','localtime')
        WHERE user_id=? AND period_number>? AND status='planned'
    ''', (user_id, total_count))
    db.execute('UPDATE users SET period_count=? WHERE id=?', (total_count, user_id))
    _schedule_period_dates(db, user_id)

    active_count = db.execute('''
        SELECT COUNT(*) FROM enrollment_periods
        WHERE user_id=? AND status='active'
    ''', (user_id,)).fetchone()[0]
    planned_count = db.execute('''
        SELECT COUNT(*) FROM enrollment_periods
        WHERE user_id=? AND status='planned' AND period_number<=?
    ''', (user_id, total_count)).fetchone()[0]
    if not active_count and planned_count:
        db.execute("UPDATE users SET camp_status='pending' WHERE id=?", (user_id,))


def _period_closing_weight(db, user_id, period_number):
    """返回上一期结尾体重：该期最后一次早称体重。"""
    row = db.execute('''
        SELECT w.weight
        FROM weights w
        JOIN enrollment_periods p ON p.id=w.period_id
        WHERE p.user_id=? AND p.period_number=?
        ORDER BY w.weigh_date DESC, w.id DESC
        LIMIT 1
    ''', (user_id, int(period_number))).fetchone()
    return float(row['weight']) if row and row['weight'] is not None else None


def _period_initial_weight(db, user_id, period_number, fallback=0):
    if int(period_number) <= 1:
        return float(fallback or 0)
    closing = _period_closing_weight(db, user_id, int(period_number) - 1)
    return closing if closing is not None else float(fallback or 0)


def _period_start_weights(db, user_id, period_number, initial_fallback=0, tice_fallback=0):
    if int(period_number) <= 1:
        return float(initial_fallback or 0), float(tice_fallback or 0)
    closing = _period_closing_weight(db, user_id, int(period_number) - 1)
    if closing is not None:
        return closing, closing
    return float(initial_fallback or 0), float(tice_fallback or 0)


def _period_rows(db, user_id):
    rows = db.execute('''
        SELECT p.*, c.name AS coach_name,
               (SELECT w.weight FROM weights w WHERE w.period_id=p.id
                ORDER BY w.weigh_date, w.id LIMIT 1) AS first_weight,
               (SELECT w.weight FROM weights w WHERE w.period_id=p.id
                ORDER BY w.weigh_date DESC, w.id DESC LIMIT 1) AS latest_weight,
               (SELECT COUNT(*) FROM weights w WHERE w.period_id=p.id) AS weight_count
        FROM enrollment_periods p
        LEFT JOIN coaches c ON c.id=p.coach_id
        WHERE p.user_id=?
        ORDER BY p.period_number
    ''', (user_id,)).fetchall()
    result = []
    for row in rows:
        item = dict(row)
        item['status_label'] = PERIOD_STATUS_LABELS.get(item['status'], item['status'])
        first_weight = item.get('first_weight')
        latest_weight = item.get('latest_weight')
        initial_weight = float(item.get('initial_weight') or 0)
        basis = initial_weight or (float(first_weight) if first_weight is not None else 0)
        item['period_loss'] = (
            round(basis - float(latest_weight), 1)
            if basis and latest_weight is not None else None
        )
        item['has_air_conditioner'] = bool(item.get('has_air_conditioner'))
        item['exclusive_use'] = bool(item.get('exclusive_use'))
        result.append(item)
    return result


def get_user_periods(user_id):
    with get_db() as db:
        return _period_rows(db, user_id)


def _period_summary(periods, registered_total):
    active = next((p for p in periods if p['status'] == 'active'), None)
    planned = [p for p in periods if p['status'] == 'planned']
    completed = [p for p in periods if p['status'] == 'completed']
    cancelled = [p for p in periods if p['status'] == 'cancelled']
    focus = active or (planned[0] if planned else (completed[-1] if completed else None))
    return {
        'registered_periods': max(1, int(registered_total or 1)),
        'completed_periods': len(completed),
        'remaining_periods': len(planned),
        'cancelled_periods': len(cancelled),
        'current_period_number': int(focus['period_number']) if focus else None,
        'current_period_status': focus['status'] if focus else None,
        'current_period_status_label': focus['status_label'] if focus else '',
        'active_period_id': int(active['id']) if active else None,
        'next_period_number': int(planned[0]['period_number']) if planned else None,
    }


def _attach_periods(db, users):
    for user in users:
        periods = _period_rows(db, user['id'])
        user['periods'] = periods
        user['period_summary'] = _period_summary(periods, user.get('period_count'))
    return users


def get_active_period(user_id, db=None):
    owns_connection = db is None
    if owns_connection:
        connection = sqlite3.connect(DB_PATH)
        connection.row_factory = sqlite3.Row
    else:
        connection = db
    try:
        row = connection.execute('''
            SELECT * FROM enrollment_periods
            WHERE user_id=? AND status='active'
            ORDER BY period_number LIMIT 1
        ''', (user_id,)).fetchone()
        return dict(row) if row else None
    finally:
        if owns_connection:
            connection.close()


def update_current_period_accommodation(user_id, assignment=None):
    assignment = assignment or {}
    with get_db() as db:
        active = get_active_period(user_id, db)
        if not active:
            return False
        db.execute('''
            UPDATE enrollment_periods SET
                room_id=?, room_number=?, room_type=?, has_air_conditioner=?,
                exclusive_use=?, updated_at=datetime('now','localtime')
            WHERE id=?
        ''', (
            int(assignment.get('room_id') or 0), str(assignment.get('room_number') or ''),
            str(assignment.get('room_type') or ''),
            1 if assignment.get('has_air_conditioner') else 0,
            1 if assignment.get('exclusive_use') else 0, active['id'],
        ))
        return True


def start_next_period(user_id, enroll_date, coach_id, initial_weight, tice_weight):
    """将最早的待安排期次办理为在营。"""
    enroll_date = str(enroll_date or '')[:10]
    date.fromisoformat(enroll_date)
    with get_db() as db:
        if get_active_period(user_id, db):
            raise ValueError('该学员已有正在进行的期次')
        period = db.execute('''
            SELECT * FROM enrollment_periods
            WHERE user_id=? AND status='planned'
            ORDER BY period_number LIMIT 1
        ''', (user_id,)).fetchone()
        if not period:
            raise ValueError('该学员没有待入营期次，请先增加报名总期数')
        # 连续30天模式下优先使用系统已经计算好的期次开始日期。
        enroll_date = str(period['enroll_date'] or enroll_date)[:10]
        period_number = int(period['period_number'])
        new_initial, new_tice = _period_start_weights(
            db, user_id, period_number, initial_weight, tice_weight
        )
        db.execute('''
            UPDATE enrollment_periods SET
                status='active', enroll_date=?, planned_end_date=?, exit_date='',
                initial_weight=?, tice_weight=?, coach_id=?, exit_note='',
                room_id=0, room_number='', room_type='', has_air_conditioner=0,
                exclusive_use=0, updated_at=datetime('now','localtime')
            WHERE id=?
        ''', (
            enroll_date, _default_period_end(enroll_date), new_initial,
            new_tice, int(coach_id or 0), period['id'],
        ))
        db.execute('''
            UPDATE users SET camp_status='active', enroll_date=?, exit_date='', exit_note='',
                initial_weight=?, tice_weight=?, coach_id=? WHERE id=?
        ''', (
            enroll_date, new_initial, new_tice,
            int(coach_id or 0), user_id,
        ))
        return period_number


def apply_continuous_period_schedule(user_id, reference_date=None, reassign_weights=True):
    """按连续30天修正多期期次，并按称重日期重新归属早晚体重。"""
    reference = date.fromisoformat(str(reference_date)[:10]) if reference_date else date.today()
    with get_db() as db:
        user = db.execute('SELECT * FROM users WHERE id=?', (user_id,)).fetchone()
        if not user:
            raise ValueError('学员不存在')
        total = max(1, int(user['period_count'] or 1))
        first = db.execute('''
            SELECT enroll_date FROM enrollment_periods
            WHERE user_id=? AND period_number=1
        ''', (user_id,)).fetchone()
        anchor_text = str((first['enroll_date'] if first else '') or '')[:10]
        if not anchor_text:
            raise ValueError('第1期入营日期为空，无法自动计算')
        anchor = date.fromisoformat(anchor_text)
        _schedule_period_dates(db, user_id, force=True)

        periods = db.execute('''
            SELECT * FROM enrollment_periods
            WHERE user_id=? AND status<>'cancelled'
            ORDER BY period_number
        ''', (user_id,)).fetchall()
        by_number = {int(period['period_number']): period for period in periods}
        active_number = None
        day_offset = (reference - anchor).days
        calculated_number = max(1, day_offset // PERIOD_DAYS + 1)
        if user['camp_status'] == 'active' and calculated_number <= total:
            active_number = calculated_number
            old_active = next((period for period in periods if period['status'] == 'active'), None)
            for period in periods:
                number = int(period['period_number'])
                status = 'completed' if number < active_number else ('active' if number == active_number else 'planned')
                db.execute('''
                    UPDATE enrollment_periods SET status=?,
                        exit_date=CASE WHEN ?='active' THEN '' ELSE exit_date END,
                        updated_at=datetime('now','localtime')
                    WHERE id=?
                ''', (status, status, period['id']))
            current = by_number[active_number]
            current_start, _ = _period_window(anchor_text, active_number)
            new_initial, new_tice = _period_start_weights(
                db, user_id, active_number, user['initial_weight'], user['tice_weight']
            )
            db.execute('''
                UPDATE enrollment_periods SET initial_weight=?, tice_weight=?, coach_id=?,
                    room_id=?, room_number=?, room_type=?, has_air_conditioner=?, exclusive_use=?
                WHERE id=?
            ''', (
                new_initial, new_tice,
                int(user['coach_id'] or 0), int((old_active['room_id'] if old_active else 0) or 0),
                str((old_active['room_number'] if old_active else '') or ''),
                str((old_active['room_type'] if old_active else '') or ''),
                int((old_active['has_air_conditioner'] if old_active else 0) or 0),
                int((old_active['exclusive_use'] if old_active else 0) or 0), current['id'],
            ))
            db.execute(
                'UPDATE users SET enroll_date=?, initial_weight=?, tice_weight=? WHERE id=?',
                (current_start, new_initial, new_tice, user_id),
            )

        moved_morning = 0
        moved_evening = 0
        outside = 0
        if reassign_weights:
            for table in ('weights', 'evening_weights'):
                records = db.execute(
                    f'SELECT id, weigh_date, period_id FROM {table} WHERE user_id=?',
                    (user_id,),
                ).fetchall()
                for record in records:
                    try:
                        offset = (date.fromisoformat(str(record['weigh_date'])[:10]) - anchor).days
                    except ValueError:
                        outside += 1
                        continue
                    number = offset // PERIOD_DAYS + 1 if offset >= 0 else 0
                    target = by_number.get(number)
                    if not target:
                        outside += 1
                        continue
                    if int(record['period_id'] or 0) != int(target['id']):
                        db.execute(f'UPDATE {table} SET period_id=? WHERE id=?', (target['id'], record['id']))
                        if table == 'weights':
                            moved_morning += 1
                        else:
                            moved_evening += 1
        return {
            'user_id': user_id,
            'name': user['name'],
            'total_periods': total,
            'calculated_period': calculated_number,
            'active_period': active_number,
            'moved_morning': moved_morning,
            'moved_evening': moved_evening,
            'outside_records': outside,
        }

def get_all_users(status='active', include_face=True):
    """获取学员列表；status 可为 active/pending/exited/all。"""
    status = status if status in ('active', 'pending', 'exited', 'all') else 'active'
    where_sql = '' if status == 'all' else 'WHERE u.camp_status = ?'
    params = () if status == 'all' else (status,)
    face_select = 'f.face_image' if include_face else "'' AS face_image"
    with get_db() as db:
        rows = db.execute(f'''
            SELECT u.*, {face_select},
                   CASE WHEN f.feature IS NOT NULL THEN 1 ELSE 0 END AS face_enrolled,
                   c.name as coach_name,
                   (SELECT weight FROM weights WHERE user_id=u.id
                    ORDER BY weigh_date DESC LIMIT 1) as latest_weight
            FROM users u
            LEFT JOIN face_features f ON f.user_id = u.id
            LEFT JOIN coaches c ON c.id = u.coach_id
            {where_sql}
            ORDER BY CASE u.camp_status WHEN 'active' THEN 0 WHEN 'pending' THEN 1 ELSE 2 END,
                     coalesce(u.exit_date, '') DESC, u.name
        ''', params).fetchall()
        return _attach_periods(db, [dict(r) for r in rows])


def get_user(user_id):
    """获取单个学员"""
    with get_db() as db:
        row = db.execute('''
            SELECT u.*, f.face_image,
                   c.name as coach_name,
                   (SELECT weight FROM weights WHERE user_id=u.id
                    ORDER BY weigh_date DESC LIMIT 1) as latest_weight
            FROM users u
            LEFT JOIN face_features f ON f.user_id = u.id
            LEFT JOIN coaches c ON c.id = u.coach_id
            WHERE u.id = ?
        ''', (user_id,)).fetchone()
        if not row:
            return None
        user = dict(row)
        _attach_periods(db, [user])
        return user


def add_user(name, initial_weight=0, phone='', note='', tice_weight=0, coach_id=0,
             enroll_date=None, period_count=1, camp_status='active'):
    """添加学员"""
    if not enroll_date:
        enroll_date = date.today().isoformat()
    period_count = max(1, int(period_count or 1))
    camp_status = camp_status if camp_status in ('active', 'pending', 'exited') else 'active'
    with get_db() as db:
        cur = db.execute('''
            INSERT INTO users
                (name, phone, initial_weight, note, tice_weight, coach_id,
                 enroll_date, period_count, camp_status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (name, phone, initial_weight, note, tice_weight, coach_id,
              enroll_date, period_count, camp_status))
        user_id = cur.lastrowid
        _sync_period_count(db, user_id, period_count)
        first_status = 'active' if camp_status == 'active' else ('completed' if camp_status == 'exited' else 'planned')
        db.execute('''
            UPDATE enrollment_periods SET
                status=?, enroll_date=?, planned_end_date=?, initial_weight=?,
                tice_weight=?, coach_id=?, updated_at=datetime('now','localtime')
            WHERE user_id=? AND period_number=1
        ''', (
            first_status, enroll_date if first_status != 'planned' else '',
            _default_period_end(enroll_date) if first_status != 'planned' else '',
            float(initial_weight or 0), float(tice_weight or 0), int(coach_id or 0), user_id,
        ))
        _schedule_period_dates(db, user_id, force=True)
        db.execute('UPDATE users SET camp_status=? WHERE id=?', (camp_status, user_id))
        return user_id


def update_user(user_id, name=None, phone=None, initial_weight=None, note=None,
                tice_weight=None, coach_id=None, enroll_date=None, period_count=None):
    """更新学员信息"""
    fields = []
    values = []
    if name is not None:
        fields.append('name=?')
        values.append(name)
    if phone is not None:
        fields.append('phone=?')
        values.append(phone)
    if initial_weight is not None:
        fields.append('initial_weight=?')
        values.append(initial_weight)
    if note is not None:
        fields.append('note=?')
        values.append(note)
    if tice_weight is not None:
        fields.append('tice_weight=?')
        values.append(tice_weight)
    if coach_id is not None:
        fields.append('coach_id=?')
        values.append(coach_id)
    if enroll_date is not None:
        fields.append('enroll_date=?')
        values.append(enroll_date)
    if not fields and period_count is None:
        return False
    with get_db() as db:
        if fields:
            values.append(user_id)
            db.execute(f'UPDATE users SET {", ".join(fields)} WHERE id=?', values)
        if period_count is not None:
            _sync_period_count(db, user_id, period_count)
        active = get_active_period(user_id, db)
        if active:
            period_fields = []
            period_values = []
            if initial_weight is not None:
                period_fields.append('initial_weight=?')
                period_values.append(float(initial_weight or 0))
            if tice_weight is not None:
                period_fields.append('tice_weight=?')
                period_values.append(float(tice_weight or 0))
            if coach_id is not None:
                period_fields.append('coach_id=?')
                period_values.append(int(coach_id or 0))
            if enroll_date is not None:
                period_fields.extend(['enroll_date=?', 'planned_end_date=?'])
                period_values.extend([enroll_date, _default_period_end(enroll_date)])
            if period_fields:
                period_fields.append("updated_at=datetime('now','localtime')")
                period_values.append(active['id'])
                db.execute(
                    f"UPDATE enrollment_periods SET {', '.join(period_fields)} WHERE id=?",
                    period_values,
                )
        return True


def exit_user(user_id, exit_date=None, exit_note=''):
    """完成当前期；尚有待安排期次时进入等待下一期状态。"""
    if not exit_date:
        exit_date = date.today().isoformat()
    with get_db() as db:
        active = db.execute('''
            SELECT * FROM enrollment_periods
            WHERE user_id=? AND status='active' ORDER BY period_number LIMIT 1
        ''', (user_id,)).fetchone()
        if not active:
            return None
        db.execute('''
            UPDATE enrollment_periods SET status='completed', exit_date=?, exit_note=?,
                updated_at=datetime('now','localtime') WHERE id=?
        ''', (exit_date, str(exit_note or '')[:500], active['id']))
        next_period = db.execute('''
            SELECT period_number FROM enrollment_periods
            WHERE user_id=? AND status='planned' ORDER BY period_number LIMIT 1
        ''', (user_id,)).fetchone()
        next_status = 'pending' if next_period else 'exited'
        db.execute('''
            UPDATE users SET camp_status=?, exit_date=?, exit_note=? WHERE id=?
        ''', (next_status, exit_date, str(exit_note or '')[:500], user_id))
        return {
            'success': True,
            'completed_period_number': int(active['period_number']),
            'next_period_number': int(next_period['period_number']) if next_period else None,
            'camp_status': next_status,
        }


def restore_user(user_id, enroll_date=None, period_count=None):
    """撤销最近一次出营，将最近完成的期次恢复为在营。"""
    with get_db() as db:
        if period_count is not None:
            _sync_period_count(db, user_id, period_count)
        if get_active_period(user_id, db):
            return False
        period = db.execute('''
            SELECT * FROM enrollment_periods
            WHERE user_id=? AND status='completed'
            ORDER BY period_number DESC LIMIT 1
        ''', (user_id,)).fetchone()
        if not period:
            return False
        restored_enroll = enroll_date or period['enroll_date']
        db.execute('''
            UPDATE enrollment_periods SET status='active', exit_date='', exit_note='',
                enroll_date=?, planned_end_date=?, updated_at=datetime('now','localtime')
            WHERE id=?
        ''', (restored_enroll, _default_period_end(restored_enroll), period['id']))
        db.execute('''
            UPDATE users SET camp_status='active', enroll_date=?, exit_date='', exit_note='',
                initial_weight=?, tice_weight=?, coach_id=? WHERE id=?
        ''', (
            restored_enroll, period['initial_weight'], period['tice_weight'],
            period['coach_id'], user_id,
        ))
        return True


def delete_user(user_id):
    """删除学员及其人脸特征和体重记录"""
    with get_db() as db:
        db.execute('DELETE FROM face_features WHERE user_id=?', (user_id,))
        db.execute('DELETE FROM weights WHERE user_id=?', (user_id,))
        db.execute('DELETE FROM evening_weights WHERE user_id=?', (user_id,))
        db.execute('DELETE FROM enrollment_periods WHERE user_id=?', (user_id,))
        db.execute('DELETE FROM users WHERE id=?', (user_id,))
        return True



# 教练管理

def add_coach(name, phone=''):
    """添加教练"""
    with get_db() as db:
        cur = db.execute('INSERT INTO coaches (name, phone) VALUES (?, ?)', (name, phone))
        return cur.lastrowid

def get_all_coaches():
    """获取所有教练列表"""
    with get_db() as db:
        rows = db.execute('''
            SELECT c.*,
                   CASE WHEN f.feature IS NOT NULL THEN 1 ELSE 0 END AS face_enrolled,
                   a.id AS account_id, a.username, a.role AS account_role,
                   coalesce(a.is_active, 0) AS account_active,
                   CASE WHEN coalesce(a.password_hash, '') <> '' THEN 1 ELSE 0 END AS password_set,
                   a.last_login_at
            FROM coaches c
            LEFT JOIN coach_face_features f ON f.coach_id=c.id
            LEFT JOIN coach_accounts a ON a.coach_id=c.id
            ORDER BY c.name
        ''').fetchall()
        return [dict(r) for r in rows]

def update_coach(coach_id, name=None, phone=None):
    """更新教练信息"""
    fields = []
    values = []
    if name is not None:
        fields.append('name=?')
        values.append(name)
    if phone is not None:
        fields.append('phone=?')
        values.append(phone)
    if not fields:
        return False
    values.append(coach_id)
    with get_db() as db:
        set_clause = ', '.join(fields)
        db.execute(f'UPDATE coaches SET {set_clause} WHERE id=?', values)
        return True

def delete_coach(coach_id):
    """删除教练及其人脸特征"""
    with get_db() as db:
        db.execute('DELETE FROM coach_face_features WHERE coach_id=?', (coach_id,))
        db.execute('DELETE FROM coaches WHERE id=?', (coach_id,))
        db.execute('UPDATE users SET coach_id=0 WHERE coach_id=?', (coach_id,))
        return True


# ─── 教练独立账号 ───────────────────────────────────

def _available_username(db, candidate, exclude_account_id=None):
    base = str(candidate or '').strip() or 'coach'
    username = base
    suffix = 2
    while True:
        if exclude_account_id:
            row = db.execute(
                'SELECT id FROM coach_accounts WHERE username=? COLLATE NOCASE AND id<>?',
                (username, int(exclude_account_id)),
            ).fetchone()
        else:
            row = db.execute(
                'SELECT id FROM coach_accounts WHERE username=? COLLATE NOCASE',
                (username,),
            ).fetchone()
        if not row:
            return username
        username = f'{base}{suffix}'
        suffix += 1


def ensure_coach_accounts(admin_coach_name, admin_username, admin_password_hash):
    """为现有教练补齐独立账号，并将指定教练设为唯一管理员。"""
    with get_db() as db:
        coaches = db.execute('SELECT id, name, phone FROM coaches ORDER BY id').fetchall()
        bound_admin = db.execute('''
            SELECT coach_id FROM coach_accounts
            WHERE role='admin' ORDER BY id LIMIT 1
        ''').fetchone()
        admin_coach = (
            next((r for r in coaches if r['id'] == bound_admin['coach_id']), None)
            if bound_admin else
            next((r for r in coaches if r['name'] == admin_coach_name), None)
        )
        if not admin_coach:
            raise RuntimeError(f'未找到管理员绑定教练：{admin_coach_name}')

        existing_admin = db.execute(
            'SELECT id FROM coach_accounts WHERE coach_id=?', (admin_coach['id'],)
        ).fetchone()
        if not existing_admin:
            username = _available_username(db, admin_username)
            db.execute('''
                INSERT INTO coach_accounts
                    (coach_id, username, password_hash, role, is_active)
                VALUES (?, ?, ?, 'admin', 1)
            ''', (admin_coach['id'], username, admin_password_hash or ''))
        else:
            db.execute('''
                UPDATE coach_accounts
                SET role='admin', is_active=1,
                    updated_at=datetime('now','localtime')
                WHERE id=?
            ''', (existing_admin['id'],))

        db.execute(
            "UPDATE coach_accounts SET role='coach' WHERE coach_id<>? AND role='admin'",
            (admin_coach['id'],),
        )

        for coach in coaches:
            if coach['id'] == admin_coach['id']:
                continue
            exists = db.execute(
                'SELECT id FROM coach_accounts WHERE coach_id=?', (coach['id'],)
            ).fetchone()
            if exists:
                continue
            preferred = str(coach['phone'] or '').strip() or f'coach{coach["id"]}'
            username = _available_username(db, preferred)
            db.execute('''
                INSERT INTO coach_accounts
                    (coach_id, username, password_hash, role, is_active)
                VALUES (?, ?, '', 'coach', 1)
            ''', (coach['id'], username))


def get_coach_account_by_username(username):
    with get_db() as db:
        row = db.execute('''
            SELECT a.*, c.name AS coach_name, c.phone AS coach_phone,
                   CASE WHEN f.feature IS NOT NULL THEN 1 ELSE 0 END AS face_enrolled
            FROM coach_accounts a
            JOIN coaches c ON c.id=a.coach_id
            LEFT JOIN coach_face_features f ON f.coach_id=c.id
            WHERE a.username=? COLLATE NOCASE
        ''', (str(username or '').strip(),)).fetchone()
        return dict(row) if row else None


def get_coach_account_by_coach_id(coach_id):
    with get_db() as db:
        row = db.execute('''
            SELECT a.*, c.name AS coach_name, c.phone AS coach_phone,
                   CASE WHEN f.feature IS NOT NULL THEN 1 ELSE 0 END AS face_enrolled
            FROM coach_accounts a
            JOIN coaches c ON c.id=a.coach_id
            LEFT JOIN coach_face_features f ON f.coach_id=c.id
            WHERE a.coach_id=?
        ''', (int(coach_id),)).fetchone()
        return dict(row) if row else None


def get_coach_account(account_id):
    with get_db() as db:
        row = db.execute('''
            SELECT a.*, c.name AS coach_name, c.phone AS coach_phone,
                   CASE WHEN f.feature IS NOT NULL THEN 1 ELSE 0 END AS face_enrolled
            FROM coach_accounts a
            JOIN coaches c ON c.id=a.coach_id
            LEFT JOIN coach_face_features f ON f.coach_id=c.id
            WHERE a.id=?
        ''', (int(account_id),)).fetchone()
        return dict(row) if row else None


def ensure_account_for_coach(coach_id, username, password_hash='', is_active=True):
    with get_db() as db:
        existing = db.execute(
            'SELECT id FROM coach_accounts WHERE coach_id=?', (int(coach_id),)
        ).fetchone()
        if existing:
            raise ValueError('该教练已经绑定账号')
        clean_username = str(username or '').strip()
        if not clean_username:
            raise ValueError('请输入登录账号')
        if db.execute(
            'SELECT id FROM coach_accounts WHERE username=? COLLATE NOCASE',
            (clean_username,),
        ).fetchone():
            raise ValueError('登录账号已存在')
        cur = db.execute('''
            INSERT INTO coach_accounts
                (coach_id, username, password_hash, role, is_active)
            VALUES (?, ?, ?, 'coach', ?)
        ''', (int(coach_id), clean_username, password_hash or '', 1 if is_active else 0))
        return cur.lastrowid


def update_coach_account(account_id, username=None, password_hash=None, is_active=None):
    fields = []
    values = []
    with get_db() as db:
        account = db.execute(
            'SELECT * FROM coach_accounts WHERE id=?', (int(account_id),)
        ).fetchone()
        if not account:
            raise ValueError('账号不存在')
        if username is not None:
            clean_username = str(username).strip()
            if not clean_username:
                raise ValueError('登录账号不能为空')
            duplicate = db.execute('''
                SELECT id FROM coach_accounts
                WHERE username=? COLLATE NOCASE AND id<>?
            ''', (clean_username, int(account_id))).fetchone()
            if duplicate:
                raise ValueError('登录账号已存在')
            fields.append('username=?')
            values.append(clean_username)
        if password_hash is not None:
            fields.append('password_hash=?')
            values.append(password_hash)
        if is_active is not None:
            if account['role'] == 'admin' and not bool(is_active):
                raise ValueError('管理员账号不能停用')
            fields.append('is_active=?')
            values.append(1 if is_active else 0)
        if not fields:
            return True
        fields.append("updated_at=datetime('now','localtime')")
        values.append(int(account_id))
        db.execute(
            f'UPDATE coach_accounts SET {", ".join(fields)} WHERE id=?', values
        )
        return True


def mark_account_login(account_id):
    with get_db() as db:
        db.execute('''
            UPDATE coach_accounts
            SET last_login_at=datetime('now','localtime')
            WHERE id=?
        ''', (int(account_id),))


# ─── 操作日志 ───────────────────────────────────────

def add_operation_log(account_id=None, coach_id=None, actor_username='', actor_name='',
                      actor_role='', action='', target_type='', target_id='', detail='',
                      method='', path='', status_code=0, ip_address=''):
    with get_db() as db:
        db.execute('''
            INSERT INTO operation_logs
                (account_id, coach_id, actor_username, actor_name, actor_role,
                 action, target_type, target_id, detail, method, path,
                 status_code, ip_address)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            account_id, coach_id, str(actor_username or '')[:100],
            str(actor_name or '')[:100], str(actor_role or '')[:20],
            str(action or '')[:100], str(target_type or '')[:50],
            str(target_id or '')[:100], str(detail or '')[:1000],
            str(method or '')[:10], str(path or '')[:500],
            int(status_code or 0), str(ip_address or '')[:100],
        ))


def get_operation_logs(coach_id=None, action='', date_from='', date_to='', page=1, page_size=50):
    where = []
    params = []
    if coach_id:
        where.append('coach_id=?')
        params.append(int(coach_id))
    if action:
        where.append('action LIKE ?')
        params.append(f'%{str(action).strip()}%')
    if date_from:
        where.append('created_at>=?')
        params.append(str(date_from)[:10] + ' 00:00:00')
    if date_to:
        where.append('created_at<=?')
        params.append(str(date_to)[:10] + ' 23:59:59')
    where_sql = (' WHERE ' + ' AND '.join(where)) if where else ''
    page = max(1, int(page or 1))
    page_size = max(1, min(100, int(page_size or 50)))
    with get_db() as db:
        total = db.execute(
            'SELECT COUNT(*) FROM operation_logs' + where_sql, params
        ).fetchone()[0]
        rows = db.execute('''
            SELECT id, account_id, coach_id, actor_username, actor_name,
                   actor_role, action, target_type, target_id, detail,
                   method, path, status_code, ip_address, created_at
            FROM operation_logs
        ''' + where_sql + ' ORDER BY id DESC LIMIT ? OFFSET ?',
            params + [page_size, (page - 1) * page_size],
        ).fetchall()
        return {
            'logs': [dict(r) for r in rows],
            'total': int(total),
            'page': page,
            'page_size': page_size,
            'pages': max(1, (int(total) + page_size - 1) // page_size),
        }

# ─── 人脸特征管理 ───────────────────────────────────

def save_face_feature(user_id, feature_bytes, face_image_base64=''):
    """保存/更新人脸特征"""
    with get_db() as db:
        db.execute('''
            INSERT INTO face_features (user_id, feature, face_image)
            VALUES (?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                feature=excluded.feature,
                face_image=excluded.face_image,
                created_at=datetime('now','localtime')
        ''', (user_id, feature_bytes, face_image_base64))
        return True


def get_face_feature(user_id):
    """获取单个人脸特征"""
    with get_db() as db:
        row = db.execute('''
            SELECT * FROM face_features WHERE user_id=?
        ''', (user_id,)).fetchone()
        return dict(row) if row else None


def delete_face_feature(user_id):
    """删除人脸特征"""
    with get_db() as db:
        db.execute('DELETE FROM face_features WHERE user_id=?', (user_id,))
        return True


def get_all_face_features():
    """仅获取在营学员人脸特征 (用于 1:N 搜索)。"""
    with get_db() as db:
        rows = db.execute('''
            SELECT f.user_id, f.feature
            FROM face_features f
            JOIN users u ON u.id=f.user_id
            WHERE f.feature IS NOT NULL AND u.camp_status='active'
        ''').fetchall()
        return [(r['user_id'], r['feature']) for r in rows]


# ─── 教练人脸特征管理 ───────────────────────────────

def save_coach_face_feature(coach_id, feature_bytes, face_image_base64=''):
    """保存/更新教练人脸特征"""
    with get_db() as db:
        db.execute('''
            INSERT INTO coach_face_features (coach_id, feature, face_image)
            VALUES (?, ?, ?)
            ON CONFLICT(coach_id) DO UPDATE SET
                feature=excluded.feature,
                face_image=excluded.face_image,
                created_at=datetime('now','localtime')
        ''', (coach_id, feature_bytes, face_image_base64))
        return True


def get_coach_face_feature(coach_id):
    """获取单个教练人脸特征"""
    with get_db() as db:
        row = db.execute('''
            SELECT * FROM coach_face_features WHERE coach_id=?
        ''', (coach_id,)).fetchone()
        return dict(row) if row else None


def delete_coach_face_feature(coach_id):
    """删除教练人脸特征"""
    with get_db() as db:
        db.execute('DELETE FROM coach_face_features WHERE coach_id=?', (coach_id,))
        return True


def get_all_coach_face_features():
    """获取已启用账号的教练人脸特征 (用于人脸登录 1:N 搜索)"""
    with get_db() as db:
        rows = db.execute('''
            SELECT f.coach_id, f.feature
            FROM coach_face_features f
            JOIN coach_accounts a ON a.coach_id=f.coach_id AND a.is_active=1
            WHERE f.feature IS NOT NULL
        ''').fetchall()
        return [(r['coach_id'], r['feature']) for r in rows]


# ─── 体重记录 ───────────────────────────────────────

def _ensure_period_for_weigh_date(db, user_id, weigh_date):
    """按称重日期自动补齐期次，并返回该日期应该归属的期次 ID。"""
    try:
        target_date = date.fromisoformat(str(weigh_date)[:10])
    except (TypeError, ValueError):
        return None

    user = db.execute('SELECT * FROM users WHERE id=?', (user_id,)).fetchone()
    if not user or user['camp_status'] != 'active':
        return None

    first = db.execute('''
        SELECT enroll_date FROM enrollment_periods
        WHERE user_id=? AND period_number=1
    ''', (user_id,)).fetchone()
    anchor_text = str((first['enroll_date'] if first else '') or '')[:10]
    if not anchor_text:
        return None

    try:
        anchor = date.fromisoformat(anchor_text)
    except ValueError:
        return None

    day_offset = (target_date - anchor).days
    if day_offset < 0:
        return None

    target_number = day_offset // PERIOD_DAYS + 1
    total = max(1, int(user['period_count'] or 1))
    if target_number > total:
        _sync_period_count(db, user_id, target_number)
        total = target_number

    _schedule_period_dates(db, user_id, force=True)
    periods = db.execute('''
        SELECT * FROM enrollment_periods
        WHERE user_id=? AND status<>'cancelled' AND period_number<=?
        ORDER BY period_number
    ''', (user_id, total)).fetchall()
    by_number = {int(period['period_number']): period for period in periods}
    target = by_number.get(target_number)
    if not target:
        return None

    old_active = next((period for period in periods if period['status'] == 'active'), None)
    for period in periods:
        number = int(period['period_number'])
        status = 'completed' if number < target_number else ('active' if number == target_number else 'planned')
        if period['status'] != status:
            db.execute('''
                UPDATE enrollment_periods SET status=?,
                    exit_date=CASE WHEN ?='active' THEN '' ELSE exit_date END,
                    updated_at=datetime('now','localtime')
                WHERE id=?
            ''', (status, status, period['id']))

    current_start, _ = _period_window(anchor_text, target_number)
    new_initial, new_tice = _period_start_weights(
        db, user_id, target_number, user['initial_weight'], user['tice_weight']
    )
    db.execute('''
        UPDATE enrollment_periods SET initial_weight=?, tice_weight=?, coach_id=?,
            room_id=?, room_number=?, room_type=?, has_air_conditioner=?, exclusive_use=?,
            updated_at=datetime('now','localtime')
        WHERE id=?
    ''', (
        new_initial, new_tice,
        int(user['coach_id'] or 0), int((old_active['room_id'] if old_active else 0) or 0),
        str((old_active['room_number'] if old_active else '') or ''),
        str((old_active['room_type'] if old_active else '') or ''),
        int((old_active['has_air_conditioner'] if old_active else 0) or 0),
        int((old_active['exclusive_use'] if old_active else 0) or 0), target['id'],
    ))
    db.execute('''
        UPDATE users SET period_count=?, enroll_date=?, initial_weight=?, tice_weight=?
        WHERE id=?
    ''', (max(total, target_number), current_start, new_initial, new_tice, user_id))
    return int(target['id'])


def _resolve_weight_period_id(db, user_id, weigh_date):
    dated_period_id = _ensure_period_for_weigh_date(db, user_id, weigh_date)
    existing = db.execute('''
        SELECT period_id FROM weights
        WHERE user_id=? AND weigh_date=? AND coalesce(period_id,0)>0
    ''', (user_id, weigh_date)).fetchone()
    if existing and (not dated_period_id or int(existing['period_id']) == dated_period_id):
        return int(existing['period_id'])
    existing_evening = db.execute('''
        SELECT period_id FROM evening_weights
        WHERE user_id=? AND weigh_date=? AND coalesce(period_id,0)>0
    ''', (user_id, weigh_date)).fetchone()
    if existing_evening and (not dated_period_id or int(existing_evening['period_id']) == dated_period_id):
        return int(existing_evening['period_id'])
    if dated_period_id:
        return dated_period_id
    dated = db.execute('''
        SELECT id FROM enrollment_periods
        WHERE user_id=? AND coalesce(enroll_date,'')<>'' AND enroll_date<=?
          AND (coalesce(planned_end_date,'')='' OR planned_end_date>=?)
        ORDER BY period_number DESC LIMIT 1
    ''', (user_id, weigh_date, weigh_date)).fetchone()
    if dated:
        return int(dated['id'])
    active = db.execute('''
        SELECT id FROM enrollment_periods
        WHERE user_id=? AND status='active' ORDER BY period_number LIMIT 1
    ''', (user_id,)).fetchone()
    if active:
        return int(active['id'])
    first = db.execute('''
        SELECT id FROM enrollment_periods WHERE user_id=?
        ORDER BY period_number LIMIT 1
    ''', (user_id,)).fetchone()
    return int(first['id']) if first else 0

def save_weight(user_id, weight_val, weigh_date=None, note=None):
    """保存体重记录 (同一天覆盖)"""
    if weigh_date is None:
        weigh_date = date.today().isoformat()

    with get_db() as db:
        period_id = _resolve_weight_period_id(db, user_id, weigh_date)
        if note is None:
            # 称重端只更新体重时，保留数据中心已填写的备注。
            db.execute('''
                INSERT INTO weights (user_id, weigh_date, weight, period_id)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(user_id, weigh_date) DO UPDATE SET
                    weight=excluded.weight,
                    period_id=excluded.period_id,
                    recorded_at=datetime('now','localtime')
            ''', (user_id, weigh_date, weight_val, period_id))
        else:
            db.execute('''
                INSERT INTO weights (user_id, weigh_date, weight, note, period_id)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(user_id, weigh_date) DO UPDATE SET
                    weight=excluded.weight,
                    note=excluded.note,
                    period_id=excluded.period_id,
                    recorded_at=datetime('now','localtime')
            ''', (user_id, weigh_date, weight_val, str(note), period_id))
        return True


def get_user_weights(user_id, limit=100, period_id=None):
    """获取学员体重历史"""
    with get_db() as db:
        if period_id is None:
            rows = db.execute('''
                SELECT * FROM weights WHERE user_id=?
                ORDER BY weigh_date DESC LIMIT ?
            ''', (user_id, limit)).fetchall()
        else:
            rows = db.execute('''
                SELECT * FROM weights WHERE user_id=? AND period_id=?
                ORDER BY weigh_date DESC LIMIT ?
            ''', (user_id, int(period_id), limit)).fetchall()
        return [dict(r) for r in rows]


def delete_weight(user_id, weigh_date):
    """Delete weight record for a specific date"""
    with get_db() as db:
        db.execute('DELETE FROM weights WHERE user_id=? AND weigh_date=?', (user_id, weigh_date))
        return True

def get_today_weight(user_id):
    """获取今日体重"""
    today = date.today().isoformat()
    with get_db() as db:
        row = db.execute('''
            SELECT * FROM weights
            WHERE user_id=? AND weigh_date=?
        ''', (user_id, today)).fetchone()
        return dict(row) if row else None


def get_today_weighed_users():
    """获取今日已称重学员"""
    today = date.today().isoformat()
    with get_db() as db:
        rows = db.execute('''
            SELECT u.id, u.name, w.weight, w.recorded_at
            FROM weights w
            JOIN users u ON u.id = w.user_id
            WHERE w.weigh_date=? AND u.camp_status='active'
            ORDER BY w.recorded_at DESC
        ''', (today,)).fetchall()
        return [dict(r) for r in rows]


# ─── 晚上体重记录（仅用于完整学员导出）──────────────────

def save_evening_weight(user_id, weight_val, weigh_date=None):
    """保存晚上体重；同一学员同一天再次保存时覆盖。"""
    if weigh_date is None:
        weigh_date = date.today().isoformat()
    with get_db() as db:
        period_id = _resolve_weight_period_id(db, user_id, weigh_date)
        db.execute('''
            INSERT INTO evening_weights (user_id, weigh_date, weight, period_id)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(user_id, weigh_date) DO UPDATE SET
                weight=excluded.weight,
                period_id=excluded.period_id,
                recorded_at=datetime('now','localtime')
        ''', (user_id, weigh_date, weight_val, period_id))
        return True


def get_evening_weight(user_id, weigh_date=None):
    """获取指定日期的晚上体重，默认今天。"""
    if weigh_date is None:
        weigh_date = date.today().isoformat()
    with get_db() as db:
        row = db.execute('''
            SELECT * FROM evening_weights
            WHERE user_id=? AND weigh_date=?
        ''', (user_id, weigh_date)).fetchone()
        return dict(row) if row else None


def get_user_evening_weights(user_id, limit=100, period_id=None):
    """获取学员晚上体重历史，仅供完整学员表导出。"""
    with get_db() as db:
        if period_id is None:
            rows = db.execute('''
                SELECT * FROM evening_weights WHERE user_id=?
                ORDER BY weigh_date DESC LIMIT ?
            ''', (user_id, limit)).fetchall()
        else:
            rows = db.execute('''
                SELECT * FROM evening_weights WHERE user_id=? AND period_id=?
                ORDER BY weigh_date DESC LIMIT ?
            ''', (user_id, int(period_id), limit)).fetchall()
        return [dict(r) for r in rows]


# ─── 排名与统计 ─────────────────────────────────────

def _get_period_range(period_type, ref_date=None):
    """获取周期起止日期"""
    if ref_date is None:
        ref_date = date.today()
    elif isinstance(ref_date, str):
        ref_date = date.fromisoformat(ref_date)

    if period_type == 'week':
        # 按周起始日计算周范围
        start_day = WEEK_START_DAY
        days_diff = (ref_date.weekday() - start_day) % 7
        week_start = ref_date - timedelta(days=days_diff)
        week_end = week_start + timedelta(days=6)
        return week_start.isoformat(), week_end.isoformat()
    elif period_type == 'month':
        month_start = ref_date.replace(day=1)
        if ref_date.month == 12:
            month_end = ref_date.replace(year=ref_date.year+1, month=1, day=1) - timedelta(days=1)
        else:
            month_end = ref_date.replace(month=ref_date.month+1, day=1) - timedelta(days=1)
        return month_start.isoformat(), month_end.isoformat()
    return None, None


def get_rankings(period_type, ref_date=None):
    """获取指定周期的排名数据

    Args:
        period_type: 'week' 或 'month'
        ref_date: 参考日期, 默认今天

    Returns:
        list[dict]: 按掉秤率排序的学员排名列表
    """
    start_date, end_date = _get_period_range(period_type, ref_date)
    if not start_date:
        return []

    with get_db() as db:
        # 获取该周期内有称重记录的学员
        rows = db.execute('''
            SELECT
                u.id, u.name, u.initial_weight,
                MIN(w.weigh_date) as first_date,
                MAX(w.weigh_date) as last_date
            FROM users u
            JOIN weights w ON w.user_id = u.id
            WHERE w.weigh_date BETWEEN ? AND ?
              AND u.camp_status='active'
            GROUP BY u.id
            HAVING COUNT(w.id) >= 1
        ''', (start_date, end_date)).fetchall()

        result = []
        for row in rows:
            user_id = row['id']
            # 周期内首次体重
            first = db.execute('''
                SELECT weight FROM weights
                WHERE user_id=? AND weigh_date BETWEEN ? AND ?
                ORDER BY weigh_date ASC LIMIT 1
            ''', (user_id, start_date, end_date)).fetchone()

            # 周期末次体重
            last = db.execute('''
                SELECT weight FROM weights
                WHERE user_id=? AND weigh_date BETWEEN ? AND ?
                ORDER BY weigh_date DESC LIMIT 1
            ''', (user_id, start_date, end_date)).fetchone()

            if first and last:
                first_w = first['weight']
                last_w = last['weight']
                # 掉秤率 = (期末 - 期初) / 期初 * 100%
                change_rate = ((last_w - first_w) / first_w) * 100 if first_w > 0 else 0
                result.append({
                    'user_id': user_id,
                    'name': row['name'],
                    'initial_weight': row['initial_weight'],
                    'first_weight': first_w,
                    'last_weight': last_w,
                    'change_rate': round(change_rate, 2),
                    'first_date': row['first_date'],
                    'last_date': row['last_date'],
                    'period_type': period_type,
                })

        # 按掉秤率排序 (掉秤最多排最前, 即 change_rate 最小的排第一)
        result.sort(key=lambda x: x['change_rate'])
        for i, r in enumerate(result):
            r['rank'] = i + 1
        return result


# ─── 系统设置 ───────────────────────────────────────

def get_setting(key, default=''):
    """获取配置项"""
    with get_db() as db:
        row = db.execute('SELECT value FROM settings WHERE key=?', (key,)).fetchone()
        return row['value'] if row else default


def set_setting(key, value):
    """设置配置项"""
    with get_db() as db:
        db.execute('''
            INSERT INTO settings (key, value) VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE SET value=excluded.value
        ''', (key, value))
        return True


# ─── 导出数据 ───────────────────────────────────────

def export_ranking_excel(period_type, ref_date=None):
    """导出排名数据为 Excel (返回文件路径)"""
    import pandas as pd
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side

    rankings = get_rankings(period_type, ref_date)
    if not rankings:
        return None

    period_label = '周' if period_type == 'week' else '月'
    start_date, end_date = _get_period_range(period_type, ref_date)

    df = pd.DataFrame(rankings)
    df = df.rename(columns={
        'rank': '排名',
        'name': '姓名',
        'initial_weight': '初始体重(斤)',
        'first_weight': '期初体重(斤)',
        'last_weight': '期末体重(斤)',
        'change_rate': f'本{period_label}掉秤率(%)',
    })
    df = df[['排名', '姓名', '初始体重(斤)', '期初体重(斤)', '期末体重(斤)', f'本{period_label}掉秤率(%)']]

    export_dir = os.path.join(os.path.dirname(DB_PATH), 'exports')
    os.makedirs(export_dir, exist_ok=True)
    filename = f'排名_{period_type}_{start_date}_{end_date}.xlsx'
    filepath = os.path.join(export_dir, filename)

    df.to_excel(filepath, index=False, engine='openpyxl')
    return filepath
