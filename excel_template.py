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

def create_sheet(ws, user, weights, student_index, total_students):
    """按工作簿1.xlsx模板写入一个学员sheet"""
    name = user.get('name', '') or ''
    height = user.get('note', '') or '170'  # 身高, 暂用默认值
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
    for col_letter in 'BCDEFGHIJKL':
        ws.column_dimensions[col_letter].width = 13.0

    # Row 1: 标题 (D1:H1合并)
    ws.merge_cells('D1:H1')
    _c(ws, 1, 4, '聚美康减肥训练营学员减重记录表',
       Font(name=FONT_FS, size=22, bold=True), ALIGN_CENTER)

    # Row 2: 学员信息表头
    h2 = ['', '姓名', '身高/cm', '体重/斤', '月目标', '天目标',
          '入营时间', '结营时间', '体侧体重', '报名期数', '责任教练', '备注']
    for i, v in enumerate(h2, 1):
        _c(ws, 2, i, v, Font(name=FONT_SON, size=10, bold=True), ALIGN_CENTER, BORDER_THIN)

    # Row 3: 学员信息值
    coach_name = user.get('coach_name', '') or ''
    tice_w = float(user.get('tice_weight', 0) or 0)
    d3 = ['', name, height, w_kg, '', '', join_serial, end_serial, tice_w, '', coach_name, '']
    for i, v in enumerate(d3, 1):
        c = _c(ws, 3, i, v, Font(name=FONT_SON, size=10), ALIGN_VCENTER, BORDER_THIN)
        if i == 3:  # 身高
            c.number_format = '0.0'
        elif i in (4, 9):  # 体重、体测体重
            c.number_format = '0.0'
        elif i in (7, 8):  # 日期
            c.number_format = 'YYYY-MM-DD'
    # 公式: 月目标 = 体重*0.08, 天目标 = 月目标/30
    _c(ws, 3, 5, '=D3*0.08', Font(name=FONT_SON, size=10), ALIGN_VCENTER, BORDER_THIN, '0.0')
    _c(ws, 3, 6, '=E3/30', Font(name=FONT_SON, size=10), ALIGN_VCENTER, BORDER_THIN, '0.0')

    # Row 4: 每日记录表头
    h4 = ['', '日期', '当日体重', '当日减重', '总减重(斤)', '剩余天数',
          '签约目标差', '共减重(斤)', '教练目标', '领取物品']
    for i, v in enumerate(h4, 1):
        cell = _c(ws, 4, i, v if v else None, Font(name=FONT_SON, size=10, bold=True),
                  ALIGN_CENTER, BORDER_THIN)
    # K4, L4 空白但有边框
    for i in (11, 12):
        _c(ws, 4, i, None, Font(name=FONT_SON, size=10, bold=True), ALIGN_CENTER, BORDER_THIN)

    # 整理体重数据 (kg)
    sorted_w = sorted(weights, key=lambda w: w['weigh_date'])
    w_map = {}
    for w in sorted_w:
        w_map[w['weigh_date']] = round(w['weight'], 1)  # kg

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

        # C: 当日体重 (kg)
        if has_w and cur_w is not None:
            _c(ws, row, 3, cur_w, Font(name=FONT_SON, size=10),
               ALIGN_VCENTER, BORDER_THIN, '0.0')

        # D: 当日减重 = IF(C{row}="","",IFERROR(C{row-1}-C{row},""))
        if row == 5:
            _c(ws, row, 4, 0, Font(name=FONT_SON, size=10),
               ALIGN_VCENTER, BORDER_THIN, '0.0')
        else:
            _c(ws, row, 4, f'=IF(C{row}="","",IFERROR(C{row-1}-C{row},""))',
               Font(name=FONT_SON, size=10), ALIGN_VCENTER, BORDER_THIN, '0.0')

        # E: 总减重(kg) = IF(C{row}="","",D3-C{row})
        _c(ws, row, 5, f'=IF(C{row}="","",D3-C{row})',
           Font(name=FONT_SON, size=10), ALIGN_VCENTER, BORDER_THIN, '0.0')

        # F: 剩余天数
        _c(ws, row, 6, f'{30-offset}天', Font(name=FONT_SON, size=10),
           ALIGN_VCENTER, BORDER_THIN)

        # G: 签约目标差 = IF(C{row}="","",E3-E{row})
        _c(ws, row, 7, f'=IF(C{row}="","",E3-E{row})',
           Font(name=FONT_SON, size=10), ALIGN_VCENTER, BORDER_THIN, '0.000')

        # H: 共减重(kg) = IF(C{row}="","",IFERROR(MAX(H{row-1}+D{row},H{row-1}),MAX(E{row},0)))
        if row == 5:
            _c(ws, row, 8, f'=IF(C{row}="","",MAX(E{row},0))',
               Font(name=FONT_SON, size=10), ALIGN_VCENTER, BORDER_THIN, '0.0')
        else:
            _c(ws, row, 8, f'=IF(C{row}="","",IFERROR(MAX(H{row-1}+D{row},H{row-1}),MAX(E{row},0)))',
               Font(name=FONT_SON, size=10), ALIGN_VCENTER, BORDER_THIN, '0.0')

        # I: 教练目标 = IF(C{row}="","",I5-E{row})
        _c(ws, row, 9, f'=IF(C{row}="","",I5-E{row})',
           Font(name=FONT_SON, size=10), ALIGN_VCENTER, BORDER_THIN, '0.0')

        # J, K, L: 空白但有边框
        for col_jkl in (10, 11, 12):
            _c(ws, row, col_jkl, None, Font(name=FONT_SON, size=10),
               ALIGN_VCENTER, BORDER_THIN)

    # 确保所有行 B-L 列都有边框 (即使空值)
    for offset in range(30):
        row = offset + 5
        for col_border in range(2, 13):
            cell = ws.cell(row=row, column=col_border)
            if cell.value is None:
                cell.border = BORDER_THIN
                cell.font = Font(name=FONT_SON, size=10)
                cell.alignment = ALIGN_VCENTER    # I5 公式 = I3*0.1 (教练目标)
    _c(ws, 5, 9, '=I3*0.1', Font(name=FONT_SON, size=10), ALIGN_VCENTER, BORDER_THIN, '0.0')

    # 打印设置
    ws.page_setup.orientation = 'landscape'
    ws.page_setup.fitToWidth = 1
    ws.page_setup.fitToHeight = 1


