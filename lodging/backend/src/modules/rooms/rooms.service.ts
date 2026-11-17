import { Injectable, NotFoundException, BadRequestException } from '@nestjs/common';
import { PrismaService } from '../../prisma/prisma.service';
import { CAPACITY_MAP, calcRoomStatus, RoomType } from '../../common/constants';
import { CreateRoomDto, UpdateRoomDto, BatchCreateRoomDto } from './dto/rooms.dto';

@Injectable()
export class RoomsService {
  constructor(private readonly prisma: PrismaService) {}

  /**
   * 获取房间列表（支持筛选）
   */
  async findAll(query?: {
    keyword?: string;
    roomType?: string;
    hasAirConditioner?: string;
    status?: string;
  }) {
    const where: any = {};

    if (query?.keyword) {
      where.roomNumber = { contains: query.keyword };
    }
    if (query?.roomType) {
      where.roomType = query.roomType;
    }
    if (query?.hasAirConditioner !== undefined && query?.hasAirConditioner !== '') {
      where.hasAirConditioner = query.hasAirConditioner === 'true';
    }
    if (query?.status) {
      where.status = query.status;
    }

    const rooms = await this.prisma.room.findMany({
      where,
      orderBy: { roomNumber: 'asc' },
      include: {
        residents: {
          where: { status: 'CHECKED_IN' },
          orderBy: { bedNumber: 'asc' },
        },
      },
    });

    return rooms;
  }

  /**
   * 获取房间详情（含入住人员）
   */
  async findOne(id: number) {
    const room = await this.prisma.room.findUnique({
      where: { id },
      include: {
        residents: {
          where: { status: 'CHECKED_IN' },
          orderBy: { bedNumber: 'asc' },
        },
      },
    });

    if (!room) {
      throw new NotFoundException(`房间 #${id} 不存在`);
    }

    return room;
  }

  /**
   * 添加房间
   */
  async create(dto: CreateRoomDto) {
    const capacity = CAPACITY_MAP[dto.roomType as RoomType];

    // 检查房间号是否重复
    const exist = await this.prisma.room.findUnique({
      where: { roomNumber: dto.roomNumber },
    });
    if (exist) {
      throw new BadRequestException(`房间号 ${dto.roomNumber} 已存在`);
    }

    return this.prisma.room.create({
      data: {
        roomNumber: dto.roomNumber,
        roomType: dto.roomType,
        hasAirConditioner: dto.hasAirConditioner,
        capacity,
        occupiedCount: 0,
        availableCount: capacity,
        status: 'AVAILABLE',
        remark: dto.remark || null,
      },
      include: { residents: { where: { status: 'CHECKED_IN' } } },
    });
  }

  /**
   * 批量创建房间
   * 起始房间号作为字符串前缀+数字，例如 startNumber="101" count=3 -> 101,102,103
   * 也支持字母前缀如 "A201" -> A201,A202,A203
   */
  async batchCreate(dto: BatchCreateRoomDto) {
    const capacity = CAPACITY_MAP[dto.roomType as RoomType];

    // 解析起始房间号：分离字母前缀与数字部分
    const match = dto.startNumber.match(/^([A-Za-z]*?)(\d+)$/);
    if (!match) {
      throw new BadRequestException('起始房间号格式无效，应为字母前缀+数字，例如 101 或 A201');
    }
    const prefix = match[1];
    const startNum = parseInt(match[2], 10);
    const digits = match[2].length;

    // 检查是否已存在冲突的房间号
    const newNumbers: string[] = [];
    for (let i = 0; i < dto.count; i++) {
      const num = startNum + i;
      const numStr = String(num).padStart(digits, '0');
      newNumbers.push(`${prefix}${numStr}`);
    }

    const existing = await this.prisma.room.findMany({
      where: { roomNumber: { in: newNumbers } },
      select: { roomNumber: true },
    });
    if (existing.length > 0) {
      throw new BadRequestException(
        `以下房间号已存在: ${existing.map((r) => r.roomNumber).join(', ')}`,
      );
    }

    // 批量创建
    await this.prisma.room.createMany({
      data: newNumbers.map((roomNumber) => ({
        roomNumber,
        roomType: dto.roomType,
        hasAirConditioner: dto.hasAirConditioner,
        capacity,
        occupiedCount: 0,
        availableCount: capacity,
        status: 'AVAILABLE',
        remark: dto.remark || null,
      })),
    });

    return { created: newNumbers.length, roomNumbers: newNumbers };
  }

