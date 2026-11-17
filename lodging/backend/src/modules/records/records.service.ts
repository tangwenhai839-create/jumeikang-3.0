import { Injectable } from '@nestjs/common';
import { PrismaService } from '../../prisma/prisma.service';

@Injectable()
export class RecordsService {
  constructor(private readonly prisma: PrismaService) {}

  /**
   * 查询入住历史记录
   * 支持按姓名 / 手机号 / 房间号 / 日期范围筛选
   */
  async findAll(query?: {
    name?: string;
    phone?: string;
    roomNumber?: string;
    startDate?: string;
    endDate?: string;
    status?: string;
    page?: number;
    pageSize?: number;
  }) {
    const where: any = {};

    if (query?.name) {
      where.name = { contains: query.name };
    }
    if (query?.phone) {
      where.phone = { contains: query.phone };
    }
    if (query?.status) {
      where.status = query.status;
    }
    if (query?.roomNumber) {
      where.room = { roomNumber: { contains: query.roomNumber } };
    }

    // 日期范围筛选（基于入住时间）
    if (query?.startDate || query?.endDate) {
      where.checkInTime = {};
      if (query.startDate) {
        where.checkInTime.gte = new Date(query.startDate);
      }
      if (query.endDate) {
        // 结束日期包含当天全天
        const end = new Date(query.endDate);
        end.setHours(23, 59, 59, 999);
        where.checkInTime.lte = end;
      }
    }

    const page = query?.page && query.page > 0 ? Math.floor(query.page) : 1;
    const pageSize = query?.pageSize && query.pageSize > 0 ? Math.min(Math.floor(query.pageSize), 200) : 20;
    const skip = (page - 1) * pageSize;

    const [items, total] = await Promise.all([
      this.prisma.resident.findMany({
        where,
        include: { room: { select: { roomNumber: true, roomType: true } } },
        orderBy: { checkInTime: 'desc' },
        skip,
        take: pageSize,
      }),
      this.prisma.resident.count({ where }),
    ]);

    return { items, total, page, pageSize };
  }
}
