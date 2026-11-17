import { Injectable, BadRequestException } from '@nestjs/common';
import { Response } from 'express';
import * as ExcelJS from 'exceljs';
import { PrismaService } from '../../prisma/prisma.service';
import { CAPACITY_MAP, calcRoomStatus, RoomType } from '../../common/constants';
import { RoomsService } from '../rooms/rooms.service';

// 房型中文 -> 枚举
const ROOM_TYPE_MAP: Record<string, RoomType> = {
  单人间: 'SINGLE',
  单人: 'SINGLE',
  单: 'SINGLE',
  '1': 'SINGLE',
  '1人间': 'SINGLE',
  双人间: 'DOUBLE',
  双人: 'DOUBLE',
  双: 'DOUBLE',
  '2': 'DOUBLE',
  '2人间': 'DOUBLE',
  三人间: 'TRIPLE',
  三人: 'TRIPLE',
  三: 'TRIPLE',
  '3': 'TRIPLE',
  '3人间': 'TRIPLE',
  四人间: 'QUAD',
  四人: 'QUAD',
  四: 'QUAD',
  '4': 'QUAD',
  '4人间': 'QUAD',
};

// 空调文本 -> 布尔
function parseAirConditioner(val: any): boolean | null {
  if (val === undefined || val === null || val === '') return null;
  const s = String(val).trim();
  if (['是', 'yes', 'Y', 'y', 'true', '1', '空调', '空调房'].includes(s)) return true;
  if (['否', 'no', 'N', 'n', 'false', '0', '非空调', '非空调房'].includes(s)) return false;
  return null;
}

function normalizeRoomType(val: any): RoomType | null {
  if (val === undefined || val === null || val === '') return null;
  const s = String(val).trim();
  if (ROOM_TYPE_MAP[s]) return ROOM_TYPE_MAP[s];
  const upper = s.toUpperCase();
  if (['SINGLE', 'DOUBLE', 'TRIPLE', 'QUAD'].includes(upper)) return upper as RoomType;
  return null;
}

function parseStudent(val: any): boolean | null {
  if (val === undefined || val === null || val === '') return null;
  const s = String(val).trim();
  if (['是', 'yes', 'Y', 'y', 'true', '1', '学生'].includes(s)) return true;
  if (['否', 'no', 'N', 'n', 'false', '0', '非学生', '不是学生'].includes(s)) return false;
  return null;
}

@Injectable()
export class ImportService {
  constructor(
    private readonly prisma: PrismaService,
    private readonly roomsService: RoomsService,
  ) {}

