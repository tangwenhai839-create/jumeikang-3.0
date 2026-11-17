import { useEffect } from "react";
import { Modal, Form, Input, InputNumber, Radio, Select, Alert } from "antd";
import { roomsApi } from "@/api";
import { ROOM_TYPE_LABEL, CAPACITY_MAP, type RoomType } from "@/types";

interface Props {
  open: boolean;
  onClose: () => void;
  onSuccess: () => void;
}

export default function BatchCreateModal({ open, onClose, onSuccess }: Props) {
  const [form] = Form.useForm();

  useEffect(() => {
    if (open) {
      form.resetFields();
      form.setFieldsValue({
        roomType: "QUAD",
        hasAirConditioner: true,
        startNumber: "101",
        count: 5,
      });
    }
  }, [open, form]);

  const handleOk = async () => {
    const values = await form.validateFields();
    await roomsApi.batchCreate(values);
    onSuccess();
    onClose();
  };

  const roomType = Form.useWatch("roomType", form);
  const capacity = roomType ? CAPACITY_MAP[roomType as RoomType] : 0;
  const startNumber = Form.useWatch("startNumber", form);
  const count = Form.useWatch("count", form);

  // 预览生成的房间号
  const preview = (() => {
    if (!startNumber || !count) return [];
    const match = String(startNumber).match(/^([A-Za-z]*?)(\d+)$/);
    if (!match) return [];
    const prefix = match[1];
    const startNum = parseInt(match[2], 10);
    const digits = match[2].length;
    return Array.from({ length: Math.min(count, 5) }, (_, i) => {
      const num = String(startNum + i).padStart(digits, "0");
      return `${prefix}${num}`;
    });
  })();

  return (
    <Modal
      title="批量创建房间"
      open={open}
      onOk={handleOk}
      onCancel={onClose}
      okText="批量创建"
      cancelText="取消"
      destroyOnClose
      width={500}
    >
      <Form form={form} layout="vertical" style={{ marginTop: 16 }}>
        <Form.Item
          name="roomType"
          label="房间类型"
          rules={[{ required: true, message: "请选择房间类型" }]}
          extra={
            capacity > 0 ? (
              <span style={{ color: "#059669", fontSize: 12 }}>
                每间最大入住人数：{capacity} 人
              </span>
            ) : null
          }
        >
          <Select
            options={(Object.keys(ROOM_TYPE_LABEL) as RoomType[]).map((t) => ({
              value: t,
              label: ROOM_TYPE_LABEL[t],
            }))}
          />
        </Form.Item>

        <Form.Item
          name="hasAirConditioner"
          label="空调类型"
          rules={[{ required: true, message: "请选择空调类型" }]}
        >
          <Radio.Group>
            <Radio value={true}>空调房</Radio>
            <Radio value={false}>非空调房</Radio>
          </Radio.Group>
        </Form.Item>

        <Form.Item
          name="startNumber"
          label="起始房间号"
          rules={[
            { required: true, message: "请输入起始房间号" },
            {
              pattern: /^[A-Za-z]*\d+$/,
              message: "格式为字母前缀+数字，例如 101 或 A201",
            },
          ]}
          extra="格式：字母前缀+数字，例如 101、A201。将自动递增生成。"
        >
          <Input placeholder="例如 101" />
        </Form.Item>

        <Form.Item
          name="count"
          label="创建数量"
          rules={[
            { required: true, message: "请输入创建数量" },
            { type: "number", min: 1, max: 100, message: "数量 1-100" },
          ]}
        >
          <InputNumber min={1} max={100} style={{ width: "100%" }} />
        </Form.Item>

        <Form.Item name="remark" label="房间备注（可选）">
          <Input.TextArea rows={2} placeholder="批量应用的备注" />
        </Form.Item>

        {preview.length > 0 && (
          <Alert
            type="info"
            showIcon
            message={`将创建房间号（前 5 个预览）`}
            description={preview.join("、") + (count > 5 ? " ..." : "")}
            style={{ marginTop: 8 }}
          />
        )}
      </Form>
    </Modal>
  );
}