def export_all_students(users_with_weights):
    """导出全部学员到一个工作簿"""
    if not users_with_weights:
        return None
    wb = Workbook()
    wb.remove(wb.active)
    for i, (user, weights) in enumerate(users_with_weights):
        safe_name = (user.get('name', '') or '未知')
        safe_name = ''.join(c for c in safe_name if c.isalnum() or c in ' _.-' or ord(c) >= 0x4e00)[:31]
        if not safe_name: safe_name = '学员'
        ws = wb.create_sheet(title=safe_name)
        create_sheet(ws, user, weights, i, len(users_with_weights))

    export_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'db', 'exports')
    os.makedirs(export_dir, exist_ok=True)
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    fp = os.path.join(export_dir, f'全部学员_{ts}.xlsx')
    wb.save(fp)
    return fp


def export_extra_training(not_weighed, low_loss, late_weighed=None):
    """导出加练人员名单
    not_weighed: 今日未称重学员列表
    low_loss: 今日掉秤<0.2斤的学员列表
    late_weighed: 超过8:01称重的学员列表
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

    # Sheet 3: 超过8:01称重
    ws3 = wb.create_sheet(title='超时称重(8点01分后)')
    _write_extra_sheet(ws3, '超过8:01称重学员', late_weighed, is_not_weighed=False, is_late=True)

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