  /**
   * 编辑房间
   * 注意：修改房型会改变容量，需校验当前入住人数不超过新容量
   */
  async update(id: number, dto: UpdateRoomDto) {
    const room = await this.prisma.room.findUnique({ where: { id } });
    if (!room) {
      throw new NotFoundException(`房间 #${id} 不存在`);
    }

    // 房间号唯一性校验
    if (dto.roomNumber && dto.roomNumber !== room.roomNumber) {
      const exist = await this.prisma.room.findUnique({
        where: { roomNumber: dto.roomNumber },
      });
      if (exist && exist.id !== id) {
        throw new BadRequestException(`房间号 ${dto.roomNumber} 已存在`);
      }
    }

    // 若修改房型，校验当前入住人数
    let newCapacity = room.capacity;
    if (dto.roomType && dto.roomType !== room.roomType) {
      newCapacity = CAPACITY_MAP[dto.roomType as RoomType];
      if (room.occupiedCount > newCapacity) {
        throw new BadRequestException(
          `当前入住人数 ${room.occupiedCount} 超过新房型容量 ${newCapacity}，无法修改房型`,
        );
      }
    }

    const exclusiveResident = await this.prisma.resident.findFirst({
      where: { roomId: id, status: 'CHECKED_IN', exclusiveUse: true },
    });
    const newAvailable = exclusiveResident ? 0 : newCapacity - room.occupiedCount;
    const newStatus = exclusiveResident ? 'FULL' : calcRoomStatus(room.occupiedCount, newCapacity);

    return this.prisma.room.update({
      where: { id },
      data: {
        roomNumber: dto.roomNumber ?? room.roomNumber,
        roomType: dto.roomType ?? room.roomType,
        hasAirConditioner:
          dto.hasAirConditioner !== undefined ? dto.hasAirConditioner : room.hasAirConditioner,
        capacity: newCapacity,
        availableCount: newAvailable,
        status: newStatus,
        remark: dto.remark !== undefined ? dto.remark : room.remark,
      },
      include: { residents: { where: { status: 'CHECKED_IN' } } },
    });
  }

  /**
   * 删除房间（关联的入住人员会被级联删除）
   */
  async remove(id: number) {
    const room = await this.prisma.room.findUnique({ where: { id } });
    if (!room) {
      throw new NotFoundException(`房间 #${id} 不存在`);
    }
    if (room.occupiedCount > 0) {
      throw new BadRequestException(`房间 ${room.roomNumber} 仍有 ${room.occupiedCount} 人入住，请先办理退房`);
    }

    return this.prisma.room.delete({ where: { id } });
  }

  /**
   * 更新房间的入住统计（内部方法，供 residents 模块调用）
   */
  async refreshRoomStats(roomId: number) {
    const room = await this.prisma.room.findUnique({ where: { id: roomId } });
    if (!room) return;

    const activeResidents = await this.prisma.resident.findMany({
      where: { roomId, status: 'CHECKED_IN' },
      select: { exclusiveUse: true },
    });

    const occupiedCount = activeResidents.length;
    const exclusiveUse = activeResidents.some((resident) => resident.exclusiveUse);
    const availableCount = exclusiveUse ? 0 : room.capacity - occupiedCount;
    const status = exclusiveUse ? 'FULL' : calcRoomStatus(occupiedCount, room.capacity);
    await this.prisma.room.update({
      where: { id: roomId },
      data: {
        occupiedCount,
        availableCount,
        status,
      },
    });
  }
}
