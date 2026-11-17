import { useEffect } from "react";
import { Modal, Form, Input, Radio, Select } from "antd";
import { Snowflake, Wind } from "lucide-react";
import { roomsApi } from "@/api";
import {
  ROOM_TYPE_LABEL,
  CAPACITY_MAP,
  type Room,
  type RoomType,
} from "@/types";

interface Props {
  open: boolean;
  editingRoom: Room | null;
  onClose: () => void;
  onSuccess: () => void;
}

export default function RoomFormModal({
  open,
  editingRoom,
  onClose,
  onSuccess,
}: Props) {
  const [form] = Form.useForm();
  const isEdit = !!editingRoom;

  useEffect(() => {
    if (open) {
      if (editingRoom) {
        form.setFieldsValue({
          roomNumber: editingRoom.roomNumber,
          roomType: editingRoom.roomType,
          hasAirConditioner: editingRoom.hasAirConditioner,
          remark: editingRoom.remark || "",
        });
      } else {
        form.resetFields();
        form.setFieldsValue({
          roomType: "QUAD",
          hasAirConditioner: true,
        });
      }
    }
  }, [open, editingRoom, form]);

  const handleOk = async () => {
    const values = await form.validateFields();
    if (isEdit && editingRoom) {
      await roomsApi.update(editingRoom.id, values);
    } else {
      await roomsApi.create(values as { roomNumber: string; roomType: RoomType; hasAirConditioner: boolean });
    }
    onSuccess();
    onClose();
  };

  const roomType = Form.useWatch("roomType", form);
  const capacity = roomType ? CAPACITY_MAP[roomType as RoomType] : 0;

  return (
    <Modal
      title={isEdit ? "编辑房间" : "添加房间"}
      open={open}
      onOk={handleOk}
      onCancel={onClose}
      okText="保存"
      cancelText="取消"
      destroyOnClose
      width={480}
    >
      <Form form={form} layout="vertical" style={{ marginTop: 16 }}>
        <Form.Item
          name="roomNumber"
          label="房间号"
          rules={[
            { required: true, message: "请输入房间号" },
            { max: 20, message: "房间号不超过 20 字符" },
          ]}
        >
          <Input placeholder="例如 101、102、A201" />
        </Form.Item>

        <Form.Item
          name="roomType"
          label="房间类型"
          rules={[{ required: true, message: "请选择房间类型" }]}
          extra={
            capacity > 0 ? (
              <span style={{ color: "#059669", fontSize: 12 }}>
                最大入住人数：{capacity} 人
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
            <Radio value={true}>
              <Snowflake size={13} style={{ verticalAlign: -2, color: "#0891b2" }} /> 空调房
            </Radio>
            <Radio value={false}>
              <Wind size={13} style={{ verticalAlign: -2, color: "#6b7280" }} /> 非空调房
            </Radio>
          </Radio.Group>
        </Form.Item>

        <Form.Item name="remark" label="房间备注">
          <Input.TextArea rows={2} placeholder="可选，例如：靠走廊、有阳台等" />
        </Form.Item>
      </Form>
    </Modal>
  );
}
