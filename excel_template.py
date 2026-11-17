# -*- coding: utf-8 -*-
"""导出 Excel - 完全匹配工作簿1.xlsx 模板"""

import os
from datetime import datetime, timedelta
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, Border, Side
from openpyxl.utils import get_column_letter
import re

FONT_SON = '宋体'
FONT_FS = '仿宋'
BORDER_THIN = Border(
    left=Side(style='thin'), right=Side(style='thin'),
    top=Side(style='thin'), bottom=Side(style='thin'))
ALIGN_CENTER = Alignment(horizontal='center', vertical='center')
ALIGN_VCENTER = Alignment(vertical='center')

def _c(ws, r, c, v=None, font=None, align=None, border=None, nf=None):
    cell = ws.cell(row=r, column=c)
    if v is not None: cell.value = v
    if font: cell.font = font
    if align: cell.alignment = align
    if border: cell.border = border
    if nf: cell.number_format = nf
    return cell

def create_sheet(ws, user, weights, evening_weights, student_index, total_students):
    """按工作簿1.xlsx模板写入一个学员sheet"""
    name = user.get('name', '') or ''
    # 兼容现有数据：学员身高历史上保存在 phone 字段。
    height = user.get('phone', '') or '170'
    w_kg = float(user.get('initial_weight', 0) or 0)
    # 月目标、天目标、体测体重在 Excel 导出时用公式计算

    # 日期 - 优先使用 enroll_date, 否则用 created_at
    enroll_date = user.get('enroll_date', '') or ''
    created = user.get('created_at', str(datetime.now().date()))
    join_str = enroll_date if enroll_date else created
    join_dt = datetime.strptime(join_str[:10], '%Y-%m-%d') if len(join_str) >= 10 else datetime.now()
    join_serial = (join_dt - datetime(1899, 12, 30)).days
    end_serial = (join_dt + timedelta(days=30) - datetime(1899, 12, 30)).days

    # 列宽
    for col_letter in 'BCDEFGHIJKLM':
        ws.column_dimensions[col_letter].width = 13.0

    # Row 1: 左侧学员表与右侧教练板块标题
    ws.merge_cells('B1:I1')
    _c(ws, 1, 2, '聚美康减肥训练营学员减重记录表',
       Font(name=FONT_FS, size=22, bold=True), ALIGN_CENTER)
    ws.merge_cells('K1:M1')
    _c(ws, 1, 11, '教练板块',
       Font(name=FONT_FS, size=22, bold=True), ALIGN_CENTER)

    # Row 2: 学员信息表头
    h2 = ['', '姓名', '身高/cm', '体重/斤', '月目标', '天目标',
          '入营时间', '结营时间', '', '', '体测体重', '报名期数', '责任教练']
    for i, v in enumerate(h2, 1):
        if i == 10:  # J列作为左右区域的空白分隔列
            continue
        _c(ws, 2, i, v, Font(name=FONT_SON, size=10, bold=True), ALIGN_CENTER, BORDER_THIN)

    # Row 3: 学员信息值
    coach_name = user.get('coach_name', '') or ''
    tice_w = float(user.get('tice_weight', 0) or 0)
    d3 = ['', name, height, w_kg, '', '', join_serial, end_serial, '', '', tice_w, '', coach_name]
    for i, v in enumerate(d3, 1):
        if i == 10:
            continue
        c = _c(ws, 3, i, v, Font(name=FONT_SON, size=10), ALIGN_VCENTER, BORDER_THIN)
        if i == 3:  # 身高
            c.number_format = '0.0'
        elif i in (4, 11):  # 体重、体测体重
            c.number_format = '0.0'
        elif i in (7, 8):  # 日期
            c.number_format = 'YYYY-MM-DD'
    # 公式: 月目标 = 体重*0.08, 天目标 = 月目标/30
    _c(ws, 3, 5, '=D3*0.08', Font(name=FONT_SON, size=10), ALIGN_VCENTER, BORDER_THIN, '0.0')
    _c(ws, 3, 6, '=E3/30', Font(name=FONT_SON, size=10), ALIGN_VCENTER, BORDER_THIN, '0.0')

    # Row 4: 每日记录表头
    h4 = ['', '日期', '备注', '当日体重', '晚上体重', '当日减重',
          '总减重(斤)', '剩余天数', '签约目标差', '',
          '共减重(斤)', '教练目标', '体测减重']
    for i, v in enumerate(h4, 1):
        if i == 10:
            continue
        _c(ws, 4, i, v if v else None, Font(name=FONT_SON, size=10, bold=True),
           ALIGN_CENTER, BORDER_THIN)

    # 整理体重数据 (kg)
    sorted_w = sorted(weights, key=lambda w: w['weigh_date'])
    w_map = {}
    note_map = {}
    for w in sorted_w:
        w_map[w['weigh_date']] = round(w['weight'], 1)  # kg
        note_map[w['weigh_date']] = str(w.get('note', '') or '')
    evening_map = {
        w['weigh_date']: round(w['weight'], 1)
        for w in evening_weights
    }

    # 生成30天日期
    dates_30 = [(join_dt + timedelta(days=i)).strftime('%Y-%m-%d') for i in range(30)]

    # 不做carry-forward：只有实际称重的日期才填体重，未来日期留空

    # Rows 5-34: 每日数据 (所有行都写公式, IF判断空值)
    last_weight = None
    for offset in range(30):
        row = offset + 5
        d = dates_30[offset]
        has_w = d in w_map
        cur_w = w_map[d] if has_w else last_weight
        if has_w:
            last_weight = cur_w

        # B: 日期
        dt = join_dt + timedelta(days=offset)
        _c(ws, row, 2, (dt - datetime(1899, 12, 30)).days,
           Font(name=FONT_SON, size=10), ALIGN_VCENTER, BORDER_THIN, 'YYYY-MM-DD')

        # C: 备注（与数据中心当日称重记录一致）
        _c(ws, row, 3, note_map.get(d) or None, Font(name=FONT_SON, size=10),
           ALIGN_VCENTER, BORDER_THIN)

        # D: 当日体重 (kg)
        if has_w and cur_w is not None:
            _c(ws, row, 4, cur_w, Font(name=FONT_SON, size=10),
               ALIGN_VCENTER, BORDER_THIN, '0.0')

        # E: 晚上体重（只展示，不参与任何公式）
        if d in evening_map:
            _c(ws, row, 5, evening_map[d], Font(name=FONT_SON, size=10),
               ALIGN_VCENTER, BORDER_THIN, '0.0')

        # F: 当日减重 = 上一次有效早上体重 - 当日早上体重（自动跳过漏称日）
        if row == 5:
            _c(ws, row, 6, 0, Font(name=FONT_SON, size=10),
               ALIGN_VCENTER, BORDER_THIN, '0.0')
        else:
            _c(ws, row, 6,
               f'=IF(D{row}="","",IFERROR(LOOKUP(2,1/(D$5:D{row-1}<>""),D$5:D{row-1})-D{row},0))',
               Font(name=FONT_SON, size=10), ALIGN_VCENTER, BORDER_THIN, '0.0')

        # G: 总减重(kg) = 入营体重 - 当日早上体重
        _c(ws, row, 7, f'=IF(D{row}="","",D3-D{row})',
           Font(name=FONT_SON, size=10), ALIGN_VCENTER, BORDER_THIN, '0.0')

        # H: 剩余天数
        _c(ws, row, 8, f'{30-offset}天', Font(name=FONT_SON, size=10),
           ALIGN_VCENTER, BORDER_THIN)

        # I: 签约目标差 = 月目标 - 总减重
        _c(ws, row, 9, f'=IF(D{row}="","",E3-G{row})',
           Font(name=FONT_SON, size=10), ALIGN_VCENTER, BORDER_THIN, '0.000')

        # J: 空白分隔列

        # K: 共减重(kg)
        if row == 5:
            _c(ws, row, 11, f'=IF(D{row}="","",MAX(G{row},0))',
               Font(name=FONT_SON, size=10), ALIGN_VCENTER, BORDER_THIN, '0.0')
        else:
            prev_common = (f'LOOKUP(2,1/(K$5:K{row-1}<>""),K$5:K{row-1})')
            _c(ws, row, 11,
               f'=IF(D{row}="","",IFERROR(MAX({prev_common}+F{row},{prev_common}),MAX(G{row},0)))',
               Font(name=FONT_SON, size=10), ALIGN_VCENTER, BORDER_THIN, '0.0')

        # L: 30分制教练目标进度 = 体测减重 / (体测体重 * 10%) * 30。
        # 单元格保留数值，显示为“4.6/30”。
        _c(ws, row, 12,
           f'=IF(OR(M{row}="",$K$3=0),"",M{row}/($K$3*0.1)*30)',
           Font(name=FONT_SON, size=10), ALIGN_VCENTER, BORDER_THIN,
           '0.0"/30"')

        # M: 体测减重 = 本营期体测体重 - 截至当日最近一次有效早上体重。
        # 当日未称重时，自动沿用上一次有效称重的结果。
        body_test_formula = (f'=IFERROR($K$3-'
                             f'LOOKUP(2,1/(D$5:D{row}<>""),D$5:D{row}),"")')
        _c(ws, row, 13, body_test_formula, Font(name=FONT_SON, size=10),
           ALIGN_VCENTER, BORDER_THIN, '0.0')

    # 确保所有行 B-M 列都有边框 (即使空值)
    for offset in range(30):
        row = offset + 5
        for col_border in range(2, 14):
            if col_border == 10:
                continue
            cell = ws.cell(row=row, column=col_border)
            if cell.value is None:
                cell.border = BORDER_THIN
                cell.font = Font(name=FONT_SON, size=10)
                cell.alignment = ALIGN_VCENTER


    # === 第二营期（第31-60天）===
    p2_start_dt = join_dt + timedelta(days=30)
    p2_end_dt = p2_start_dt + timedelta(days=30)
    p2_join_serial = (p2_start_dt - datetime(1899, 12, 30)).days
    p2_end_serial = (p2_end_dt - datetime(1899, 12, 30)).days
    # 第二营期入营体重 = 第一营期最后实际体重
    p2_initial = last_weight if last_weight is not None else w_kg

    # Row 37: 第二营期左右板块标题
    ws.merge_cells('B37:I37')
    _c(ws, 37, 2, '第二营期减重记录表',
       Font(name=FONT_FS, size=22, bold=True), ALIGN_CENTER)
    ws.merge_cells('K37:M37')
    _c(ws, 37, 11, '教练板块',
       Font(name=FONT_FS, size=22, bold=True), ALIGN_CENTER)

    # Row 38: 信息表头
    for i, v in enumerate(h2, 1):
        if i == 10:
            continue
        _c(ws, 38, i, v, Font(name=FONT_SON, size=10, bold=True),
           ALIGN_CENTER, BORDER_THIN)

    # Row 39: 信息值（入营体重用上月末尾）
    d39 = ['', name, height, p2_initial, '', '',
           p2_join_serial, p2_end_serial, '', '', tice_w, '', coach_name]
    for i, v in enumerate(d39, 1):
        if i == 10:
            continue
        c = _c(ws, 39, i, v, Font(name=FONT_SON, size=10),
               ALIGN_VCENTER, BORDER_THIN)
        if i == 3:
            c.number_format = '0.0'
        elif i in (4, 11):
            c.number_format = '0.0'
        elif i in (7, 8):
            c.number_format = 'YYYY-MM-DD'
    _c(ws, 39, 5, '=D39*0.08', Font(name=FONT_SON, size=10),
       ALIGN_VCENTER, BORDER_THIN, '0.0')
    _c(ws, 39, 6, '=E39/30', Font(name=FONT_SON, size=10),
       ALIGN_VCENTER, BORDER_THIN, '0.0')

    # Row 40: 每日记录表头
    for i, v in enumerate(h4, 1):
        if i == 10:
            continue
        _c(ws, 40, i, v if v else None,
           Font(name=FONT_SON, size=10, bold=True),
           ALIGN_CENTER, BORDER_THIN)

    # 生成第二营期日期
    dates_30_p2 = [(p2_start_dt + timedelta(days=i)).strftime('%Y-%m-%d')
                   for i in range(30)]

    # Rows 41-70: 第二营期每日数据
    for offset in range(30):
        row = offset + 41
        d = dates_30_p2[offset]
        has_w = d in w_map
        cur_w = w_map[d] if has_w else None

        # B: 日期
        dt = p2_start_dt + timedelta(days=offset)
        _c(ws, row, 2, (dt - datetime(1899, 12, 30)).days,
           Font(name=FONT_SON, size=10), ALIGN_VCENTER, BORDER_THIN,
           'YYYY-MM-DD')

        # C: 备注（与数据中心当日称重记录一致）
        _c(ws, row, 3, note_map.get(d) or None, Font(name=FONT_SON, size=10),
           ALIGN_VCENTER, BORDER_THIN)

        # D: 当日体重
        if has_w and cur_w is not None:
            _c(ws, row, 4, cur_w, Font(name=FONT_SON, size=10),
               ALIGN_VCENTER, BORDER_THIN, '0.0')

        # E: 晚上体重（只展示，不参与任何公式）
        if d in evening_map:
            _c(ws, row, 5, evening_map[d], Font(name=FONT_SON, size=10),
               ALIGN_VCENTER, BORDER_THIN, '0.0')

        # F: 当日减重（自动跳过漏称日）
        if row == 41:
            _c(ws, row, 6, 0, Font(name=FONT_SON, size=10),
               ALIGN_VCENTER, BORDER_THIN, '0.0')
        else:
            _c(ws, row, 6,
               f'=IF(D{row}="","",IFERROR(LOOKUP(2,1/(D$41:D{row-1}<>""),D$41:D{row-1})-D{row},0))',
               Font(name=FONT_SON, size=10), ALIGN_VCENTER, BORDER_THIN,
               '0.0')

        # G: 总减重
        _c(ws, row, 7, f'=IF(D{row}="","",D39-D{row})',
           Font(name=FONT_SON, size=10), ALIGN_VCENTER, BORDER_THIN, '0.0')

        # H: 剩余天数
        _c(ws, row, 8, f'{30-offset}天',
           Font(name=FONT_SON, size=10), ALIGN_VCENTER, BORDER_THIN)

        # I: 签约目标差
        _c(ws, row, 9, f'=IF(D{row}="","",E39-G{row})',
           Font(name=FONT_SON, size=10), ALIGN_VCENTER, BORDER_THIN,
           '0.000')

        # J: 空白分隔列

        # K: 共减重
        if row == 41:
            _c(ws, row, 11,
               f'=IF(D{row}="","",MAX(G{row},0))',
               Font(name=FONT_SON, size=10), ALIGN_VCENTER, BORDER_THIN,
               '0.0')
        else:
            prev_common = (f'LOOKUP(2,1/(K$41:K{row-1}<>""),K$41:K{row-1})')
            _c(ws, row, 11,
               f'=IF(D{row}="","",IFERROR(MAX({prev_common}+F{row},{prev_common}),MAX(G{row},0)))',
               Font(name=FONT_SON, size=10), ALIGN_VCENTER, BORDER_THIN,
               '0.0')

        # L: 第二营期30分制教练目标进度。
        _c(ws, row, 12,
           f'=IF(OR(M{row}="",$K$39=0),"",M{row}/($K$39*0.1)*30)',
           Font(name=FONT_SON, size=10), ALIGN_VCENTER, BORDER_THIN,
           '0.0"/30"')

        # M: 第二营期体测减重；未称重日沿用上一次有效早上体重。
        body_test_formula = (f'=IFERROR($K$39-'
                             f'LOOKUP(2,1/(D$41:D{row}<>""),D$41:D{row}),"")')
        _c(ws, row, 13, body_test_formula, Font(name=FONT_SON, size=10),
           ALIGN_VCENTER, BORDER_THIN, '0.0')

    # 确保第二营期所有行有边框
    for offset in range(30):
        row = offset + 41
        for col_border in range(2, 14):
            if col_border == 10:
                continue
            cell = ws.cell(row=row, column=col_border)
            if cell.value is None:
                cell.border = BORDER_THIN
                cell.font = Font(name=FONT_SON, size=10)
                cell.alignment = ALIGN_VCENTER


    # 打印设置
    ws.page_setup.orientation = 'landscape'
    ws.page_setup.fitToWidth = 1
    ws.page_setup.fitToHeight = 1


