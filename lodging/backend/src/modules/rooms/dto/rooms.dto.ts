import { IsString, IsBoolean, IsOptional, IsIn, IsInt, Min, Max } from 'class-validator';
import { Type } from 'class-transformer';

// 房型
export const ROOM_TYPES = ['SINGLE', 'DOUBLE', 'TRIPLE', 'QUAD'] as const;

export class CreateRoomDto {
  @IsString()
  roomNumber: string;

  @IsIn(ROOM_TYPES)
  roomType: string;

  @IsBoolean()
  hasAirConditioner: boolean;

  @IsOptional()
  @IsString()
  remark?: string;
}

export class UpdateRoomDto {
  @IsOptional()
  @IsString()
  roomNumber?: string;

  @IsOptional()
  @IsIn(ROOM_TYPES)
  roomType?: string;

  @IsOptional()
  @IsBoolean()
  hasAirConditioner?: boolean;

  @IsOptional()
  @IsString()
  remark?: string;
}

export class BatchCreateRoomDto {
  @IsIn(ROOM_TYPES)
  roomType: string;

  @IsBoolean()
  hasAirConditioner: boolean;

  @IsString()
  // 起始房间号，例如 "101"
  startNumber: string;

  @IsInt()
  @Min(1)
  @Max(100)
  @Type(() => Number)
  count: number;

  @IsOptional()
  @IsString()
  remark?: string;
}
