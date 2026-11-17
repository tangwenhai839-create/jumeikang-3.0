import { Card, Statistic, Progress, Row, Col } from "antd";
import {
  DoorClosed,
  BedDouble,
  UserCheck,
  Bed,
  Snowflake,
  Wind,
  TrendingUp,
} from "lucide-react";
import type { Stats } from "@/types";

interface Props {
  stats: Stats | null;
  loading?: boolean;
}

export default function StatCards({ stats, loading }: Props) {
  const cards = [
    {
      title: "房间总数",
      value: stats?.totalRooms ?? 0,
      icon: <DoorClosed size={20} />,
      color: "#1e3a5f",
    },
    {
      title: "总床位数量",
      value: stats?.totalBeds ?? 0,
      icon: <BedDouble size={20} />,
      color: "#2c5282",
    },
    {
      title: "当前入住人数",
      value: stats?.occupiedCount ?? 0,
      icon: <UserCheck size={20} />,
      color: "#d97706",
    },
    {
      title: "剩余床位",
      value: stats?.availableBeds ?? 0,
      icon: <Bed size={20} />,
      color: "#059669",
    },
    {
      title: "空调房数量",
      value: stats?.acRooms ?? 0,
      icon: <Snowflake size={20} />,
      color: "#0891b2",
    },
    {
      title: "非空调房数量",
      value: stats?.nonAcRooms ?? 0,
      icon: <Wind size={20} />,
      color: "#6b7280",
    },
  ];

  return (
    <div style={{ marginBottom: 24 }}>
      <Row gutter={[16, 16]}>
        {cards.map((c) => (
          <Col xs={12} sm={12} md={8} lg={4} key={c.title}>
            <Card
              hoverable
              loading={loading}
              style={{ borderRadius: 12, height: "100%" }}
              styles={{ body: { padding: 20 } }}
            >
              <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
                <div
                  style={{
                    width: 44,
                    height: 44,
                    borderRadius: 10,
                    background: `${c.color}15`,
                    color: c.color,
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    flexShrink: 0,
                  }}
                >
                  {c.icon}
                </div>
                <div style={{ minWidth: 0 }}>
                  <div
                    style={{
                      fontSize: 12,
                      color: "#6b7280",
                      marginBottom: 2,
                      whiteSpace: "nowrap",
                    }}
                  >
                    {c.title}
                  </div>
                  <Statistic
                    value={c.value}
                    valueStyle={{
                      fontSize: 22,
                      fontWeight: 700,
                      color: c.color,
                      lineHeight: 1,
                    }}
                  />
                </div>
              </div>
            </Card>
          </Col>
        ))}
        <Col xs={24} sm={12} md={8} lg={6}>
          <Card
            loading={loading}
            style={{ borderRadius: 12, height: "100%" }}
            styles={{ body: { padding: 20 } }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
              <Progress
                type="circle"
                percent={stats?.occupancyRate ?? 0}
                size={64}
                strokeColor="#d97706"
                format={(p) => `${p}%`}
              />
              <div>
                <div
                  style={{
                    fontSize: 12,
                    color: "#6b7280",
                    marginBottom: 4,
                    display: "flex",
                    alignItems: "center",
                    gap: 4,
                  }}
                >
                  <TrendingUp size={14} /> 入住率
                </div>
                <div style={{ fontSize: 13, color: "#374151" }}>
                  已住 {stats?.occupiedCount ?? 0} / {stats?.totalBeds ?? 0} 床
                </div>
              </div>
            </div>
          </Card>
        </Col>
      </Row>
    </div>
  );
}
