import { Outlet, useNavigate, useLocation } from "react-router-dom";
import { Layout, Menu, theme } from "antd";
import { Home, DoorClosed, FileText } from "lucide-react";

const { Header, Content } = Layout;

const navItems = [
  { key: "/", label: "房间总览", icon: <Home size={16} /> },
  { key: "/rooms", label: "房间管理", icon: <DoorClosed size={16} /> },
  { key: "/records", label: "入住记录", icon: <FileText size={16} /> },
];

export default function MainLayout() {
  const navigate = useNavigate();
  const location = useLocation();
  const { token } = theme.useToken();
  const integrated = import.meta.env.VITE_ADMIN_INTEGRATED === "true";

  // 当前选中项：以最长前缀匹配
  const selectedKey =
    navItems
      .map((i) => i.key)
      .filter((k) => location.pathname.startsWith(k))
      .sort((a, b) => b.length - a.length)[0] || "/";

  return (
    <Layout style={{ minHeight: "100vh" }}>
      <Header
        className="lodging-header"
        style={{
          display: "flex",
          alignItems: "center",
          background: "linear-gradient(90deg, #1e3a5f 0%, #2c5282 100%)",
          padding: "0 24px",
          boxShadow: "0 2px 8px rgba(0,0,0,0.15)",
          position: "sticky",
          top: 0,
          zIndex: 10,
        }}
      >
        <div
          className="lodging-brand"
          style={{
            color: "#fff",
            fontWeight: 700,
            fontSize: 18,
            marginRight: 40,
            letterSpacing: 1,
            whiteSpace: "nowrap",
          }}
        >
          <span aria-hidden="true">🏨</span> 聚美康住宿管理
        </div>
        {integrated && (
          <a className="lodging-back-link" href="/">
            返回管理中心
          </a>
        )}
        <Menu
          className="lodging-main-menu"
          theme="dark"
          mode="horizontal"
          selectedKeys={[selectedKey]}
          items={navItems}
          onClick={({ key }) => navigate(key)}
          style={{
            background: "transparent",
            borderBottom: "none",
            flex: 1,
            minWidth: 0,
          }}
        />
      </Header>
      <Content
        className="lodging-content"
        style={{
          background: token.colorBgLayout,
          padding: "24px",
        }}
      >
        <div style={{ maxWidth: 1400, margin: "0 auto" }}>
          <Outlet />
        </div>
      </Content>
    </Layout>
  );
}
