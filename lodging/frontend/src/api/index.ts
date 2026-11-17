import axios from 'axios';
import { message } from 'antd';
import type {
  Room,
  CheckInPayload,
  CreateRoomPayload,
  BatchCreateRoomPayload,
  Stats,
  RecordsPage,
  Resident,
} from '@/types';

const http = axios.create({
  baseURL: import.meta.env.VITE_API_BASE || '/api',
  timeout: 15000,
});

// 响应拦截：统一错误处理
http.interceptors.response.use(
  (resp) => resp.data,
  (error) => {
    const msg =
      error?.response?.data?.message ||
      error?.message ||
      '请求失败，请稍后重试';
    message.error(msg);
    return Promise.reject(error);
  },
);

// 房间 API
export const roomsApi = {
  list: (params?: {
    keyword?: string;
    roomType?: string;
    hasAirConditioner?: string;
    status?: string;
  }) => http.get<unknown, Room[]>('/rooms', { params }),

  detail: (id: number) => http.get<unknown, Room>(`/rooms/${id}`),

  create: (payload: CreateRoomPayload) => http.post<unknown, Room>('/rooms', payload),

  batchCreate: (payload: BatchCreateRoomPayload) =>
    http.post<unknown, { created: number; roomNumbers: string[] }>('/rooms/batch', payload),

  update: (id: number, payload: Partial<CreateRoomPayload>) =>
    http.patch<unknown, Room>(`/rooms/${id}`, payload),

  remove: (id: number) => http.delete<unknown, Room>(`/rooms/${id}`),
};

// 入住 / 退房 API
export const residentsApi = {
  checkIn: (roomId: number, payload: CheckInPayload) =>
    http.post<unknown, Resident>(`/rooms/${roomId}/check-in`, payload),

  checkOut: (roomId: number, residentId: number) =>
    http.post<unknown, Resident>(`/rooms/${roomId}/check-out/${residentId}`),
};

// 入住记录 API
export const recordsApi = {
  list: (params?: {
    name?: string;
    phone?: string;
    roomNumber?: string;
    startDate?: string;
    endDate?: string;
    status?: string;
    page?: number;
    pageSize?: number;
  }) => http.get<unknown, RecordsPage>('/records', { params }),
};

// 统计 API
export const statsApi = {
  get: () => http.get<unknown, Stats>('/stats'),
};

// 导入 API
export interface ImportResultItem {
  row: number;
  reason?: string;
  roomNumber?: string;
  name?: string;
  bedNumber?: number;
  data?: any;
}

export interface ImportResult {
  successCount: number;
  failedCount: number;
  success: ImportResultItem[];
  failed: ImportResultItem[];
}

export const importApi = {
  downloadRoomTemplate: () =>
    http.get('/import/template/rooms', { responseType: 'blob' }),
  downloadResidentTemplate: () =>
    http.get('/import/template/residents', { responseType: 'blob' }),
  importRooms: (file: File) => {
    const fd = new FormData();
    fd.append('file', file);
    return http.post<unknown, ImportResult>('/import/rooms', fd, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
  },
  importResidents: (file: File) => {
    const fd = new FormData();
    fd.append('file', file);
    return http.post<unknown, ImportResult>('/import/residents', fd, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
  },
};
