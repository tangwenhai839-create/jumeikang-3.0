import { Card, Tag, Tooltip } from "antd";
import { Snowflake, User } from "lucide-react";
import { useNavigate } from "react-router-dom";
import type { Room } from "@/types";
import {
  ROOM_TYPE_LABEL,
  ROOM_STATUS_LABEL,
  ROOM_STATUS_COLOR,
} from "@/types";

interface Props {
  room: Room;
}

// 状态边框颜色
const STATUS_BORDER: Record<string, string> = {
  AVAILABLE: "#10b981",
  PARTIALLY: "#f59e0b",
  FULL: "#ef4444",
};

const STATUS_BG: Record<string, string> = {
  AVAILABLE: "linear-gradient(135deg, #ecfdf5 0%, #ffffff 100%)",
  PARTIALLY: "linear-gradient(135deg, #fffbeb 0%, #ffffff 100%)",
  FULL: "linear-gradient(135deg, #fef2f2 0%, #ffffff 100%)",
};

export default function RoomCard({ room }: Props) {
  const navigate = useNavigate();

  // 构造床位可视化数组：1=已入住 0=空闲
  const residentList = room.residents || [];
  const exclusiveResident = residentList.find((resident) => resident.exclusiveUse);
  const beds: Array<{ occupied: boolean; reserved: boolean; resident?: string; isStudent?: boolean }> = [];
  for (let i = 1; i <= room.capacity; i++) {
    const r = residentList.find((x) => x.bedNumber === i);
    beds.push({
      occupied: !!r,
      reserved: !r && !!exclusiveResident,
      resident: r?.name,
      isStudent: r?.isStudent,
    });
  }

  const borderColor = STATUS_BORDER[room.status] || "#e5e7eb";

  return (
    <Card
      hoverable
      onClick={() => navigate(`/rooms/${room.id}`)}
      style={{
        borderRadius: 14,
        borderColor,
        borderWidth: 2,
        background: STATUS_BG[room.status],
        cursor: "pointer",
        transition: "all 0.2s ease",
        height: "100%",
      }}
      styles={{ body: { padding: 16 } }}
    >
      {/* 房间号 + 状态 */}
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "flex-start",
          marginBottom: 12,
        }}
      >
        <div>
          <div style={{ fontSize: 18, fontWeight: 700, color: "#1f2937" }}>
            {room.roomNumber}
          </div>
          <div style={{ fontSize: 12, color: "#6b7280", marginTop: 2 }}>
            {ROOM_TYPE_LABEL[room.roomType]}
            {room.hasAirConditioner && (
              <span style={{ marginLeft: 6, color: "#0891b2" }}>
                <Snowflake size={11} style={{ verticalAlign: -1 }} /> 空调房
              </span>
            )}
          </div>
        </div>
        <Tag color={ROOM_STATUS_COLOR[room.status]} style={{ margin: 0 }}>
          {ROOM_STATUS_LABEL[room.status]}
        </Tag>
      </div>

      {/* 床位可视化 */}
      <div
        style={{
          display: "flex",
          gap: 6,
          flexWrap: "wrap",
          marginBottom: 12,
        }}
      >
        {beds.map((b, idx) => (
          <Tooltip
            key={idx}
            title={b.occupied ? `${b.resident}${b.isStudent ? "（学生）" : ""}` : b.reserved ? "整间独住预留" : "空闲床位"}
          >
            <div
              style={{
                width: 30,
                height: 30,
                borderRadius: 8,
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                background: b.occupied ? "#1e3a5f" : b.reserved ? "#fef3c7" : "#f3f4f6",
                color: b.occupied ? "#fff" : b.reserved ? "#b45309" : "#9ca3af",
                border: b.occupied ? "none" : b.reserved ? "1px solid #f59e0b" : "1px dashed #d1d5db",
                fontSize: 14,
                transition: "transform 0.15s",
              }}
            >
              {b.occupied ? <User size={15} /> : b.reserved ? "锁" : "○"}
            </div>
          </Tooltip>
        ))}
      </div>

      {/* 入住人员列表 */}
      <div style={{ minHeight: 28, marginBottom: 8 }}>
        {residentList.length > 0 ? (
          residentList.map((r) => (
            <div
              key={r.id}
              style={{
                fontSize: 12,
                color: "#374151",
                marginBottom: 2,
                display: "flex",
                alignItems: "center",
                gap: 4,
              }}
            >
              <span style={{ color: "#1e3a5f" }}>👤</span>
              <span>{r.name}</span>
              <span style={{ color: "#9ca3af" }}>·{r.bedNumber}号床</span>
              {r.isStudent && (
                <Tag
                  color="blue"
                  style={{ fontSize: 10, lineHeight: "16px", padding: "0 4px", margin: 0 }}
                >
                  学生
                </Tag>
              )}
              {r.exclusiveUse && (
                <Tag color="orange" style={{ fontSize: 10, lineHeight: "16px", padding: "0 4px", margin: 0 }}>
                  整间独住
                </Tag>
              )}
            </div>
          ))
        ) : (
          <div style={{ fontSize: 12, color: "#9ca3af" }}>暂无入住人员</div>
        )}
      </div>

      {/* 入住统计 */}
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          paddingTop: 8,
          borderTop: "1px solid #f3f4f6",
          fontSize: 12,
        }}
      >
        <span style={{ color: "#374151", fontWeight: 600 }}>
          已入住：{room.occupiedCount}/{room.capacity}人
        </span>
        <span style={{ color: room.availableCount > 0 ? "#059669" : "#ef4444", fontWeight: 600 }}>
          剩余：{room.availableCount}个床位
        </span>
      </div>
    </Card>
  );
}
