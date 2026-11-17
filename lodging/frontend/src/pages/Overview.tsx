import { useEffect, useState, useMemo } from "react";
import { Row, Col, Tag, Input, Empty, Spin } from "antd";
import { Search } from "lucide-react";
import StatCards from "@/components/StatCards";
import RoomCard from "@/components/RoomCard";
import { roomsApi, statsApi } from "@/api";
import type { Room, Stats } from "@/types";
import { ROOM_TYPE_LABEL } from "@/types";

// 状态筛选标签
type StatusFilter = "ALL" | "AVAILABLE" | "PARTIALLY" | "FULL";
const STATUS_OPTIONS: { value: StatusFilter; label: string }[] = [
  { value: "ALL", label: "全部" },
  { value: "AVAILABLE", label: "空闲" },
  { value: "PARTIALLY", label: "入住中" },
  { value: "FULL", label: "已满" },
];

// 空调筛选标签
const AC_OPTIONS = [
  { value: true, label: "空调房" },
  { value: false, label: "非空调房" },
];

// 房型筛选标签
const TYPE_OPTIONS = [
  { value: "SINGLE", label: "单人间" },
  { value: "DOUBLE", label: "双人间" },
  { value: "TRIPLE", label: "三人间" },
  { value: "QUAD", label: "四人间" },
];

const { CheckableTag } = Tag;

