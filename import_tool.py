#!/usr/bin/env python3
"""
聚美康体重管理系统 - Excel 批量导入工具
==========================================

功能:
  1. 从 Excel 导入学员体重记录（支持多 Sheet，每个 Sheet 一个学员）
  2. 同步入营时间（F3 单元格的 Excel 序号 → 日期）
  3. 自动填充空缺日期（用前一天体重补齐）

使用方法:
  1. 把 Excel 文件上传到服务器: scp -P 223 xxx.xlsx root@8.137.111.127:/tmp/
  2. 修改下方 XLSX_PATH 指向你的 Excel 文件
  3. 先预览: DRY_RUN = False，运行 python3 import_tool.py
  4. 确认无误后写入: DRY_RUN = False，再运行一次
  5. 填充空缺: 运行 python3 import_tool.py --fill-gaps

Excel 表格格式要求:
  - 每个 Sheet 代表一个学员（Sheet 名随意，但 B3 必须是学员姓名）
  - 跳过的 Sheet: 新模版、最新原模版、Sheet1、Sheet2
  - 第2行是表头，第3行是学员信息，第4行是体重表头，第5行起是每日数据

  列位置（第2行表头自动检测）:
    B3 = 姓名（固定）
    C3 = 身高/cm
    D3 = 体重/斤（入营体重）→ users.initial_weight
    E3 = 月目标
    F3 = 天目标 / 入营时间（因表格版本不同可能在不同列）
    G3 = 结营时间 / 入营时间
    I3 = 体测体重 → users.tice_weight
    K3 = 责任教练 → users.coach_id（按名匹配）

  体重记录（固定位置）:
    B列(第5行起) = 日期（Excel 序号，如 46207 = 2026-07-07）
    C列(第5行起) = 当日体重（单位：斤）

导入规则:
  - 学员姓名必须与系统中已有学员匹配，不存在的自动跳过
  - 体重为 0 或空的行 = 当日未称重，跳过不导入
  - 同一天同一学员已有记录则跳过（不覆盖，只填空缺）
  - 教练名支持模糊匹配（"钰宸教练"→"钰宸"、"卢教练"→"卢教"、"悦教"→"悦悦"）
  - 入营体重、体测体重、教练绑定会更新到 users 表

日期转换:
  Excel 序号 → 日期: 基准 1899-12-30 + 序号天
  例: 46207 → 2026-07-07

回滚方法:
  cp /root/backups/weight_db_backup_YYYYMMDD_HHMMSS.db /root/聚美康正式版2.0/db/weight.db
  systemctl restart jumeikang-app jumeikang-admin
"""

import sqlite3
import openpyxl
from datetime import datetime, timedelta
from collections import Counter
import sys

# ==================== 配置区 ====================
DB_PATH = '/root/聚美康正式版2.0/db/weight.db'
XLSX_PATH = '/tmp/卢教.xlsx'
DRY_RUN = False                               # True=只预览不写入, False=实际写入

SKIP_SHEETS = ['新模版', '最新原模版', 'Sheet1', 'Sheet2']

# 教练别名映射（Excel 中的写法 → 系统中的教练名）
COACH_ALIAS = {
    '悦教': '悦悦',
    '卢': '卢教',
}
# ===============================================


def excel_serial_to_date(serial):
    """Excel 序号转日期 (1899-12-30 基准)"""
    if serial is None or serial == '':
        return None
    try:
        serial = int(serial)
    except (ValueError, TypeError):
        return None
    base = datetime(1899, 12, 30)
    return (base + timedelta(days=serial)).strftime('%Y-%m-%d')


def safe_float(val, default=0):
    if val is None or val == '':
        return default
    try:
        return float(val)
    except (ValueError, TypeError):
        return default


def find_header_col(ws, row, keywords):
    """在第 row 行查找包含 keywords 中任一关键词的列号 (1-based)"""
    for col in range(1, ws.max_column + 1):
        val = ws.cell(row=row, column=col).value
        if val and isinstance(val, str):
            for kw in keywords:
                if kw in val:
                    return col
    return None


def match_coach(name, coaches):
    """教练名模糊匹配"""
    if name in coaches:
        return coaches[name]
    for k, v in coaches.items():
        if name in k or k in name:
            return v
    clean = name.replace('教练', '').strip()
    if clean in coaches:
        return coaches[clean]
    for k, v in coaches.items():
        if clean in k or k in clean:
            return v
    if name in COACH_ALIAS and COACH_ALIAS[name] in coaches:
        return coaches[COACH_ALIAS[name]]
    return 0