def _safe_sheet_name(name, existing):
    base = re.sub(r'[\\/*?:\[\]]', '', str(name or '学员')).strip()[:27] or '学员'
    candidate = base
    counter = 2
    while candidate in existing:
        suffix = f'-{counter}'
        candidate = base[:31-len(suffix)] + suffix
        counter += 1
    return candidate


def _period_status_label(status):
    return {
        'planned': '待安排', 'active': '在营',
        'completed': '已完成', 'cancelled': '已取消',
    }.get(status, status or '')


def _write_overview_sheet(ws, users_with_weights):
    ws.title = '学员总览'
    headers = [
        '序号', '姓名', '报名总期数', '已完成期数', '当前/下一期', '剩余待安排',
        '学员状态', '本期入营时间', '本期预计结营', '责任教练', '当前宿舍',
        '初始体重(斤)', '最新体重(斤)', '累计减重(斤)', '备注',
    ]
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=len(headers))
    _c(ws, 1, 1, '聚美康学员报名期数总览', Font(name=FONT_FS, size=18, bold=True), ALIGN_CENTER)
    for col, header in enumerate(headers, 1):
        _c(ws, 2, col, header, Font(name=FONT_SON, size=10, bold=True), ALIGN_CENTER, BORDER_THIN)
        ws.column_dimensions[get_column_letter(col)].width = 15
    ws.column_dimensions['B'].width = 13
    ws.column_dimensions['O'].width = 28

    status_labels = {'active': '在营', 'pending': '待下一期入营', 'exited': '全部期数完成'}
    for index, (user, weights, _evening) in enumerate(users_with_weights, 1):
        row = index + 2
        periods = user.get('periods') or []
        summary = user.get('period_summary') or {}
        focus_number = summary.get('current_period_number')
        focus = next((p for p in periods if p.get('period_number') == focus_number), None) or {}
        sorted_weights = sorted(weights, key=lambda item: item.get('weigh_date', ''))
        latest = float(sorted_weights[-1]['weight']) if sorted_weights else None
        first_period = next((p for p in periods if p.get('status') != 'cancelled'), {})
        initial = float(first_period.get('initial_weight') or user.get('initial_weight') or 0)
        loss = round(initial - latest, 1) if initial and latest is not None else None
        vals = [
            index, user.get('name', ''), int(user.get('period_count') or 1),
            int(summary.get('completed_periods') or 0),
            (f"第{focus_number}期 · {_period_status_label(focus.get('status'))}" if focus_number else '--'),
            int(summary.get('remaining_periods') or 0),
            status_labels.get(user.get('camp_status'), user.get('camp_status', '')),
            focus.get('enroll_date') or '', focus.get('planned_end_date') or '',
            focus.get('coach_name') or user.get('coach_name') or '',
            focus.get('room_number') or '', initial or None, latest, loss,
            user.get('note') or '',
        ]
        for col, value in enumerate(vals, 1):
            cell = _c(ws, row, col, value, Font(name=FONT_SON, size=10), ALIGN_VCENTER, BORDER_THIN)
            if col in (12, 13, 14):
                cell.number_format = '0.0'
    ws.freeze_panes = 'A3'
    ws.auto_filter.ref = f'A2:O{max(2, len(users_with_weights)+2)}'


