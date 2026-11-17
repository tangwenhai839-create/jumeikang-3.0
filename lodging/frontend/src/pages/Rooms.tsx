import { useEffect, useState, useCallback } from "react";
import {
  Table,
  Button,
  Input,
  Select,
  Space,
  Tag,
  Popconfirm,
  message,
  Card,
} from "antd";
import { Plus, SquareStack, Edit, Trash2, Search, ArrowLeft, Upload } from "lucide-react";
import { useNavigate } from "react-router-dom";
import RoomFormModal from "@/components/RoomFormModal";
import BatchCreateModal from "@/components/BatchCreateModal";
import ImportModal from "@/components/ImportModal";
import { roomsApi } from "@/api";
import {
  ROOM_TYPE_LABEL,
  ROOM_STATUS_LABEL,
  ROOM_STATUS_COLOR,
  type Room,
  type RoomType,
} from "@/types";

export default function Rooms() {
  const navigate = useNavigate();
  const [rooms, setRooms] = useState<Room[]>([]);
  const [loading, setLoading] = useState(false);
  const [formOpen, setFormOpen] = useState(false);
  const [batchOpen, setBatchOpen] = useState(false);
  const [importOpen, setImportOpen] = useState(false);
  const [editing, setEditing] = useState<Room | null>(null);
  const [filters, setFilters] = useState({
    keyword: "",
    roomType: "",
    hasAirConditioner: "",
    status: "",
  });

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const list = await roomsApi.list({
        keyword: filters.keyword || undefined,
        roomType: filters.roomType || undefined,
        hasAirConditioner: filters.hasAirConditioner || undefined,
        status: filters.status || undefined,
      });
      setRooms(list);
    } finally {
      setLoading(false);
    }
  }, [filters]);

  useEffect(() => {
    load();
  }, [load]);

  const handleDelete = async (room: Room) => {
    await roomsApi.remove(room.id);
    message.success(`房间 ${room.roomNumber} 已删除`);
    load();
  };

  const columns = [
    {
      title: "房间号",
      dataIndex: "roomNumber",
      key: "roomNumber",
      render: (v: string, record: Room) => (
        <a onClick={() => navigate(`/rooms/${record.id}`)} style={{ fontWeight: 600 }}>
          {v}
        </a>
      ),
    },
    {
      title: "房型",
      dataIndex: "roomType",
      key: "roomType",
      render: (v: RoomType) => ROOM_TYPE_LABEL[v],
    },
    {
      title: "空调",
      dataIndex: "hasAirConditioner",
      key: "hasAirConditioner",
      render: (v: boolean) =>
        v ? (
          <Tag color="cyan">空调房</Tag>
        ) : (
          <Tag color="default">非空调房</Tag>
        ),
    },
    {
      title: "容量",
      dataIndex: "capacity",
      key: "capacity",
      align: "center" as const,
    },
    {
      title: "入住人数",
      key: "occupied",
      align: "center" as const,
      render: (_: unknown, r: Room) => (
        <span style={{ fontWeight: 600 }}>
          {r.occupiedCount} / {r.capacity}
        </span>
      ),
    },
    {
      title: "剩余床位",
      dataIndex: "availableCount",
      key: "availableCount",
      align: "center" as const,
      render: (v: number) => (
        <span style={{ color: v > 0 ? "#059669" : "#ef4444", fontWeight: 600 }}>
          {v}
        </span>
      ),
    },
    {
      title: "状态",
      dataIndex: "status",
      key: "status",
      render: (v: Room["status"]) => (
        <Tag color={ROOM_STATUS_COLOR[v]}>{ROOM_STATUS_LABEL[v]}</Tag>
      ),
    },
    {
      title: "备注",
      dataIndex: "remark",
      key: "remark",
      ellipsis: true,
      render: (v: string | null) => v || "-",
    },
    {
      title: "操作",
      key: "action",
      width: 160,
      render: (_: unknown, r: Room) => (
        <Space>
          <Button
            type="link"
            size="small"
            icon={<Edit size={13} />}
            onClick={() => {
              setEditing(r);
              setFormOpen(true);
            }}
          >
            编辑
          </Button>
          <Popconfirm
            title="确认删除该房间？"
            description={r.occupiedCount > 0 ? "请先办理退房" : "删除后不可恢复"}
            onConfirm={() => handleDelete(r)}
            disabled={r.occupiedCount > 0}
          >
            <Button
              type="link"
              size="small"
              danger
              icon={<Trash2 size={13} />}
              disabled={r.occupiedCount > 0}
            >
              删除
            </Button>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <div>
      <div style={{ marginBottom: 16, display: "flex", alignItems: "center", gap: 8 }}>
        <Button
          icon={<ArrowLeft size={14} />}
          onClick={() => navigate("/")}
          type="text"
        />
        <h2 style={{ margin: 0, fontSize: 20, fontWeight: 700 }}>房间管理</h2>
      </div>

      <Card style={{ borderRadius: 12, marginBottom: 16 }}>
        <Space wrap size="middle">
          <Input
            prefix={<Search size={14} />}
            placeholder="搜索房间号"
            allowClear
            value={filters.keyword}
            onChange={(e) => setFilters({ ...filters, keyword: e.target.value })}
            style={{ width: 200 }}
          />
          <Select
            placeholder="房型"
            allowClear
            value={filters.roomType || undefined}
            onChange={(v) => setFilters({ ...filters, roomType: v || "" })}
            style={{ width: 120 }}
            options={(Object.keys(ROOM_TYPE_LABEL) as RoomType[]).map((t) => ({
              value: t,
              label: ROOM_TYPE_LABEL[t],
            }))}
          />
          <Select
            placeholder="空调类型"
            allowClear
            value={filters.hasAirConditioner || undefined}
            onChange={(v) =>
              setFilters({ ...filters, hasAirConditioner: v ?? "" })
            }
            style={{ width: 120 }}
            options={[
              { value: "true", label: "空调房" },
              { value: "false", label: "非空调房" },
            ]}
          />
          <Select
            placeholder="入住状态"
            allowClear
            value={filters.status || undefined}
            onChange={(v) => setFilters({ ...filters, status: v || "" })}
            style={{ width: 120 }}
            options={[
              { value: "AVAILABLE", label: "空闲" },
              { value: "PARTIALLY", label: "入住中" },
              { value: "FULL", label: "已满" },
            ]}
          />
          <Space style={{ marginLeft: "auto" }}>
            <Button
              type="primary"
              icon={<Plus size={14} />}
              onClick={() => {
                setEditing(null);
                setFormOpen(true);
              }}
            >
              添加房间
            </Button>
            <Button icon={<SquareStack size={14} />} onClick={() => setBatchOpen(true)}>
              批量创建
            </Button>
            <Button icon={<Upload size={14} />} onClick={() => setImportOpen(true)}>
              表格导入
            </Button>
          </Space>
        </Space>
      </Card>

      <Card style={{ borderRadius: 12 }}>
        <Table
          rowKey="id"
          columns={columns}
          dataSource={rooms}
          loading={loading}
          pagination={{ pageSize: 10, showSizeChanger: true, showTotal: (t) => `共 ${t} 条` }}
          scroll={{ x: 900 }}
        />
      </Card>

      <RoomFormModal
        open={formOpen}
        editingRoom={editing}
        onClose={() => setFormOpen(false)}
        onSuccess={() => {
          message.success(editing ? "房间已更新" : "房间已添加");
          load();
        }}
      />
      <BatchCreateModal
        open={batchOpen}
        onClose={() => setBatchOpen(false)}
        onSuccess={() => {
          message.success("批量创建成功");
          load();
        }}
      />
      <ImportModal
        open={importOpen}
        type="rooms"
        onClose={() => setImportOpen(false)}
        onSuccess={() => load()}
      />
    </div>
  );
}
