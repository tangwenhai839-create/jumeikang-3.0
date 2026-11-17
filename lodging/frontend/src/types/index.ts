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

// 房型中文
export const ROOM_TYPE_LABEL: Record<RoomType, string> = {
  SINGLE: '单人间',
  DOUBLE: '双人间',
  TRIPLE: '三人间',
  QUAD: '四人间',
};

// 房间状态中文
export const ROOM_STATUS_LABEL: Record<RoomStatus, string> = {
  AVAILABLE: '空闲',
  PARTIALLY: '入住中',
  FULL: '已满',
};

// 房间状态颜色
export const ROOM_STATUS_COLOR: Record<RoomStatus, string> = {
  AVAILABLE: 'green',
  PARTIALLY: 'gold',
  FULL: 'red',
};

export interface Resident {
  id: number;
  name: string;
  phone: string;
  isStudent: boolean;
  campUserId: number | null;
  exclusiveUse: boolean;
  roomId: number;
  bedNumber: number;
  checkInTime: string;
  checkOutTime: string | null;
  status: ResidentStatus;
  remark: string | null;
  room?: { roomNumber: string; roomType: string };
}

export interface Room {
  id: number;
  roomNumber: string;
  roomType: RoomType;
  hasAirConditioner: boolean;
  capacity: number;
  occupiedCount: number;
  availableCount: number;
  status: RoomStatus;
  remark: string | null;
  createdTime: string;
  updatedTime: string;
  residents?: Resident[];
}

export interface CheckInPayload {
  name: string;
  phone: string;
  isStudent: boolean;
  remark?: string;
  campUserId?: number;
  exclusiveUse?: boolean;
}

export interface CreateRoomPayload {
  roomNumber: string;
  roomType: RoomType;
  hasAirConditioner: boolean;
  remark?: string;
}

export interface BatchCreateRoomPayload {
  roomType: RoomType;
  hasAirConditioner: boolean;
  startNumber: string;
  count: number;
  remark?: string;
}

export interface Stats {
  totalRooms: number;
  totalBeds: number;
  occupiedCount: number;
  availableBeds: number;
  acRooms: number;
  nonAcRooms: number;
  occupancyRate: number;
  statusBreakdown: Record<string, number>;
  typeBreakdown: Array<{ roomType: string; count: number }>;
}

export interface RecordsPage {
  items: Resident[];
  total: number;
  page: number;
  pageSize: number;
}
