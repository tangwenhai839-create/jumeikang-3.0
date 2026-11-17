import { Injectable, NotFoundException, BadRequestException } from '@nestjs/common';
import { PrismaService } from '../../prisma/prisma.service';
import { RoomsService } from '../rooms/rooms.service';
import { CheckInDto, UpdateStayDto } from './dto/residents.dto';

@Injectable()
export class ResidentsService {
  constructor(
    private readonly prisma: PrismaService,
    private readonly roomsService: RoomsService,
  ) {}

  async findByCampUser(campUserId: number) {
    const resident = await this.prisma.resident.findFirst({
      where: {
        status: 'CHECKED_IN',
        OR: [
          { campUserId },
          { remark: { contains: `学员ID：${campUserId}` } },
        ],
      },
      include: { room: true },
      orderBy: { checkInTime: 'desc' },
    });
    if (!resident) {
      throw new NotFoundException(`学员 #${campUserId} 当前没有住宿记录`);
    }
    return resident;
  }

  /**
   * 办理入住：自动分配最小可用床位
   */
  async checkIn(roomId: number, dto: CheckInDto) {
    const room = await this.prisma.room.findUnique({
      where: { id: roomId },
      include: {
        residents: {
          where: { status: 'CHECKED_IN' },
          select: { bedNumber: true, exclusiveUse: true },
        },
      },
    });

    if (!room) {
      throw new NotFoundException(`房间 #${roomId} 不存在`);
    }

    if (dto.campUserId) {
      const existing = await this.prisma.resident.findFirst({
        where: {
          status: 'CHECKED_IN',
          OR: [
            { campUserId: dto.campUserId },
            { remark: { contains: `学员ID：${dto.campUserId}` } },
          ],
        },
      });
      if (existing) {
        throw new BadRequestException('该学员已有在住记录，请使用修改住宿或先办理退房');
      }
    }

    // 校验是否已满
    if (room.status === 'FULL' || room.availableCount <= 0 || room.occupiedCount >= room.capacity) {
      throw new BadRequestException(`房间 ${room.roomNumber} 已满（${room.capacity}/${room.capacity}），无法继续入住`);
    }
    if (room.residents.some((resident) => resident.exclusiveUse)) {
      throw new BadRequestException(`房间 ${room.roomNumber} 已设置整间独住，无法继续入住`);
    }
    if (dto.exclusiveUse && room.residents.length > 0) {
      throw new BadRequestException('整间独住只能选择当前无人入住的房间');
    }

    // 找出最小可用床位号
    const occupiedBeds = new Set(room.residents.map((r) => r.bedNumber));
    let bedNumber = 1;
    for (let i = 1; i <= room.capacity; i++) {
      if (!occupiedBeds.has(i)) {
        bedNumber = i;
        break;
      }
    }

    // 创建入住记录
    const resident = await this.prisma.resident.create({
      data: {
        name: dto.name,
        phone: dto.phone,
        isStudent: dto.isStudent,
        campUserId: dto.campUserId || null,
        exclusiveUse: dto.exclusiveUse === true,
        roomId,
        bedNumber,
        remark: dto.remark || null,
        status: 'CHECKED_IN',
      },
      include: { room: true },
    });

    // 更新房间统计
    await this.roomsService.refreshRoomStats(roomId);

    return resident;
  }

  /**
   * 修改住宿：支持换房和切换整间独住；原入住历史记录保持为同一条。
   */
  async updateStay(residentId: number, dto: UpdateStayDto) {
    const resident = await this.prisma.resident.findUnique({ where: { id: residentId } });
    if (!resident || resident.status !== 'CHECKED_IN') {
      throw new NotFoundException(`在住人员 #${residentId} 不存在`);
    }

    const targetRoom = await this.prisma.room.findUnique({
      where: { id: dto.roomId },
      include: { residents: { where: { status: 'CHECKED_IN' } } },
    });
    if (!targetRoom) {
      throw new NotFoundException(`房间 #${dto.roomId} 不存在`);
    }

    const otherResidents = targetRoom.residents.filter((item) => item.id !== residentId);
    if (otherResidents.some((item) => item.exclusiveUse)) {
      throw new BadRequestException(`房间 ${targetRoom.roomNumber} 已设置整间独住`);
    }
    if (dto.exclusiveUse && otherResidents.length > 0) {
      throw new BadRequestException('整间独住只能选择除当前学员外无人入住的房间');
    }
    if (!dto.exclusiveUse && otherResidents.length >= targetRoom.capacity) {
      throw new BadRequestException(`房间 ${targetRoom.roomNumber} 已满`);
    }

    let bedNumber = resident.bedNumber;
    if (resident.roomId !== dto.roomId) {
      const occupiedBeds = new Set(otherResidents.map((item) => item.bedNumber));
      bedNumber = 0;
      for (let i = 1; i <= targetRoom.capacity; i++) {
        if (!occupiedBeds.has(i)) {
          bedNumber = i;
          break;
        }
      }
      if (!bedNumber) {
        throw new BadRequestException(`房间 ${targetRoom.roomNumber} 没有可用床位`);
      }
    }

    const oldRoomId = resident.roomId;
    await this.prisma.resident.update({
      where: { id: residentId },
      data: {
        roomId: dto.roomId,
        bedNumber,
        exclusiveUse: dto.exclusiveUse,
        name: dto.name ?? resident.name,
        phone: dto.phone ?? resident.phone,
      },
    });

    if (oldRoomId !== dto.roomId) {
      await this.roomsService.refreshRoomStats(oldRoomId);
    }
    await this.roomsService.refreshRoomStats(dto.roomId);

    return this.prisma.resident.findUnique({
      where: { id: residentId },
      include: { room: true },
    });
  }

  /**
   * 办理退房：标记 CHECKED_OUT，记录退房时间，更新房间统计
   */
  async checkOut(roomId: number, residentId: number) {
    const resident = await this.prisma.resident.findFirst({
      where: { id: residentId, roomId },
    });

    if (!resident) {
      throw new NotFoundException(`入住人员 #${residentId} 不存在于房间 #${roomId}`);
    }

    if (resident.status === 'CHECKED_OUT') {
      throw new BadRequestException('该人员已退房，无需重复操作');
    }

    const updated = await this.prisma.resident.update({
      where: { id: residentId },
      data: {
        status: 'CHECKED_OUT',
        checkOutTime: new Date(),
      },
      include: { room: true },
    });

    // 更新房间统计
    await this.roomsService.refreshRoomStats(roomId);

    return updated;
  }
}
