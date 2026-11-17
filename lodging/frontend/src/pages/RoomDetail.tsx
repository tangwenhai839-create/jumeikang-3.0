import { useEffect, useState } from "react";
import {
  useParams,
  useNavigate,
} from "react-router-dom";
import {
  Card,
  Button,
  Tag,
  Spin,
  Empty,
  Popconfirm,
  message,
  Descriptions,
  Space,
} from "antd";
import {
  ArrowLeft,
  UserPlus,
  LogOut,
  Snowflake,
  User,
  Phone,
  Clock,
} from "lucide-react";
import dayjs from "dayjs";
import CheckInModal from "@/components/CheckInModal";
import { roomsApi, residentsApi } from "@/api";
import {
  ROOM_TYPE_LABEL,
  ROOM_STATUS_LABEL,
  ROOM_STATUS_COLOR,
  type Room,
} from "@/types";

export default function RoomDetail() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [room, setRoom] = useState<Room | null>(null);
  const [loading, setLoading] = useState(true);
  const [checkInOpen, setCheckInOpen] = useState(false);

  const roomId = Number(id);

  const load = async () => {
    setLoading(true);
    try {
      const data = await roomsApi.detail(roomId);
      setRoom(data);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (roomId) load();
  }, [roomId]);

  const handleCheckOut = async (residentId: number, name: string) => {
    await residentsApi.checkOut(roomId, residentId);
    message.success(`${name} 已办理退房`);
    load();
  };

  if (loading) {
    return (
      <div style={{ textAlign: "center", padding: 80 }}>
        <Spin size="large" />
      </div>
    );
  }

  if (!room) {
    return <Empty description="房间不存在" />;
  }

  // 构造床位状态列表
  const residentList = room.residents || [];
  const exclusiveResident = residentList.find((resident) => resident.exclusiveUse);
  const beds = Array.from({ length: room.capacity }, (_, i) => {
    const bedNumber = i + 1;
    const resident = residentList.find((r) => r.bedNumber === bedNumber);
    return { bedNumber, resident };
  });

  const isFull = room.status === "FULL" || room.availableCount <= 0;

  return (
    <div>
      <div style={{ marginBottom: 16, display: "flex", alignItems: "center", gap: 8 }}>
        <Button
          icon={<ArrowLeft size={14} />}
          onClick={() => navigate("/rooms")}
          type="text"
        />
        <h2 style={{ margin: 0, fontSize: 20, fontWeight: 700 }}>
          {room.roomNumber} 房间详情
        </h2>
        <Tag color={ROOM_STATUS_COLOR[room.status]} style={{ marginLeft: 8 }}>
          {ROOM_STATUS_LABEL[room.status]}
        </Tag>
      </div>

      {/* 房间信息卡片 */}
      <Card style={{ borderRadius: 12, marginBottom: 16 }}>
        <Descriptions column={{ xs: 1, sm: 2, md: 4 }} size="small">
          <Descriptions.Item label="房间号">{room.roomNumber}</Descriptions.Item>
          <Descriptions.Item label="房型">
            {ROOM_TYPE_LABEL[room.roomType]}
          </Descriptions.Item>
          <Descriptions.Item label="空调">
            {room.hasAirConditioner ? (
              <span style={{ color: "#0891b2" }}>
                <Snowflake size={12} style={{ verticalAlign: -1 }} /> 空调房
              </span>
            ) : (
              "非空调房"
            )}
          </Descriptions.Item>
          <Descriptions.Item label="入住情况">
            <span style={{ fontWeight: 600 }}>
              {room.occupiedCount} / {room.capacity} 人
            </span>
            <span style={{ marginLeft: 12, color: room.availableCount > 0 ? "#059669" : "#ef4444" }}>
              剩余 {room.availableCount} 个床位
            </span>
          </Descriptions.Item>
          {exclusiveResident && (
            <Descriptions.Item label="独住状态">
              <Tag color="orange">{exclusiveResident.name} 整间独住</Tag>
            </Descriptions.Item>
          )}
          {room.remark && (
            <Descriptions.Item label="备注" span={4}>
              {room.remark}
            </Descriptions.Item>
          )}
        </Descriptions>
      </Card>

      {/* 床位列表 */}
      <Card
        title="床位状态"
        extra={
          <Button
            type="primary"
            icon={<UserPlus size={14} />}
            disabled={isFull}
            onClick={() => setCheckInOpen(true)}
          >
            {isFull ? "房间已满" : "添加入住人员"}
          </Button>
        }
        style={{ borderRadius: 12 }}
      >
        <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
          {beds.map(({ bedNumber, resident }) => (
            <div
              key={bedNumber}
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                padding: "14px 16px",
                borderRadius: 10,
                border: `1px solid ${
                  resident ? "#1e3a5f40" : exclusiveResident ? "#f59e0b" : "#e5e7eb"
                }`,
                background: resident ? "#f0f5ff" : exclusiveResident ? "#fffbeb" : "#fafafa",
              }}
            >
              <div style={{ display: "flex", alignItems: "center", gap: 16, flex: 1, flexWrap: "wrap" }}>
                <div
                  style={{
                    width: 40,
                    height: 40,
                    borderRadius: 10,
                    background: resident ? "#1e3a5f" : "#f3f4f6",
                    color: resident ? "#fff" : "#9ca3af",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    fontSize: 12,
                    fontWeight: 600,
                    flexShrink: 0,
                  }}
                >
                  {resident ? <User size={18} /> : `${bedNumber}床`}
                </div>
                <div style={{ minWidth: 60 }}>
                  <div style={{ fontSize: 13, color: "#6b7280" }}>{bedNumber}号床</div>
                </div>
                {resident ? (
                  <>
                    <div style={{ fontSize: 15, fontWeight: 600, color: "#1f2937" }}>
                      {resident.name}
                    </div>
                    <Space size="small" wrap>
                      <Tag
                        color="blue"
                        style={{ margin: 0 }}
                      >
                        <Phone size={10} style={{ verticalAlign: -1 }} /> {resident.phone}
                      </Tag>
                      {resident.isStudent && (
                        <Tag color="geekblue" style={{ margin: 0 }}>学生</Tag>
                      )}
                      {resident.exclusiveUse && (
                        <Tag color="orange" style={{ margin: 0 }}>整间独住</Tag>
                      )}
                      <Tag
                        color="default"
                        style={{ margin: 0 }}
                      >
                        <Clock size={10} style={{ verticalAlign: -1 }} />
                        {dayjs(resident.checkInTime).format("YYYY-MM-DD HH:mm")}
                      </Tag>
                      {resident.remark && (
                        <Tag color="orange" style={{ margin: 0 }}>{resident.remark}</Tag>
                      )}
                    </Space>
                  </>
                ) : (
                  <Tag color={exclusiveResident ? "orange" : "success"} style={{ margin: 0 }}>
                    {exclusiveResident ? "独住预留" : "空闲"}
                  </Tag>
                )}
              </div>
              {resident && (
                <Popconfirm
                  title={`确认办理 ${resident.name} 退房？`}
                  onConfirm={() => handleCheckOut(resident.id, resident.name)}
                >
                  <Button danger size="small" icon={<LogOut size={13} />}>
                    办理退房
                  </Button>
                </Popconfirm>
              )}
            </div>
          ))}
        </div>
      </Card>

      <CheckInModal
        open={checkInOpen}
        roomId={roomId}
        bedNumber={null}
        onClose={() => setCheckInOpen(false)}
        onSuccess={() => {
          message.success("入住办理成功");
          load();
        }}
      />
    </div>
  );
}
