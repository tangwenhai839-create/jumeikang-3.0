import { useState } from "react";
import { Modal, Upload, Button, Alert, Space, App } from "antd";
import { Inbox, Download, FileSpreadsheet, AlertCircle } from "lucide-react";
import type { UploadFile } from "antd";
import { importApi, type ImportResult } from "@/api";

interface Props {
  open: boolean;
  type: "rooms" | "residents";
  onClose: () => void;
  onSuccess: () => void;
}

const TYPE_META = {
  rooms: {
    title: "批量导入房间",
    desc: "通过 Excel 表格批量创建房间。",
    columns: ["房间号", "几人间", "是否空调房", "备注"],
    templateName: "rooms_template.xlsx",
  },
  residents: {
    title: "批量导入学员（办理入住）",
    desc: "通过 Excel 表格批量导入学员并自动完成入住分配床位。",
    columns: ["姓名", "手机号", "是否学生", "房间号", "床位号", "备注"],
    templateName: "residents_template.xlsx",
  },
} as const;

export default function ImportModal({ open, type, onClose, onSuccess }: Props) {
  const meta = TYPE_META[type];
  const { message } = App.useApp();
  const [fileList, setFileList] = useState<UploadFile[]>([]);
  const [uploading, setUploading] = useState(false);
  const [result, setResult] = useState<ImportResult | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | undefined>(undefined);

  const reset = () => {
    setFileList([]);
    setResult(null);
    setErrorMsg(undefined);
  };

  const handleClose = () => {
    reset();
    onClose();
  };

  const handleDownload = async () => {
    try {
      const blob =
        type === "rooms"
          ? await importApi.downloadRoomTemplate()
          : await importApi.downloadResidentTemplate();
      const url = window.URL.createObjectURL(blob as any);
      const a = document.createElement("a");
      a.href = url;
      a.download = meta.templateName;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      window.URL.revokeObjectURL(url);
      message.success("模板下载成功");
    } catch (e: any) {
      message.error("模板下载失败：" + (e?.message || "未知错误"));
    }
  };

  const handleImport = async () => {
    if (fileList.length === 0) {
      message.warning("请先选择文件");
      return;
    }
    const f = fileList[0];
    const raw = (f.originFileObj as File) || (f as any);
    if (!raw) {
      message.error("文件对象无效");
      return;
    }
    setUploading(true);
    setErrorMsg(undefined);
    try {
      const r =
        type === "rooms"
          ? await importApi.importRooms(raw)
          : await importApi.importResidents(raw);
      setResult(r);
      if (r.successCount > 0) {
        message.success(`导入完成：成功 ${r.successCount} 条${r.failedCount > 0 ? `，失败 ${r.failedCount} 条` : ""}`);
        onSuccess();
      } else {
        message.warning("全部数据导入失败，请查看详情");
      }
    } catch (e: any) {
      const msg = e?.response?.data?.message || e?.message || "导入失败";
      setErrorMsg(msg);
    } finally {
      setUploading(false);
    }
  };

  return (
    <Modal
      title={
        <span>
          <FileSpreadsheet size={16} style={{ verticalAlign: -2, marginRight: 6 }} />
          {meta.title}
        </span>
      }
      open={open}
      onCancel={handleClose}
      width={640}
      footer={
        result ? (
          [<Button key="ok" type="primary" onClick={handleClose}>完成</Button>]
        ) : (
          [
            <Button key="cancel" onClick={handleClose} disabled={uploading}>
              取消
            </Button>,
            <Button
              key="ok"
              type="primary"
              loading={uploading}
              disabled={fileList.length === 0}
              onClick={handleImport}
            >
              开始导入
            </Button>,
          ]
        )
      }
    >
      <p style={{ color: "#6b7280", marginTop: 0 }}>{meta.desc}</p>

      {/* 模板下载区 */}
      <Alert
        type="info"
        showIcon
        icon={<AlertCircle size={16} />}
        style={{ marginBottom: 16 }}
        message={
          <Space>
            <span>表格模板：</span>
            <Button
              type="link"
              size="small"
              icon={<Download size={14} />}
              onClick={handleDownload}
              style={{ padding: 0 }}
            >
              下载 {meta.templateName}
            </Button>
          </Space>
        }
        description={
          <div style={{ marginTop: 6 }}>
            <div style={{ marginBottom: 4 }}>模板列：</div>
            <Space size={4} wrap>
              {meta.columns.map((c) => (
                <span
                  key={c}
                  style={{
                    background: "#fff",
                    border: "1px solid #d1d5db",
                    padding: "2px 8px",
                    borderRadius: 4,
                    fontSize: 12,
                    fontFamily: "monospace",
                  }}
                >
                  {c}
                </span>
              ))}
            </Space>
          </div>
        }
      />

      {/* 上传区 */}
      {!result && (
        <Upload.Dragger
          multiple={false}
          maxCount={1}
          accept=".xlsx,.xls"
          fileList={fileList}
          beforeUpload={(file) => {
            const isExcel = /\.(xlsx|xls)$/i.test(file.name);
            if (!isExcel) {
              message.error("仅支持 .xlsx / .xls 格式");
              return Upload.LIST_IGNORE;
            }
            const isLt10M = file.size / 1024 / 1024 < 10;
            if (!isLt10M) {
              message.error("文件大小不能超过 10MB");
              return Upload.LIST_IGNORE;
            }
            setFileList([
              {
                uid: String(Date.now()),
                name: file.name,
                status: "done",
                originFileObj: file,
              } as UploadFile,
            ]);
            return false; // 阻止默认上传
          }}
          onRemove={() => {
            setFileList([]);
          }}
          style={{ marginBottom: 12 }}
        >
          <p style={{ marginBottom: 4 }}>
            <Inbox size={32} color="#1e3a5f" />
          </p>
          <p style={{ fontSize: 14, fontWeight: 600, marginBottom: 4 }}>
            点击或拖拽 Excel 文件到此区域
          </p>
          <p style={{ fontSize: 12, color: "#6b7280" }}>
            支持 .xlsx / .xls 格式，单文件不超过 10MB
          </p>
        </Upload.Dragger>
      )}

      {/* 错误提示 */}
      {errorMsg && (
        <Alert
          type="error"
          showIcon
          message="导入失败"
          description={errorMsg}
          style={{ marginBottom: 12 }}
        />
      )}

      {/* 导入结果 */}
      {result && (
        <div>
          <div
            style={{
              display: "flex",
              gap: 12,
              marginBottom: 12,
              flexWrap: "wrap",
            }}
          >
            <div
              style={{
                flex: 1,
                minWidth: 120,
                padding: 12,
                borderRadius: 8,
                background: "#f0fdf4",
                border: "1px solid #bbf7d0",
              }}
            >
              <div style={{ fontSize: 12, color: "#059669" }}>导入成功</div>
              <div style={{ fontSize: 24, fontWeight: 700, color: "#10b981" }}>
                {result.successCount}
              </div>
            </div>
            <div
              style={{
                flex: 1,
                minWidth: 120,
                padding: 12,
                borderRadius: 8,
                background: result.failedCount > 0 ? "#fef2f2" : "#f0fdf4",
                border: `1px solid ${result.failedCount > 0 ? "#fecaca" : "#bbf7d0"}`,
              }}
            >
              <div
                style={{
                  fontSize: 12,
                  color: result.failedCount > 0 ? "#dc2626" : "#059669",
                }}
              >
                导入失败
              </div>
              <div
                style={{
                  fontSize: 24,
                  fontWeight: 700,
                  color: result.failedCount > 0 ? "#ef4444" : "#10b981",
                }}
              >
                {result.failedCount}
              </div>
            </div>
          </div>

          {result.success.length > 0 && (
            <div style={{ marginBottom: 12 }}>
              <div style={{ fontWeight: 600, color: "#059669", marginBottom: 6 }}>
                ✓ 成功明细
              </div>
              <div
                style={{
                  maxHeight: 160,
                  overflowY: "auto",
                  border: "1px solid #e5e7eb",
                  borderRadius: 6,
                  padding: 8,
                  fontSize: 12,
                }}
              >
                {result.success.slice(0, 50).map((s) => (
                  <div key={`s-${s.row}`} style={{ padding: "2px 0" }}>
                    第 {s.row} 行：
                    {s.roomNumber && <span>{s.roomNumber}</span>}
                    {s.name && <span> / {s.name}</span>}
                    {s.bedNumber && <span> / {s.bedNumber}号床</span>}
                  </div>
                ))}
                {result.success.length > 50 && (
                  <div style={{ color: "#6b7280", marginTop: 4 }}>
                    ...还有 {result.success.length - 50} 条
                  </div>
                )}
              </div>
            </div>
          )}

          {result.failed.length > 0 && (
            <div>
              <div style={{ fontWeight: 600, color: "#dc2626", marginBottom: 6 }}>
                ✗ 失败明细
              </div>
              <div
                style={{
                  maxHeight: 160,
                  overflowY: "auto",
                  border: "1px solid #fecaca",
                  borderRadius: 6,
                  padding: 8,
                  fontSize: 12,
                  background: "#fef2f2",
                }}
              >
                {result.failed.map((f) => (
                  <div key={`f-${f.row}`} style={{ padding: "3px 0" }}>
                    第 {f.row} 行：
                    <span style={{ color: "#dc2626" }}>{f.reason}</span>
                    {f.data && (
                      <span style={{ color: "#6b7280", marginLeft: 4 }}>
                        (数据: {JSON.stringify(f.data)})
                      </span>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </Modal>
  );
}
