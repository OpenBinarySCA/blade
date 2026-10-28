import React, { useState } from 'react';
import { Routes, Route, Navigate, useLocation, useNavigate } from 'react-router-dom';
import { Layout, message } from 'antd';
import ProLayout from '@ant-design/pro-layout';
import {
  UserOutlined,
  DashboardOutlined,
  DatabaseOutlined,
  LogoutOutlined,
  SettingOutlined,
  TeamOutlined,
  HistoryOutlined,
  MonitorOutlined,
  AppstoreOutlined,
} from '@ant-design/icons';

import LoginPage from './pages/LoginPage';
import Dashboard from './pages/Dashboard';
import LibraryManagement from './pages/LibraryManagement';
import LibraryDetail from './pages/LibraryDetail';
import SystemSettings from './pages/SystemSettings';
import UserManagement from './pages/UserManagement';
import AnalysisHistory from './pages/AnalysisHistory';
import SystemMonitor from './pages/SystemMonitor';
import SampleManagement from './pages/SampleManagement';

const { Content } = Layout;

interface MenuItem {
  path: string;
  name: string;
  icon: React.ReactNode;
  component: React.ReactNode;
  hideInMenu?: boolean;
}

interface TokenPayload {
  sub: string;
  session_id: string;
  is_admin: boolean;
  exp: number;
}

// Parse JWT token to get payload
function parseJwt(token: string): TokenPayload | null {
  try {
    const parts = token.split('.');
    if (parts.length !== 3) return null;
    const payload = JSON.parse(atob(parts[1]));
    return payload;
  } catch {
    return null;
  }
}

// Check if token is valid and user is admin
function checkAdminToken(token: string | null): { valid: boolean; isAdmin: boolean; username: string } {
  if (!token) return { valid: false, isAdmin: false, username: '' };

  const payload = parseJwt(token);
  if (!payload) return { valid: false, isAdmin: false, username: '' };

  // Check expiration
  const currentTime = Math.floor(Date.now() / 1000);
  if (payload.exp && payload.exp < currentTime) {
    return { valid: false, isAdmin: false, username: '' };
  }

  return {
    valid: true,
    isAdmin: payload.is_admin === true,
    username: payload.sub || '',
  };
}

const menuItems: MenuItem[] = [
  {
    path: '/dashboard',
    name: 'Dashboard',
    icon: <DashboardOutlined />,
    component: <Dashboard />,
  },
  {
    path: '/libraries',
    name: 'Library Management',
    icon: <DatabaseOutlined />,
    component: <LibraryManagement />,
  },
  {
    path: '/libraries/:id',
    name: 'Library Detail',
    icon: <DatabaseOutlined />,
    component: <LibraryDetail />,
    hideInMenu: true,
  },
  {
    path: '/analysis-history',
    name: 'Analysis History',
    icon: <HistoryOutlined />,
    component: <AnalysisHistory />,
  },
  {
    path: '/samples',
    name: 'Sample Management',
    icon: <AppstoreOutlined />,
    component: <SampleManagement />,
  },
  {
    path: '/users',
    name: 'User Management',
    icon: <TeamOutlined />,
    component: <UserManagement />,
  },
  {
    path: '/system-monitor',
    name: 'System Monitor',
    icon: <MonitorOutlined />,
    component: <SystemMonitor />,
  },
  {
    path: '/settings',
    name: 'System Settings',
    icon: <SettingOutlined />,
    component: <SystemSettings />,
  },
];

function App() {
  const location = useLocation();
  const navigate = useNavigate();

  const [authState, setAuthState] = useState<{
    isAuthenticated: boolean;
    isAdmin: boolean;
    username: string;
  }>(() => {
    const token = localStorage.getItem('access_token');
    const { valid, isAdmin, username } = checkAdminToken(token);
    return {
      isAuthenticated: valid && isAdmin,
      isAdmin,
      username,
    };
  });

  const handleLogin = (token: string) => {
    const { valid, isAdmin, username } = checkAdminToken(token);

    if (!valid) {
      message.error('Invalid token');
      return;
    }

    if (!isAdmin) {
      message.error('Access denied: Admin privileges required');
      return;
    }

    localStorage.setItem('access_token', token);
    setAuthState({
      isAuthenticated: true,
      isAdmin: true,
      username,
    });
    message.success(`Welcome, ${username}!`);
  };

  const handleLogout = () => {
    localStorage.removeItem('access_token');
    setAuthState({
      isAuthenticated: false,
      isAdmin: false,
      username: '',
    });
    message.info('Logged out successfully');
  };

  // Show login page if not authenticated
  if (!authState.isAuthenticated) {
    return <LoginPage onLogin={handleLogin} />;
  }

  return (
    <ProLayout
      title="BLADE Admin"
      logo={false}
      layout="mix"
      navTheme="light"
      route={{
        path: '/',
        children: menuItems
          .filter(item => !item.hideInMenu)
          .map(item => ({
            path: item.path,
            name: item.name,
            icon: item.icon,
          })),
      }}
      location={{
        pathname: location.pathname,
      }}
      menuItemRender={(item, dom) => (
        <a
          onClick={(e) => {
            e.preventDefault();
            if (item.path) {
              navigate(item.path);
            }
          }}
        >
          {dom}
        </a>
      )}
      actionsRender={() => [
        <div
          key="user"
          style={{ padding: '0 16px', color: '#666' }}
        >
          <UserOutlined /> {authState.username}
        </div>,
        <div
          key="logout"
          style={{ cursor: 'pointer', padding: '0 16px' }}
          onClick={handleLogout}
        >
          <LogoutOutlined /> Logout
        </div>,
      ]}
    >
      <Content style={{ padding: 24 }}>
        <Routes>
          <Route path="/" element={<Navigate to="/dashboard" replace />} />
          {menuItems.map(item => (
            <Route
              key={item.path}
              path={item.path}
              element={item.component}
            />
          ))}
        </Routes>
      </Content>
    </ProLayout>
  );
}

export default App;
