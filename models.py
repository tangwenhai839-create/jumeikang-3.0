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
                recorded_at TEXT DEFAULT (datetime('now','localtime')),
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                UNIQUE(user_id, weigh_date)
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

            CREATE INDEX IF NOT EXISTS idx_weights_user_date
                ON weights(user_id, weigh_date);
            CREATE INDEX IF NOT EXISTS idx_weights_date
                ON weights(weigh_date);
        ''')

        # 兼容已有数据库: 自动补充缺失的列
        cols = [r['name'] for r in db.execute('PRAGMA table_info(users)').fetchall()]
        if 'tice_weight' not in cols:
            db.execute('ALTER TABLE users ADD COLUMN tice_weight REAL DEFAULT 0')
        if 'coach_id' not in cols:
            db.execute('ALTER TABLE users ADD COLUMN coach_id INTEGER DEFAULT 0')

        # 默认设置：活体开关
        db.execute('''
            INSERT INTO settings (key, value) VALUES ('liveness_enabled', ?)
            ON CONFLICT(key) DO NOTHING
        ''', ('1' if LIVENESS_ENABLED else '0',))


# ─── 学员管理 ───────────────────────────────────────

def get_all_users():
    """获取所有学员列表"""
    with get_db() as db:
        rows = db.execute('''
            SELECT u.*, f.face_image,
                   c.name as coach_name,
                   (SELECT weight FROM weights WHERE user_id=u.id
                    ORDER BY weigh_date DESC LIMIT 1) as latest_weight
            FROM users u
            LEFT JOIN face_features f ON f.user_id = u.id
            LEFT JOIN coaches c ON c.id = u.coach_id
            ORDER BY u.name
        ''').fetchall()
        return [dict(r) for r in rows]


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
        return dict(row) if row else None


def add_user(name, initial_weight=0, phone='', note='', tice_weight=0, coach_id=0):
    """添加学员"""
    with get_db() as db:
        cur = db.execute('''
            INSERT INTO users (name, phone, initial_weight, note, tice_weight, coach_id)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (name, phone, initial_weight, note, tice_weight, coach_id))
        return cur.lastrowid


def update_user(user_id, name=None, phone=None, initial_weight=None, note=None, tice_weight=None, coach_id=None):
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

    if not fields:
        return False

    values.append(user_id)
    with get_db() as db:
        db.execute(f'UPDATE users SET {", ".join(fields)} WHERE id=?', values)
        return True


def delete_user(user_id):
    """删除学员及其人脸特征和体重记录"""
    with get_db() as db:
        db.execute('DELETE FROM face_features WHERE user_id=?', (user_id,))
        db.execute('DELETE FROM weights WHERE user_id=?', (user_id,))
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
        rows = db.execute('SELECT * FROM coaches ORDER BY name').fetchall()
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
    """获取所有人脸特征 (用于 1:N 搜索)"""
    with get_db() as db:
        rows = db.execute('''
            SELECT user_id, feature FROM face_features
            WHERE feature IS NOT NULL
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
    """获取所有教练人脸特征 (用于人脸登录 1:N 搜索)"""
    with get_db() as db:
        rows = db.execute('''
            SELECT coach_id, feature FROM coach_face_features
            WHERE feature IS NOT NULL
        ''').fetchall()
        return [(r['coach_id'], r['feature']) for r in rows]


# ─── 体重记录 ───────────────────────────────────────

def save_weight(user_id, weight_val, weigh_date=None):
    """保存体重记录 (同一天覆盖)"""
    if weigh_date is None:
        weigh_date = date.today().isoformat()

    with get_db() as db:
        db.execute('''
            INSERT INTO weights (user_id, weigh_date, weight)
            VALUES (?, ?, ?)
            ON CONFLICT(user_id, weigh_date) DO UPDATE SET
                weight=excluded.weight,
                recorded_at=datetime('now','localtime')
        ''', (user_id, weigh_date, weight_val))
        return True


def get_user_weights(user_id, limit=100):
    """获取学员体重历史"""
    with get_db() as db:
        rows = db.execute('''
            SELECT * FROM weights
            WHERE user_id=?
            ORDER BY weigh_date DESC
            LIMIT ?
        ''', (user_id, limit)).fetchall()
        return [dict(r) for r in rows]


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
            WHERE w.weigh_date=?
            ORDER BY w.recorded_at DESC
        ''', (today,)).fetchall()
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
        'initial_weight': '初始体重(kg)',
        'first_weight': '期初体重(kg)',
        'last_weight': '期末体重(kg)',
        'change_rate': f'本{period_label}掉秤率(%)',
    })
    df = df[['排名', '姓名', '初始体重(kg)', '期初体重(kg)', '期末体重(kg)', f'本{period_label}掉秤率(%)']]

    export_dir = os.path.join(os.path.dirname(DB_PATH), 'exports')
    os.makedirs(export_dir, exist_ok=True)
    filename = f'排名_{period_type}_{start_date}_{end_date}.xlsx'
    filepath = os.path.join(export_dir, filename)

    df.to_excel(filepath, index=False, engine='openpyxl')
    return filepath
