import { useEffect, useState } from "react";
import {
  Card,
  Table,
  Form,
  Input,
  Select,
  DatePicker,
  Button,
  Space,
  Tag,
} from "antd";
import { Search, RotateCcw, ArrowLeft, Upload } from "lucide-react";
import { useNavigate } from "react-router-dom";
import dayjs from "dayjs";
import { recordsApi } from "@/api";
import ImportModal from "@/components/ImportModal";
import {
  ROOM_TYPE_LABEL,
  type RecordsPage,
  type ResidentStatus,
} from "@/types";

const { RangePicker } = DatePicker;

export default function Records() {
  const navigate = useNavigate();
  const [form] = Form.useForm();
  const [data, setData] = useState<RecordsPage | null>(null);
  const [loading, setLoading] = useState(false);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);
  const [importOpen, setImportOpen] = useState(false);

  const load = async (p = page, ps = pageSize) => {
    setLoading(true);
    try {
      const values = form.getFieldsValue();
      const dateRange = values.dateRange;
      const result = await recordsApi.list({
        name: values.name || undefined,
        phone: values.phone || undefined,
        roomNumber: values.roomNumber || undefined,
        status: values.status || undefined,
        startDate: dateRange?.[0]?.format("YYYY-MM-DD"),
        endDate: dateRange?.[1]?.format("YYYY-MM-DD"),
        page: p,
        pageSize: ps,
      });
      setData(result);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load(1);
  }, []);

  const handleSearch = () => {
    setPage(1);
    load(1);
  };

  const handleReset = () => {
    form.resetFields();
    setPage(1);
    load(1);
  };

  const columns = [
    {
      title: "姓名",
      dataIndex: "name",
      key: "name",
      width: 100,
    },
    {
      title: "手机号",
      dataIndex: "phone",
      key: "phone",
      width: 130,
    },
    {
      title: "是否学生",
      dataIndex: "isStudent",
      key: "isStudent",
      width: 90,
      render: (v: boolean) =>
        v ? <Tag color="geekblue">学生</Tag> : <Tag>非学生</Tag>,
    },
    {
      title: "房间号",
      key: "roomNumber",
      width: 100,
      render: (_: unknown, r: any) => r.room?.roomNumber || "-",
    },
    {
      title: "房型",
      key: "roomType",
      width: 90,
      render: (_: unknown, r: any) =>
        r.room?.roomType ? ROOM_TYPE_LABEL[r.room.roomType as keyof typeof ROOM_TYPE_LABEL] : "-",
    },
    {
      title: "床位号",
      dataIndex: "bedNumber",
      key: "bedNumber",
      width: 80,
      align: "center" as const,
      render: (v: number) => `${v}号床`,
    },
    {
      title: "入住时间",
      dataIndex: "checkInTime",
      key: "checkInTime",
      width: 160,
      render: (v: string) => dayjs(v).format("YYYY-MM-DD HH:mm"),
    },
    {
      title: "退房时间",
      dataIndex: "checkOutTime",
      key: "checkOutTime",
      width: 160,
      render: (v: string | null) => (v ? dayjs(v).format("YYYY-MM-DD HH:mm") : "-"),
    },
    {
      title: "状态",
      dataIndex: "status",
      key: "status",
      width: 90,
      render: (v: ResidentStatus) =>
        v === "CHECKED_IN" ? (
          <Tag color="processing">在住</Tag>
        ) : (
          <Tag color="default">已退房</Tag>
        ),
    },
    {
      title: "备注",
      dataIndex: "remark",
      key: "remark",
      ellipsis: true,
      render: (v: string | null) => v || "-",
    },
  ];

  return (
    <div>
      <div
        style={{
          marginBottom: 16,
          display: "flex",
          alignItems: "center",
          gap: 8,
          flexWrap: "wrap",
        }}
      >
        <Button
          icon={<ArrowLeft size={14} />}
          onClick={() => navigate("/")}
          type="text"
        />
        <h2 style={{ margin: 0, fontSize: 20, fontWeight: 700 }}>入住记录</h2>
        <Button
          type="primary"
          icon={<Upload size={14} />}
          onClick={() => setImportOpen(true)}
          style={{ marginLeft: "auto" }}
        >
          批量导入学员
        </Button>
      </div>

      <Card style={{ borderRadius: 12, marginBottom: 16 }}>
        <Form form={form} layout="inline">
          <Space wrap size="middle" style={{ width: "100%" }}>
            <Form.Item name="name" label="姓名">
              <Input placeholder="按姓名查询" allowClear style={{ width: 140 }} />
            </Form.Item>
            <Form.Item name="phone" label="手机号">
              <Input placeholder="按手机号查询" allowClear style={{ width: 150 }} />
            </Form.Item>
            <Form.Item name="roomNumber" label="房间号">
              <Input placeholder="按房间查询" allowClear style={{ width: 130 }} />
            </Form.Item>
            <Form.Item name="status" label="状态">
              <Select
                placeholder="全部"
                allowClear
                style={{ width: 120 }}
                options={[
                  { value: "CHECKED_IN", label: "在住" },
                  { value: "CHECKED_OUT", label: "已退房" },
                ]}
              />
            </Form.Item>
            <Form.Item name="dateRange" label="入住日期">
              <RangePicker style={{ width: 240 }} />
            </Form.Item>
            <Space>
              <Button
                type="primary"
                icon={<Search size={14} />}
                onClick={handleSearch}
              >
                查询
              </Button>
              <Button icon={<RotateCcw size={14} />} onClick={handleReset}>
                重置
              </Button>
            </Space>
          </Space>
        </Form>
      </Card>

      <Card style={{ borderRadius: 12 }}>
        <Table
          rowKey="id"
          columns={columns}
          dataSource={data?.items || []}
          loading={loading}
          scroll={{ x: 1100 }}
          pagination={{
            current: data?.page || 1,
            pageSize: data?.pageSize || 10,
            total: data?.total || 0,
            showSizeChanger: true,
            showTotal: (t) => `共 ${t} 条`,
            onChange: (p, ps) => {
              setPage(p);
              setPageSize(ps);
              load(p, ps);
            },
          }}
        />
      </Card>

      <ImportModal
        open={importOpen}
        type="residents"
        onClose={() => setImportOpen(false)}
        onSuccess={() => load(1)}
      />
    </div>
  );
}