  /**
   * 下载房间模板
   */
  async downloadRoomTemplate(res: Response) {
    const wb = new ExcelJS.Workbook();
    const ws = wb.addWorksheet('房间导入模板');

    // 列定义：房间号、几人间、是否空调房、备注
    ws.columns = [
      { header: '房间号 *', key: 'roomNumber', width: 16 },
      { header: '几人间 *', key: 'roomType', width: 14 },
      { header: '是否空调房 *', key: 'hasAirConditioner', width: 16 },
      { header: '备注', key: 'remark', width: 24 },
    ];

    // 表头样式
    ws.getRow(1).font = { bold: true, color: { argb: 'FFFFFFFF' } };
    ws.getRow(1).fill = {
      type: 'pattern',
      pattern: 'solid',
      fgColor: { argb: 'FF1E3A5F' },
    };
    ws.getRow(1).alignment = { vertical: 'middle', horizontal: 'center' };
    ws.getRow(1).height = 22;

    // 示例数据
    ws.addRow({ roomNumber: '301', roomType: '四人间', hasAirConditioner: '是', remark: '新楼南侧' });
    ws.addRow({ roomNumber: '302', roomType: '双人间', hasAirConditioner: '是' });
    ws.addRow({ roomNumber: '303', roomType: '单人间', hasAirConditioner: '否' });

    // 注释说明
    const helpSheet = wb.addWorksheet('填写说明');
    helpSheet.columns = [{ width: 22 }, { width: 60 }];
    helpSheet.addRow(['字段', '说明']);
    helpSheet.addRow(['房间号 *', '必填，20 字符内，同一系统内不可重复，例如 101、A201']);
    helpSheet.addRow(['几人间 *', '必填，支持填写：单人间/双人间/三人间/四人间（或 1/2/3/4）']);
    helpSheet.addRow(['是否空调房 *', '必填，是/否']);
    helpSheet.addRow(['备注', '可选']);
    helpSheet.getRow(1).font = { bold: true };
    helpSheet.getRow(1).fill = {
      type: 'pattern',
      pattern: 'solid',
      fgColor: { argb: 'FFEFEFEF' },
    };

    res.setHeader(
      'Content-Type',
      'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    );
    res.setHeader('Content-Disposition', `attachment; filename="rooms_template.xlsx"`);
    await wb.xlsx.write(res);
    res.end();
  }

  /**
   * 下载学员模板
   */
  async downloadResidentTemplate(res: Response) {
    const wb = new ExcelJS.Workbook();
    const ws = wb.addWorksheet('学员导入模板');

    ws.columns = [
      { header: '姓名 *', key: 'name', width: 14 },
      { header: '手机号 *', key: 'phone', width: 16 },
      { header: '是否学生 *', key: 'isStudent', width: 12 },
      { header: '房间号 *', key: 'roomNumber', width: 14 },
      { header: '床位号', key: 'bedNumber', width: 10 },
      { header: '备注', key: 'remark', width: 24 },
    ];

    ws.getRow(1).font = { bold: true, color: { argb: 'FFFFFFFF' } };
    ws.getRow(1).fill = {
      type: 'pattern',
      pattern: 'solid',
      fgColor: { argb: 'FF1E3A5F' },
    };
    ws.getRow(1).alignment = { vertical: 'middle', horizontal: 'center' };
    ws.getRow(1).height = 22;

    // 示例数据

    const helpSheet = wb.addWorksheet('填写说明');
    helpSheet.columns = [{ width: 22 }, { width: 60 }];
    helpSheet.addRow(['字段', '说明']);
    helpSheet.addRow(['姓名 *', '必填，50 字符内']);
    helpSheet.addRow(['手机号 *', '必填，20 字符内']);
    helpSheet.addRow(['是否学生 *', '必填，是/否']);
    helpSheet.addRow(['房间号 *', '必填，需为系统中已存在的房间号']);
    helpSheet.addRow(['床位号', '可选，留空则自动分配最小空余床位；指定时须为房间内未占用床位']);
    helpSheet.addRow(['备注', '可选']);
    helpSheet.getRow(1).font = { bold: true };
    helpSheet.getRow(1).fill = {
      type: 'pattern',
      pattern: 'solid',
      fgColor: { argb: 'FFEFEFEF' },
    };

    res.setHeader(
      'Content-Type',
      'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    );
    res.setHeader(
      'Content-Disposition',
      `attachment; filename="residents_template.xlsx"`,
    );
    await wb.xlsx.write(res);
    res.end();
  }

  /**
   * 解析并导入房间
   * 返回：成功数、失败明细
   */
  async importRooms(buffer: Buffer) {
    const wb = new ExcelJS.Workbook();
    // 兼容 Node 24 Buffer 类型：转换为 ArrayBuffer
    const arrayBuffer = buffer.buffer.slice(
      buffer.byteOffset,
      buffer.byteOffset + buffer.byteLength,
    ) as ArrayBuffer;
    await wb.xlsx.load(arrayBuffer as any);
    const ws = wb.worksheets[0];
    if (!ws) throw new BadRequestException('Excel 文件为空');

    // 期望表头顺序：房间号 / 几人间 / 是否空调房 / 备注
    const headerRow = ws.getRow(1);
    const headers: string[] = [];
    headerRow.eachCell((cell, col) => {
      headers[col] = String(cell.value || '').trim();
    });

    const COL_ROOM_NO = headers.findIndex((h) => !!h && h.includes('房间号'));
    const COL_ROOM_TYPE = headers.findIndex(
      (h) => !!h && (h.includes('几人间') || h.includes('房型')),
    );
    const COL_AC = headers.findIndex((h) => !!h && h.includes('空调'));
    const COL_REMARK = headers.findIndex((h) => !!h && h.includes('备注'));

    if (COL_ROOM_NO < 0 || COL_ROOM_TYPE < 0 || COL_AC < 0) {
      throw new BadRequestException(
        '表头格式不正确，至少需要：房间号、几人间、是否空调房',
      );
    }

    const success: Array<{ row: number; roomNumber: string }> = [];
    const failed: Array<{ row: number; reason: string; data: any }> = [];

    for (let r = 2; r <= ws.rowCount; r++) {
      const row = ws.getRow(r);
      const roomNumber = String(row.getCell(COL_ROOM_NO).value || '').trim();
      const roomTypeRaw = row.getCell(COL_ROOM_TYPE).value;
      const acRaw = row.getCell(COL_AC).value;
      const remark = COL_REMARK >= 0 ? row.getCell(COL_REMARK).value : null;

      // 跳过空行
      if (!roomNumber && !roomTypeRaw && !acRaw) continue;

      const roomType = normalizeRoomType(roomTypeRaw);
      const hasAirConditioner = parseAirConditioner(acRaw);

      if (!roomNumber) {
        failed.push({ row: r, reason: '房间号为空', data: { roomNumber, roomTypeRaw } });
        continue;
      }
      if (!roomType) {
        failed.push({
          row: r,
          reason: `房型不合法：${roomTypeRaw}`,
          data: { roomNumber, roomTypeRaw },
        });
        continue;
      }
      if (hasAirConditioner === null) {
        failed.push({
          row: r,
          reason: `是否空调房必须为 是/否：${acRaw}`,
          data: { roomNumber, acRaw },
        });
        continue;
      }

      const capacity = CAPACITY_MAP[roomType];
      try {
        // 检查重复
        const exist = await this.prisma.room.findUnique({
          where: { roomNumber },
        });
        if (exist) {
          failed.push({
            row: r,
            reason: `房间号 ${roomNumber} 已存在`,
            data: { roomNumber },
          });
          continue;
        }

        await this.prisma.room.create({
          data: {
            roomNumber,
            roomType,
            hasAirConditioner,
            capacity,
            occupiedCount: 0,
            availableCount: capacity,
            status: 'AVAILABLE',
            remark: remark ? String(remark).trim() : null,
          },
        });
        success.push({ row: r, roomNumber });
      } catch (e: any) {
        failed.push({
          row: r,
          reason: e?.message || '数据库写入失败',
          data: { roomNumber },
        });
      }
    }

    return { successCount: success.length, failedCount: failed.length, success, failed };
  }

  /**
   * 解析并导入学员（同时完成入住）
   * 返回：成功数、失败明细
   */
  async importResidents(buffer: Buffer) {
    const wb = new ExcelJS.Workbook();
    const arrayBuffer = buffer.buffer.slice(
      buffer.byteOffset,
      buffer.byteOffset + buffer.byteLength,
    ) as ArrayBuffer;
    await wb.xlsx.load(arrayBuffer as any);
    const ws = wb.worksheets[0];
    if (!ws) throw new BadRequestException('Excel 文件为空');

    const headerRow = ws.getRow(1);
    const headers: string[] = [];
    headerRow.eachCell((cell, col) => {
      headers[col] = String(cell.value || '').trim();
    });

    const COL_NAME = headers.findIndex((h) => !!h && h.includes('姓名'));
    const COL_PHONE = headers.findIndex(
      (h) => !!h && (h.includes('手机号') || h.includes('电话')),
    );
    const COL_STUDENT = headers.findIndex((h) => !!h && h.includes('是否学生'));
    const COL_ROOM = headers.findIndex((h) => !!h && h.includes('房间号'));
    const COL_BED = headers.findIndex((h) => !!h && h.includes('床位号'));
    const COL_REMARK = headers.findIndex((h) => !!h && h.includes('备注'));

    if (COL_NAME < 0 || COL_PHONE < 0 || COL_STUDENT < 0 || COL_ROOM < 0) {
      throw new BadRequestException('表头格式不正确，至少需要：姓名、手机号、是否学生、房间号');
    }

    const success: Array<{ row: number; name: string; roomNumber: string; bedNumber: number }> = [];
    const failed: Array<{ row: number; reason: string; data: any }> = [];

    // 缓存：roomNumber -> Room（含现有入住人员）
    const roomCache = new Map<string, Awaited<ReturnType<typeof this.prisma.room.findUnique>>>();

    async function getRoom(roomNumber: string) {
      if (roomCache.has(roomNumber)) return roomCache.get(roomNumber);
      const r = await this.prisma.room.findUnique({
        where: { roomNumber },
        include: { residents: { where: { status: 'CHECKED_IN' } } },
      });
      roomCache.set(roomNumber, r);
      return r;
    }

    for (let r = 2; r <= ws.rowCount; r++) {
      const row = ws.getRow(r);
      const name = String(row.getCell(COL_NAME).value || '').trim();
      const phone = String(row.getCell(COL_PHONE).value || '').trim();
      const isStudentRaw = row.getCell(COL_STUDENT).value;
      const roomNumber = String(row.getCell(COL_ROOM).value || '').trim();
      const bedRaw = row.getCell(COL_BED).value;
      const remark = COL_REMARK >= 0 ? row.getCell(COL_REMARK).value : null;

      // 跳过空行
      if (!name && !phone && !roomNumber) continue;

      const isStudent = parseStudent(isStudentRaw);

      if (!name) {
        failed.push({ row: r, reason: '姓名为空', data: { name, phone, roomNumber } });
        continue;
      }
      if (!phone) {
        failed.push({ row: r, reason: '手机号为空', data: { name, phone, roomNumber } });
        continue;
      }
      if (isStudent === null) {
        failed.push({
          row: r,
          reason: `是否学生必须为 是/否：${isStudentRaw}`,
          data: { name, phone, roomNumber },
        });
        continue;
      }
      if (!roomNumber) {
        failed.push({ row: r, reason: '房间号为空', data: { name, phone, roomNumber } });
        continue;
      }

      const room = await getRoom.call(this, roomNumber);
      if (!room) {
        failed.push({
          row: r,
          reason: `房间号 ${roomNumber} 不存在`,
          data: { name, phone, roomNumber },
        });
        continue;
      }
      if (room.occupiedCount >= room.capacity) {
        failed.push({
          row: r,
          reason: `房间 ${roomNumber} 已满（${room.capacity}/${room.capacity}）`,
          data: { name, phone, roomNumber },
        });
        continue;
      }

      // 床位号：未指定则自动分配；指定则校验
      let bedNumber: number;
      const bedRawStr = bedRaw !== null && bedRaw !== undefined ? String(bedRaw).trim() : '';
      if (bedRawStr === '') {
        // 找最小空床
        const occupied = new Set(room.residents.map((x) => x.bedNumber));
        let pick = 0;
        for (let i = 1; i <= room.capacity; i++) {
          if (!occupied.has(i)) { pick = i; break; }
        }
        if (!pick) {
          failed.push({
            row: r,
            reason: `房间 ${roomNumber} 已无可用床位`,
            data: { name, phone, roomNumber },
          });
          continue;
        }
        bedNumber = pick;
      } else {
        const n = Number(bedRawStr);
        if (!Number.isInteger(n) || n < 1 || n > room.capacity) {
          failed.push({
            row: r,
            reason: `床位号 ${bedRawStr} 超出范围 1-${room.capacity}`,
            data: { name, phone, roomNumber, bedRaw },
          });
          continue;
        }
        if (room.residents.some((x) => x.bedNumber === n)) {
          failed.push({
            row: r,
            reason: `房间 ${roomNumber} 的 ${n}号床 已被占用`,
            data: { name, phone, roomNumber, bedNumber: n },
          });
          continue;
        }
        bedNumber = n;
      }

      try {
        await this.prisma.resident.create({
          data: {
            name,
            phone,
            isStudent,
            roomId: room.id,
            bedNumber,
            remark: remark ? String(remark).trim() : null,
            status: 'CHECKED_IN',
          },
        });
        // 实时刷新（保持原行为）
        await this.roomsService.refreshRoomStats(room.id);
        // 刷新缓存
        roomCache.set(roomNumber, await this.prisma.room.findUnique({
          where: { id: room.id },
          include: { residents: { where: { status: 'CHECKED_IN' } } },
        }));
        success.push({ row: r, name, roomNumber, bedNumber });
      } catch (e: any) {
        failed.push({
          row: r,
          reason: e?.message || '数据库写入失败',
          data: { name, phone, roomNumber },
        });
      }
    }

    return { successCount: success.length, failedCount: failed.length, success, failed };
  }
}