def import_excel(db, xlsx_path, dry_run):
    """主导入函数"""
    wb = openpyxl.load_workbook(xlsx_path, data_only=True)

    users = {r['name'].strip(): dict(r) for r in db.execute('SELECT * FROM users').fetchall()}
    coaches = {r['name'].strip(): r['id'] for r in db.execute('SELECT * FROM coaches').fetchall()}

    print('=== 系统现状 ===')
    print('已有学员: %d 人' % len(users))
    print('已有教练: %s' % list(coaches.keys()))
    print('已有体重记录: %d 条' % db.execute('SELECT count(*) FROM weights').fetchone()[0])

    report = {
        'matched': [], 'not_found': [], 'coach_not_found': [],
        'weight_records': [], 'weight_errors': [], 'user_updates': [],
    }

    for sheet_name in wb.sheetnames:
        if sheet_name in SKIP_SHEETS:
            continue

        ws = wb[sheet_name]
        name = str(ws['B3'].value or '').strip()
        if not name:
            continue

        # 动态检测列位置
        weight_col = find_header_col(ws, 2, ['体重', '入营体重']) or 4
        tice_col = find_header_col(ws, 2, ['体测体重', '体测目标'])
        coach_col = find_header_col(ws, 2, ['责任教练'])
        enroll_col = find_header_col(ws, 2, ['入营时间'])

        initial_weight = safe_float(ws.cell(row=3, column=weight_col).value)
        tice_weight = safe_float(ws.cell(row=3, column=tice_col).value) if tice_col else 0
        coach_name = str(ws.cell(row=3, column=coach_col).value or '').strip() if coach_col else ''
        coach_id = match_coach(coach_name, coaches) if coach_name else 0
        enroll_date = excel_serial_to_date(ws.cell(row=3, column=enroll_col).value) if enroll_col else None

        if coach_name and coach_id == 0:
            report['coach_not_found'].append('%s -> 教练"%s"不存在' % (name, coach_name))

        print('\n===== %s =====' % name)
        print('  入营体重=%.1f, 体测体重=%.1f, 教练=%s(id=%d), 入营时间=%s' % (
            initial_weight, tice_weight, coach_name, coach_id, enroll_date or 'N/A'))

        if name not in users:
            report['not_found'].append(name)
            print('  [跳过] 学员"%s"不在系统中' % name)
            continue

        user_id = users[name]['id']
        report['matched'].append(name)
        report['user_updates'].append({
            'name': name, 'id': user_id,
            'initial_weight': initial_weight,
            'tice_weight': tice_weight,
            'coach_id': coach_id,
            'enroll_date': enroll_date,
        })

        # 读取体重记录 (B=日期, C=当日体重, 第5行起)
        w_ok = 0
        w_skip = 0
        for row in range(5, ws.max_row + 1):
            date_ser = ws.cell(row=row, column=2).value
            wt = ws.cell(row=row, column=3).value
            weigh_date = excel_serial_to_date(date_ser)
            if not weigh_date:
                w_skip += 1
                continue
            if wt is None or wt == '' or (isinstance(wt, (int, float)) and float(wt) == 0):
                w_skip += 1
                continue
            weight = safe_float(wt)
            if weight == 0:
                w_skip += 1
                continue

            report['weight_records'].append({
                'user_id': user_id, 'name': name,
                'weigh_date': weigh_date, 'weight': weight,
            })
            w_ok += 1

        print('  体重: 导入%d条, 跳过%d条' % (w_ok, w_skip))

    wb.close()

    # ===== 报告 =====
    print('\n' + '=' * 50)
    print('  导入预览报告 (DRY_RUN=%s)' % dry_run)
    print('=' * 50)
    print('匹配学员: %d 人 -> %s' % (len(report['matched']), ', '.join(report['matched'])))
    if report['not_found']:
        print('未找到学员: %d 人 -> %s' % (len(report['not_found']), ', '.join(report['not_found'])))
    if report['coach_not_found']:
        print('教练未找到:')
        for e in report['coach_not_found']:
            print('  %s' % e)
    print('体重记录: %d 条' % len(report['weight_records']))

    nc = Counter(d['name'] for d in report['weight_records'])
    print('\n各学员导入条数:')
    for n, c in sorted(nc.items()):
        dates = [d['weigh_date'] for d in report['weight_records'] if d['name'] == n]
        print('  %s: %d条 (%s ~ %s)' % (n, c, min(dates), max(dates)))

    if dry_run:
        print('\n[预览模式] 未写入数据。确认无误后设 DRY_RUN=False 重新运行。')
        return

    # ===== 写入 =====
    print('\n[写入模式] 开始...')
    updated = 0
    for u in report['user_updates']:
        sets = []
        params = []
        if u['initial_weight'] > 0:
            sets.append('initial_weight=?'); params.append(u['initial_weight'])
        if u['tice_weight'] > 0:
            sets.append('tice_weight=?'); params.append(u['tice_weight'])
        if u['coach_id'] > 0:
            sets.append('coach_id=?'); params.append(u['coach_id'])
        if u.get('enroll_date'):
            sets.append('enroll_date=?'); params.append(u['enroll_date'])
        if sets:
            params.append(u['id'])
            db.execute('UPDATE users SET %s WHERE id=?' % ', '.join(sets), params)
            updated += 1
            print('  更新学员: %s' % u['name'])
    print('学员更新: %d 人' % updated)

    inserted = 0
    skipped_existing = 0
    for rec in report['weight_records']:
        # 检查是否已有该日期记录
        existing = db.execute(
            'SELECT weight FROM weights WHERE user_id=? AND weigh_date=?',
            (rec['user_id'], rec['weigh_date'])).fetchone()
        if existing:
            skipped_existing += 1
            continue
        db.execute('''INSERT OR IGNORE INTO weights (user_id, weigh_date, weight, recorded_at)
            VALUES (?, ?, ?, datetime('now','localtime'))''',
            (rec['user_id'], rec['weigh_date'], rec['weight']))
        inserted += 1
    db.commit()
    print('体重写入: %d 条 (新增)' % inserted)
    print('跳过已有记录: %d 条 (不覆盖)' % skipped_existing)
    print('完成!')