def _write_period_detail_sheet(ws, users_with_weights):
    ws.title = '报名期次明细'
    headers = [
        '序号', '姓名', '第几期', '期次状态', '入营时间', '预计结营', '实际出营',
        '责任教练', '宿舍', '房型', '空调', '整间独住', '本期初始体重',
        '本期最新体重', '本期减重', '称重记录数', '出营说明',
    ]
    for col, header in enumerate(headers, 1):
        _c(ws, 1, col, header, Font(name=FONT_SON, size=10, bold=True), ALIGN_CENTER, BORDER_THIN)
        ws.column_dimensions[get_column_letter(col)].width = 14
    ws.column_dimensions['B'].width = 13
    ws.column_dimensions['Q'].width = 30
    row = 2
    index = 1
    room_type_labels = {'SINGLE': '单人间', 'DOUBLE': '双人间', 'TRIPLE': '三人间', 'QUAD': '四人间'}
    for user, _weights, _evening in users_with_weights:
        total = int(user.get('period_count') or 1)
        periods = [
            period for period in (user.get('periods') or [])
            if period.get('status') != 'cancelled'
            and int(period.get('period_number') or 0) <= total
        ]
        for period in periods:
            vals = [
                index, user.get('name', ''), period.get('period_number'),
                _period_status_label(period.get('status')), period.get('enroll_date') or '',
                period.get('planned_end_date') or '', period.get('exit_date') or '',
                period.get('coach_name') or '', period.get('room_number') or '',
                room_type_labels.get(period.get('room_type'), period.get('room_type') or ''), '是' if period.get('has_air_conditioner') else '否',
                '是' if period.get('exclusive_use') else '否',
                period.get('initial_weight') or None, period.get('latest_weight'),
                period.get('period_loss'), period.get('weight_count') or 0,
                period.get('exit_note') or '',
            ]
            for col, value in enumerate(vals, 1):
                cell = _c(ws, row, col, value, Font(name=FONT_SON, size=10), ALIGN_VCENTER, BORDER_THIN)
                if col in (13, 14, 15):
                    cell.number_format = '0.0'
            row += 1
            index += 1
    ws.freeze_panes = 'A2'
    ws.auto_filter.ref = f'A1:Q{max(1, row-1)}'