export default function Overview() {
  const [rooms, setRooms] = useState<Room[]>([]);
  const [stats, setStats] = useState<Stats | null>(null);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("ALL");
  const [acFilter, setAcFilter] = useState<Set<boolean>>(new Set());
  const [typeFilter, setTypeFilter] = useState<Set<string>>(new Set());
  const [keyword, setKeyword] = useState("");

  const load = async () => {
    setLoading(true);
    try {
      const [roomList, s] = await Promise.all([roomsApi.list(), statsApi.get()]);
      setRooms(roomList);
      setStats(s);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  // 前端二次过滤（避免频繁请求后端）
  const filteredRooms = useMemo(() => {
    let list = rooms;
    // 状态筛选（单选）
    if (statusFilter !== "ALL") {
      list = list.filter((r) => r.status === statusFilter);
    }
    // 空调筛选（多选：都选或都不选 = 不过滤）
    if (acFilter.size === 1) {
      const val = Array.from(acFilter)[0];
      list = list.filter((r) => r.hasAirConditioner === val);
    }
    // 房型筛选（多选：都选或都不选 = 不过滤）
    if (typeFilter.size > 0 && typeFilter.size < TYPE_OPTIONS.length) {
      list = list.filter((r) => typeFilter.has(r.roomType));
    }
    // 关键词
    if (keyword.trim()) {
      const kw = keyword.trim();
      list = list.filter(
        (r) =>
          r.roomNumber.includes(kw) ||
          (r.residents || []).some((p) => p.name.includes(kw)),
      );
    }
    return list;
  }, [rooms, statusFilter, acFilter, typeFilter, keyword]);

  // 各状态数量
  const statusCounts = useMemo(() => {
    const map: Record<string, number> = { ALL: rooms.length, AVAILABLE: 0, PARTIALLY: 0, FULL: 0 };
    rooms.forEach((r) => { map[r.status] = (map[r.status] || 0) + 1; });
    return map;
  }, [rooms]);

  // 各房型数量
  const typeCounts = useMemo(() => {
    const map: Record<string, number> = {};
    rooms.forEach((r) => { map[r.roomType] = (map[r.roomType] || 0) + 1; });
    return map;
  }, [rooms]);

  // 空调数量
  const acCounts = useMemo(() => {
    const ac = rooms.filter((r) => r.hasAirConditioner).length;
    return { ac, nonAc: rooms.length - ac };
  }, [rooms]);

  const toggleAc = (val: boolean) => {
    setAcFilter((prev) => {
      const next = new Set(prev);
      if (next.has(val)) next.delete(val);
      else next.add(val);
      return next;
    });
  };

  const toggleType = (val: string) => {
    setTypeFilter((prev) => {
      const next = new Set(prev);
      if (next.has(val)) next.delete(val);
      else next.add(val);
      return next;
    });
  };

  return (
    <div>
      <StatCards stats={stats} loading={loading && !stats} />

      {/* 过滤工具栏 */}
      <div
        style={{
          display: "flex",
          flexDirection: "column",
          gap: 10,
          marginBottom: 16,
        }}
      >
        {/* 第一行：状态 + 搜索 */}
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            flexWrap: "wrap",
            gap: 12,
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: 6, flexWrap: "wrap" }}>
            {STATUS_OPTIONS.map((opt) => (
              <CheckableTag
                key={opt.value}
                checked={statusFilter === opt.value}
                onChange={() => setStatusFilter(opt.value)}
                style={{
                  padding: "4px 14px",
                  fontSize: 13,
                  borderRadius: 6,
                  border: `1px solid ${statusFilter === opt.value ? "#1e3a5f" : "#d9d9d9"}`,
                  background: statusFilter === opt.value ? "#1e3a5f" : "#fff",
                  color: statusFilter === opt.value ? "#fff" : "#374151",
                  cursor: "pointer",
                  transition: "all 0.15s",
                }}
              >
                {opt.label} ({statusCounts[opt.value]})
              </CheckableTag>
            ))}
          </div>
          <Input
            prefix={<Search size={14} />}
            placeholder="搜索房间号 / 入住人姓名"
            allowClear
            value={keyword}
            onChange={(e) => setKeyword(e.target.value)}
            style={{ width: 240, flexShrink: 0 }}
          />
        </div>

        {/* 第二行：空调 + 房型 */}
        <div style={{ display: "flex", alignItems: "center", gap: 24, flexWrap: "wrap" }}>
          {/* 空调筛选 */}
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <span style={{ fontSize: 12, color: "#6b7280", whiteSpace: "nowrap" }}>空调：</span>
            {AC_OPTIONS.map((opt) => (
              <CheckableTag
                key={opt.label}
                checked={acFilter.has(opt.value)}
                onChange={() => toggleAc(opt.value)}
                style={{
                  padding: "3px 10px",
                  fontSize: 12,
                  borderRadius: 4,
                  border: `1px solid ${acFilter.has(opt.value) ? "#0891b2" : "#d9d9d9"}`,
                  background: acFilter.has(opt.value) ? "#ecfeff" : "#fff",
                  color: acFilter.has(opt.value) ? "#0891b2" : "#374151",
                  cursor: "pointer",
                  transition: "all 0.15s",
                }}
              >
                {opt.label}
                {opt.value ? `(${acCounts.ac})` : `(${acCounts.nonAc})`}
              </CheckableTag>
            ))}
          </div>

          {/* 房型筛选 */}
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <span style={{ fontSize: 12, color: "#6b7280", whiteSpace: "nowrap" }}>房型：</span>
            {TYPE_OPTIONS.map((opt) => (
              <CheckableTag
                key={opt.value}
                checked={typeFilter.has(opt.value)}
                onChange={() => toggleType(opt.value)}
                style={{
                  padding: "3px 10px",
                  fontSize: 12,
                  borderRadius: 4,
                  border: `1px solid ${typeFilter.has(opt.value) ? "#d97706" : "#d9d9d9"}`,
                  background: typeFilter.has(opt.value) ? "#fffbeb" : "#fff",
                  color: typeFilter.has(opt.value) ? "#d97706" : "#374151",
                  cursor: "pointer",
                  transition: "all 0.15s",
                }}
              >
                {opt.label} ({typeCounts[opt.value] || 0})
              </CheckableTag>
            ))}
          </div>

          {/* 清除筛选 */}
          {(acFilter.size > 0 || typeFilter.size > 0 || statusFilter !== "ALL" || keyword.trim()) && (
            <Tag
              closable
              onClose={() => {
                setStatusFilter("ALL");
                setAcFilter(new Set());
                setTypeFilter(new Set());
                setKeyword("");
              }}
              style={{ cursor: "pointer", fontSize: 12 }}
            >
              清除全部筛选
            </Tag>
          )}
        </div>
      </div>

      <Spin spinning={loading}>
        {filteredRooms.length === 0 && !loading ? (
          <Empty description="暂无符合条件的房间" />
        ) : (
          <Row gutter={[16, 16]}>
            {filteredRooms.map((room) => (
              <Col xs={24} sm={12} md={8} lg={6} key={room.id}>
                <RoomCard room={room} />
              </Col>
            ))}
          </Row>
        )}
      </Spin>
    </div>
  );
}