def fill_gaps(db, dry_run):
    """自动填充缺失日期（用前一天体重）"""
    users = db.execute('''
        SELECT DISTINCT user_id, u.name
        FROM weights w JOIN users u ON w.user_id = u.id
        ORDER BY u.name
    ''').fetchall()

    total_filled = 0
    detail = []

    for user in users:
        user_id = user['user_id']
        name = user['name']
        records = db.execute(
            'SELECT weigh_date, weight FROM weights WHERE user_id=? ORDER BY weigh_date',
            (user_id,)).fetchall()
        if len(records) < 2:
            continue

        dates = [r['weigh_date'] for r in records]
        start = datetime.strptime(dates[0], '%Y-%m-%d')
        end = datetime.strptime(dates[-1], '%Y-%m-%d')
        weight_map = {r['weigh_date']: r['weight'] for r in records}

        current = start
        prev_weight = records[0]['weight']
        user_filled = 0

        while current <= end:
            date_str = current.strftime('%Y-%m-%d')
            if date_str not in weight_map:
                user_filled += 1
                detail.append({'name': name, 'date': date_str, 'weight': prev_weight})
                if not dry_run:
                    db.execute('''INSERT OR IGNORE INTO weights (user_id, weigh_date, weight, recorded_at)
                        VALUES (?, ?, ?, datetime('now','localtime'))''',
                        (user_id, date_str, prev_weight))
            else:
                prev_weight = weight_map[date_str]
            current += timedelta(days=1)

        total_filled += user_filled
        if user_filled > 0:
            print('  %s: 填充 %d 条' % (name, user_filled))

    print('\n============================')
    print('  空缺填充报告 (DRY_RUN=%s)' % dry_run)
    print('============================')
    print('将填充: %d 条' % total_filled)

    if not dry_run:
        db.commit()
        new_total = db.execute('SELECT count(*) FROM weights').fetchone()[0]
        print('体重记录总数: %d' % new_total)


def main():
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row

    if '--fill-gaps' in sys.argv:
        fill_gaps(db, DRY_RUN)
    else:
        import_excel(db, XLSX_PATH, DRY_RUN)

    db.close()


if __name__ == '__main__':
    main()