def _write_dynamic_student_sheet(ws, user, weights, evening_weights):
    total = int(user.get('period_count') or 1)
    periods = [
        period for period in (user.get('periods') or [])
        if period.get('status') != 'cancelled'
        and int(period.get('period_number') or 0) <= total
    ] or [{
        'id': 0, 'period_number': 1, 'status': 'active',
        'enroll_date': user.get('enroll_date') or '',
        'planned_end_date': '', 'initial_weight': user.get('initial_weight') or 0,
        'tice_weight': user.get('tice_weight') or 0, 'coach_name': user.get('coach_name') or '',
    }]
    # 多期学员优先展示当前在营期，其余营期按期数从小到大排列。
    # 进入下一期后，只要该期状态更新为 active，下一次导出便会自动置顶。
    periods.sort(key=lambda period: (
        0 if period.get('status') == 'active' else 1,
        int(period.get('period_number') or 0),
    ))
    height = user.get('phone') or ''
    for letter in 'BCDEFGHIJKLMN':
        ws.column_dimensions[letter].width = 13
    ws.column_dimensions['N'].width = 20

    for period_index, period in enumerate(periods):
        block = 1 + period_index * 36
        info_header_row = block + 1
        info_row = block + 2
        daily_header_row = block + 3
        first_daily_row = block + 4
        period_number = int(period.get('period_number') or period_index + 1)
        status_label = _period_status_label(period.get('status'))
        title = f'第{period_number}期减重记录表 · {status_label}'
        ws.merge_cells(start_row=block, start_column=2, end_row=block, end_column=9)
        _c(ws, block, 2, title, Font(name=FONT_FS, size=20, bold=True), ALIGN_CENTER)
        ws.merge_cells(start_row=block, start_column=11, end_row=block, end_column=14)
        _c(ws, block, 11, '教练板块', Font(name=FONT_FS, size=18, bold=True), ALIGN_CENTER)

        info_headers = ['', '姓名', '身高/cm', '本期初始体重', '月目标', '天目标',
                        '入营时间', '结营时间', '', '', '体测体重', '报名情况',
                        '责任教练', '教练月目标']
        for col, value in enumerate(info_headers, 1):
            if col != 10:
                _c(ws, info_header_row, col, value or None,
                   Font(name=FONT_SON, size=10, bold=True), ALIGN_CENTER, BORDER_THIN)
        enroll_date = str(period.get('enroll_date') or '')[:10]
        end_date = str(period.get('planned_end_date') or '')[:10]
        initial = float(period.get('initial_weight') or 0)
        if not initial and period.get('first_weight') is not None:
            initial = float(period['first_weight'])
        vals = ['', user.get('name', ''), height, initial or None, '', '', enroll_date or None,
                end_date or None, '', '', float(period.get('tice_weight') or 0) or None,
                f'第{period_number}/{total}期', period.get('coach_name') or '', '']
        for col, value in enumerate(vals, 1):
            if col == 10:
                continue
            cell = _c(ws, info_row, col, value, Font(name=FONT_SON, size=10), ALIGN_VCENTER, BORDER_THIN)
            if col in (4, 11, 14): cell.number_format = '0.0'
            if col in (7, 8): cell.number_format = 'YYYY-MM-DD'
        _c(ws, info_row, 5, f'=D{info_row}*0.08', Font(name=FONT_SON, size=10), ALIGN_VCENTER, BORDER_THIN, '0.0')
        _c(ws, info_row, 6, f'=E{info_row}/30', Font(name=FONT_SON, size=10), ALIGN_VCENTER, BORDER_THIN, '0.0')
        # N: 教练月目标 = 本期体测体重的10%。
        _c(ws, info_row, 14, f'=IF(K{info_row}="","",K{info_row}*0.1)',
           Font(name=FONT_SON, size=10), ALIGN_VCENTER, BORDER_THIN, '0.0')

        daily_headers = ['', '日期', '备注', '当日体重', '晚上体重', '当日减重',
                         '总减重(斤)', '剩余天数', '签约目标差', '',
                         '共减重(斤)', '教练目标', '体测减重', '教练目标差']
        for col, value in enumerate(daily_headers, 1):
            if col != 10:
                _c(ws, daily_header_row, col, value or None,
                   Font(name=FONT_SON, size=10, bold=True), ALIGN_CENTER, BORDER_THIN)

        period_id = int(period.get('id') or 0)
        p_weights = [w for w in weights if int(w.get('period_id') or 0) == period_id]
        p_evening = [w for w in evening_weights if int(w.get('period_id') or 0) == period_id]
        weight_map = {w['weigh_date']: float(w['weight']) for w in p_weights}
        note_map = {w['weigh_date']: str(w.get('note') or '') for w in p_weights}
        evening_map = {w['weigh_date']: float(w['weight']) for w in p_evening}
        start_date = datetime.strptime(enroll_date, '%Y-%m-%d') if enroll_date else None

        for offset in range(30):
            row = first_daily_row + offset
            date_text = (start_date + timedelta(days=offset)).strftime('%Y-%m-%d') if start_date else ''
            for col in range(2, 15):
                if col != 10:
                    _c(ws, row, col, None, Font(name=FONT_SON, size=10), ALIGN_VCENTER, BORDER_THIN)
            if date_text:
                _c(ws, row, 2, date_text, Font(name=FONT_SON, size=10), ALIGN_VCENTER, BORDER_THIN, 'YYYY-MM-DD')
            if note_map.get(date_text): _c(ws, row, 3, note_map[date_text])
            if date_text in weight_map: _c(ws, row, 4, weight_map[date_text], nf='0.0')
            if date_text in evening_map: _c(ws, row, 5, evening_map[date_text], nf='0.0')
            if offset == 0:
                _c(ws, row, 6, 0 if date_text in weight_map else None, nf='0.0')
            else:
                _c(ws, row, 6, f'=IF(D{row}="","",IFERROR(LOOKUP(2,1/(D${first_daily_row}:D{row-1}<>""),D${first_daily_row}:D{row-1})-D{row},0))', nf='0.0')
            _c(ws, row, 7, f'=IF(D{row}="","",D{info_row}-D{row})', nf='0.0')
            _c(ws, row, 8, f'{30-offset}天' if start_date else '')
            _c(ws, row, 9, f'=IF(D{row}="","",E{info_row}-G{row})', nf='0.000')
            if offset == 0:
                common_loss_formula = f'=IF(D{row}="","",MAX(F{row},0))'
            else:
                prev_common = f'LOOKUP(2,1/(K${first_daily_row}:K{row-1}<>""),K${first_daily_row}:K{row-1})'
                common_loss_formula = f'=IF(D{row}="","",IFERROR({prev_common}+MAX(F{row},0),MAX(F{row},0)))'
            _c(ws, row, 11, common_loss_formula, nf='0.0')
            _c(ws, row, 12, f'=IF(OR(M{row}="",$K${info_row}=0),"",M{row}/($K${info_row}*0.1)*30)', nf='0.0"/30"')
            _c(ws, row, 13, f'=IFERROR($K${info_row}-LOOKUP(2,1/(D${first_daily_row}:D{row}<>""),D${first_daily_row}:D{row}),"")', nf='0.0')
            # N: 教练目标差 = 教练月目标 - 当日体测减重。
            _c(ws, row, 14,
               f'=IF(OR(M{row}="",$N${info_row}=""),"",$N${info_row}-M{row})', nf='0.0')

    ws.page_setup.orientation = 'landscape'
    ws.page_setup.fitToWidth = 1
    ws.page_setup.fitToHeight = 0


