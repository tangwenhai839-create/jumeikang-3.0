import { useEffect } from "react";
import { Modal, Form, Input, Radio, Tag } from "antd";
import { residentsApi } from "@/api";

interface Props {
  open: boolean;
  roomId: number | null;
  bedNumber: number | null;
  onClose: () => void;
  onSuccess: () => void;
}

export default function CheckInModal({
  open,
  roomId,
  bedNumber,
  onClose,
  onSuccess,
}: Props) {
  const [form] = Form.useForm();

  useEffect(() => {
    if (open) {
      form.resetFields();
      form.setFieldsValue({ isStudent: false });
    }
  }, [open, form]);

  const handleOk = async () => {
    const values = await form.validateFields();
    if (!roomId) return;
    await residentsApi.checkIn(roomId, values);
    onSuccess();
    onClose();
  };

  return (
    <Modal
      title={
        <span>
          办理入住
          {bedNumber && (
            <Tag color="blue" style={{ marginLeft: 8 }}>
              {bedNumber}号床
            </Tag>
          )}
        </span>
      }
      open={open}
      onOk={handleOk}
      onCancel={onClose}
      okText="确认入住"
      cancelText="取消"
      destroyOnClose
      width={460}
    >
      <Form form={form} layout="vertical" style={{ marginTop: 16 }}>
        <Form.Item
          name="name"
          label="姓名"
          rules={[
            { required: true, message: "请输入姓名" },
            { max: 50, message: "姓名不超过 50 字符" },
          ]}
        >
          <Input placeholder="例如 张三" />
        </Form.Item>

        <Form.Item
          name="phone"
          label="手机号"
          rules={[
            { required: true, message: "请输入手机号" },
            { max: 20, message: "手机号不超过 20 字符" },
          ]}
        >
          <Input placeholder="例如 138xxxxxxxx" />
        </Form.Item>

        <Form.Item
          name="isStudent"
          label="是否学生"
          rules={[{ required: true, message: "请选择" }]}
        >
          <Radio.Group>
            <Radio value={true}>是</Radio>
            <Radio value={false}>否</Radio>
          </Radio.Group>
        </Form.Item>

        <Form.Item name="remark" label="备注（可选）">
          <Input.TextArea rows={2} placeholder="例如：计算机系学生、短期住宿等" />
        </Form.Item>
      </Form>
    </Modal>
  );
}
