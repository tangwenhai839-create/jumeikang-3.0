import { Injectable } from '@nestjs/common';
import { PrismaService } from '../../prisma/prisma.service';

@Injectable()
export class StatsService {
  constructor(private readonly prisma: PrismaService) {}

  /**
   * 数据统计 Dashboard
   * 返回：房间总数、总床位、当前入住人数、剩余床位、空调房数量、非空调房数量、入住率
   */
  async getStats() {
    const rooms = await this.prisma.room.findMany({
      select: {
        capacity: true,
        occupiedCount: true,
        availableCount: true,
        hasAirConditioner: true,
      },
    });

    const totalRooms = rooms.length;
    const totalBeds = rooms.reduce((sum, r) => sum + r.capacity, 0);
    const occupiedCount = rooms.reduce((sum, r) => sum + r.occupiedCount, 0);
    const availableBeds = rooms.reduce((sum, r) => sum + r.availableCount, 0);
    const acRooms = rooms.filter((r) => r.hasAirConditioner).length;
    const nonAcRooms = totalRooms - acRooms;
    const occupancyRate = totalBeds > 0 ? Math.round(((totalBeds - availableBeds) / totalBeds) * 1000) / 10 : 0;

    // 按状态统计房间数
    const statusCount = await this.prisma.room.groupBy({
      by: ['status'],
      _count: { _all: true },
    });
    const statusMap: Record<string, number> = { AVAILABLE: 0, PARTIALLY: 0, FULL: 0 };
    statusCount.forEach((s) => {
      statusMap[s.status] = s._count._all;
    });

    // 按房型统计
    const typeCount = await this.prisma.room.groupBy({
      by: ['roomType'],
      _count: { _all: true },
    });

    return {
      totalRooms,
      totalBeds,
      occupiedCount,
      availableBeds,
      acRooms,
      nonAcRooms,
      occupancyRate,
      statusBreakdown: statusMap,
      typeBreakdown: typeCount.map((t) => ({ roomType: t.roomType, count: t._count._all })),
    };
  }
}