def export_all_students(users_with_weights):
    """导出学员总览、每期期次明细及每名学员的动态多期称重表。"""
    if not users_with_weights:
        return None
    wb = Workbook()
    overview = wb.active
    _write_overview_sheet(overview, users_with_weights)
    detail = wb.create_sheet()
    _write_period_detail_sheet(detail, users_with_weights)
    existing_names = set(wb.sheetnames)
    for user, weights, evening_weights in users_with_weights:
        safe_name = _safe_sheet_name(user.get('name'), existing_names)
        existing_names.add(safe_name)
        ws = wb.create_sheet(title=safe_name)
        _write_dynamic_student_sheet(ws, user, weights, evening_weights)

    export_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'db', 'exports')
    os.makedirs(export_dir, exist_ok=True)
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    fp = os.path.join(export_dir, f'在营学员_多期总览_{ts}.xlsx')
    wb.save(fp)
    return fp


def export_extra_training(not_weighed, low_loss, late_weighed=None):
    """导出加练人员名单
    not_weighed: 今日未称重学员列表
    low_loss: 今日掉秤<0.2斤的学员列表
    late_weighed: 超过8:10:59称重的学员列表
    三类分三个 sheet
    """
    wb = Workbook()

    # Sheet 1: 今日未称重
    ws1 = wb.active
    ws1.title = '今日未称重'
    _write_extra_sheet(ws1, '今日未称重学员', not_weighed, is_not_weighed=True)

    # Sheet 2: 掉秤不足
    ws2 = wb.create_sheet(title='掉秤不足0.2斤')
    _write_extra_sheet(ws2, '今日掉秤不足0.2斤学员', low_loss, is_not_weighed=False)

    # Sheet 3: 超过8:10:59称重
    ws3 = wb.create_sheet(title='超时称重(8点01分后)')
    _write_extra_sheet(ws3, '8:11起超时称重学员', late_weighed, is_not_weighed=False, is_late=True)

    export_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'db', 'exports')
    os.makedirs(export_dir, exist_ok=True)
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    fp = os.path.join(export_dir, f'加练人员_{ts}.xlsx')
    wb.save(fp)
    return fp


