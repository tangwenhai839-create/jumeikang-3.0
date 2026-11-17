import { BrowserRouter as Router, Routes, Route } from "react-router-dom";
import { ConfigProvider, App as AntdApp } from "antd";
import zhCN from "antd/locale/zh_CN";
import dayjs from "dayjs";
import "dayjs/locale/zh-cn";
import MainLayout from "@/components/MainLayout";
import Overview from "@/pages/Overview";
import Rooms from "@/pages/Rooms";
import RoomDetail from "@/pages/RoomDetail";
import Records from "@/pages/Records";

dayjs.locale("zh-cn");

const routerBase = import.meta.env.BASE_URL === "/"
  ? undefined
  : import.meta.env.BASE_URL.replace(/\/$/, "");

export default function App() {
  return (
    <ConfigProvider
      locale={zhCN}
      theme={{
        token: {
          colorPrimary: "#1e3a5f",
          borderRadius: 8,
          fontFamily:
            '-apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Microsoft YaHei", "Noto Sans SC", sans-serif',
        },
      }}
    >
      <AntdApp>
        <Router basename={routerBase}>
          <Routes>
            <Route element={<MainLayout />}>
              <Route path="/" element={<Overview />} />
              <Route path="/rooms" element={<Rooms />} />
              <Route path="/rooms/:id" element={<RoomDetail />} />
              <Route path="/records" element={<Records />} />
            </Route>
          </Routes>
        </Router>
      </AntdApp>
    </ConfigProvider>
  );
}
