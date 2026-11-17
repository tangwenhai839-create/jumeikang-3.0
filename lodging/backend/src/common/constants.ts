// 房型
export type RoomType = 'SINGLE' | 'DOUBLE' | 'TRIPLE' | 'QUAD';

// 房间状态
export type RoomStatus = 'AVAILABLE' | 'PARTIALLY' | 'FULL';

// 入住人员状态
export type ResidentStatus = 'CHECKED_IN' | 'CHECKED_OUT';

// 房型 -> 最大容量
export const CAPACITY_MAP: Record<RoomType, number> = {
  SINGLE: 1,
  DOUBLE: 2,
  TRIPLE: 3,
  QUAD: 4,
};

// 房型中文映射
export const ROOM_TYPE_LABEL: Record<RoomType, string> = {
  SINGLE: '单人间',
  DOUBLE: '双人间',
  TRIPLE: '三人间',
  QUAD: '四人间',
};

// 房间状态中文映射
export const ROOM_STATUS_LABEL: Record<RoomStatus, string> = {
  AVAILABLE: '空闲',
  PARTIALLY: '入住中',
  FULL: '已满',
};

// 房间状态颜色（前端使用）
export const ROOM_STATUS_COLOR: Record<RoomStatus, string> = {
  AVAILABLE: 'green',
  PARTIALLY: 'gold',
  FULL: 'red',
};

/**
 * 根据入住人数与容量计算房间状态
 */
export function calcRoomStatus(occupied: number, capacity: number): RoomStatus {
  if (occupied <= 0) return 'AVAILABLE';
  if (occupied >= capacity) return 'FULL';
  return 'PARTIALLY';
}