def _write_extra_sheet(ws, title, data, is_not_weighed, is_late=False):
    """写入加练名单 sheet"""
    # 标题
    if is_late:
        ws.merge_cells('A1:H1')
    else:
        ws.merge_cells('A1:G1')
    _c(ws, 1, 1, title, Font(name=FONT_FS, size=16, bold=True), ALIGN_CENTER)

    # 列宽
    for col_letter in 'ABCDEFGH':
        ws.column_dimensions[col_letter].width = 14.0

    # 表头
    if is_not_weighed:
        headers = ['序号', '姓名', '电话', '责任教练', '初始体重(斤)', '体测体重(斤)', '备注']
    else:
        if is_late:
            headers = ['序号', '姓名', '电话', '责任教练', '初始体重(斤)', '今日体重(斤)', '称重时间', '备注']
        else:
            headers = ['序号', '姓名', '电话', '责任教练', '初始体重(斤)', '昨日体重(斤)', '今日体重(斤)', '掉秤(斤)']
    for i, h in enumerate(headers, 1):
        _c(ws, 2, i, h, Font(name=FONT_SON, size=10, bold=True), ALIGN_CENTER, BORDER_THIN)

    # 数据行
    for idx, item in enumerate(data, 1):
        row = idx + 2
        name = item.get('name', '')
        phone = item.get('phone', '') or ''
        coach = item.get('coach_name', '') or ''
        init_w = item.get('initial_weight', 0) or 0

        if is_not_weighed:
            tice_w = item.get('tice_weight', 0) or 0
            vals = [idx, name, phone, coach, init_w, tice_w, '']
            for i, v in enumerate(vals, 1):
                cell = _c(ws, row, i, v, Font(name=FONT_SON, size=10), ALIGN_VCENTER, BORDER_THIN)
                if i in (5, 6):
                    cell.number_format = '0.0'
        elif is_late:
            today_w = item.get('today_weight', 0) or 0
            recorded_at = (item.get('recorded_at', '') or '')[-8:]
            vals = [idx, name, phone, coach, init_w, today_w, recorded_at, '超时称重']
            for i, v in enumerate(vals, 1):
                cell = _c(ws, row, i, v, Font(name=FONT_SON, size=10), ALIGN_VCENTER, BORDER_THIN)
                if i in (5, 6):
                    cell.number_format = '0.0'
        else:
            yest = item.get('yesterday_weight', 0) or 0
            today = item.get('today_weight', 0) or 0
            loss = item.get('loss', 0) or 0
            vals = [idx, name, phone, coach, init_w, yest, today, loss]
            for i, v in enumerate(vals, 1):
                cell = _c(ws, row, i, v, Font(name=FONT_SON, size=10), ALIGN_VCENTER, BORDER_THIN)
                if i in (5, 6, 7, 8):
                    cell.number_format = '0.0'

    # 如果没数据，写一行提示
    if not data:
        ws.merge_cells(f'A{3}:G{3}')
        _c(ws, 3, 1, '（无）', Font(name=FONT_SON, size=10), ALIGN_CENTER)

    # 打印设置
    ws.page_setup.orientation = 'landscape'
    ws.page_setup.fitToWidth = 1
    ws.page_setup.fitToHeight = 1
