import React, { useState, useEffect, useCallback } from 'react';
import {
  Card,
  Table,
  Button,
  Space,
  message,
  Typography,
  Tag,
  Input,
  Row,
  Col,
  Statistic,
  Avatar,
  Popconfirm,
  Select,
  Switch,
} from 'antd';
import {
  UserOutlined,
  SearchOutlined,
  DeleteOutlined,
  CrownOutlined,
  TeamOutlined,
} from '@ant-design/icons';
import type { ColumnsType, TablePaginationConfig } from 'antd/es/table';
import { usersAPI } from '../services/api';
import type { User, UserStats } from '../types/api';

const { Title, Text } = Typography;

const UserManagement: React.FC = () => {
  const [loading, setLoading] = useState(true);
  const [users, setUsers] = useState<User[]>([]);
  const [stats, setStats] = useState<UserStats | null>(null);
  const [pagination, setPagination] = useState({
    current: 1,
    pageSize: 20,
    total: 0,
  });
  const [searchText, setSearchText] = useState('');
  const [adminFilter, setAdminFilter] = useState<boolean | undefined>(undefined);

  const loadUsers = useCallback(async (page: number, pageSize: number, search?: string, isAdmin?: boolean) => {
    setLoading(true);
    try {
      const data = await usersAPI.getUsers(page, pageSize, search, isAdmin);
      setUsers(data.items);
      setPagination({
        current: data.page,
        pageSize: data.page_size,
        total: data.total,
      });
    } catch (error: unknown) {
      const err = error as { response?: { data?: { detail?: string } } };
      message.error(err.response?.data?.detail || 'Failed to load users');
    } finally {
      setLoading(false);
    }
  }, []);

  const loadStats = useCallback(async () => {
    try {
      const data = await usersAPI.getUserStats();
      setStats(data);
    } catch (error: unknown) {
      console.error('Failed to load user stats:', error);
    }
  }, []);

  useEffect(() => {
    loadUsers(1, 20);
    loadStats();
  }, [loadUsers, loadStats]);

  const handleTableChange = (paginationConfig: TablePaginationConfig) => {
    loadUsers(
      paginationConfig.current || 1,
      paginationConfig.pageSize || 20,
      searchText || undefined,
      adminFilter
    );
  };

  const handleSearch = () => {
    loadUsers(1, pagination.pageSize, searchText || undefined, adminFilter);
  };

  const handleAdminFilterChange = (value: string) => {
    const isAdmin = value === 'admin' ? true : value === 'user' ? false : undefined;
    setAdminFilter(isAdmin);
    loadUsers(1, pagination.pageSize, searchText || undefined, isAdmin);
  };

  const handleToggleAdmin = async (user: User) => {
    try {
      await usersAPI.updateAdminStatus(user.id, { is_admin: !user.is_admin });
      message.success(`User ${user.username} admin status updated`);
      loadUsers(pagination.current, pagination.pageSize, searchText || undefined, adminFilter);
      loadStats();
    } catch (error: unknown) {
      const err = error as { response?: { data?: { detail?: string } } };
      message.error(err.response?.data?.detail || 'Failed to update admin status');
    }
  };

  const handleDelete = async (user: User) => {
    try {
      await usersAPI.deleteUser(user.id);
      message.success(`User ${user.username} deleted`);
      loadUsers(pagination.current, pagination.pageSize, searchText || undefined, adminFilter);
      loadStats();
    } catch (error: unknown) {
      const err = error as { response?: { data?: { detail?: string } } };
      message.error(err.response?.data?.detail || 'Failed to delete user');
    }
  };

  const columns: ColumnsType<User> = [
    {
      title: 'User',
      key: 'user',
      render: (_, record) => (
        <Space>
          <Avatar
            src={record.profile_picture}
            icon={<UserOutlined />}
            size="small"
          />
          <Space direction="vertical" size={0}>
            <Text strong>{record.username}</Text>
            {record.full_name && (
              <Text type="secondary" style={{ fontSize: 12 }}>
                {record.full_name}
              </Text>
            )}
          </Space>
        </Space>
      ),
    },
    {
      title: 'Email',
      dataIndex: 'email',
      key: 'email',
      render: (email: string | null) => email || '-',
    },
    {
      title: 'Role',
      key: 'role',
      width: 120,
      render: (_, record) => (
        record.is_admin ? (
          <Tag color="gold" icon={<CrownOutlined />}>Admin</Tag>
        ) : (
          <Tag color="default">User</Tag>
        )
      ),
    },
    {
      title: 'Admin',
      key: 'admin_toggle',
      width: 100,
      render: (_, record) => (
        <Popconfirm
          title={`${record.is_admin ? 'Remove' : 'Grant'} admin privileges?`}
          description={`Are you sure you want to ${record.is_admin ? 'remove admin privileges from' : 'grant admin privileges to'} ${record.username}?`}
          onConfirm={() => handleToggleAdmin(record)}
          okText="Yes"
          cancelText="No"
        >
          <Switch
            checked={record.is_admin}
            checkedChildren="Yes"
            unCheckedChildren="No"
            size="small"
          />
        </Popconfirm>
      ),
    },
    {
      title: 'Created',
      dataIndex: 'created_at',
      key: 'created_at',
      width: 180,
      render: (date: string | null) => {
        if (!date) return '-';
        return new Date(date).toLocaleString();
      },
    },
    {
      title: 'Actions',
      key: 'actions',
      width: 100,
      render: (_, record) => (
        <Popconfirm
          title="Delete user?"
          description={`Are you sure you want to delete ${record.username}? This action cannot be undone.`}
          onConfirm={() => handleDelete(record)}
          okText="Yes"
          cancelText="No"
          okButtonProps={{ danger: true }}
        >
          <Button
            type="link"
            danger
            icon={<DeleteOutlined />}
            size="small"
          >
            Delete
          </Button>
        </Popconfirm>
      ),
    },
  ];

  return (
    <div>
      <Title level={4} style={{ marginBottom: 24 }}>User Management</Title>

      {/* Stats Cards */}
      {stats && (
        <Row gutter={[16, 16]} style={{ marginBottom: 24 }}>
          <Col xs={24} sm={8}>
            <Card>
              <Statistic
                title="Total Users"
                value={stats.total_users}
                prefix={<TeamOutlined style={{ color: '#1890ff' }} />}
              />
            </Card>
          </Col>
          <Col xs={24} sm={8}>
            <Card>
              <Statistic
                title="Admin Users"
                value={stats.admin_users}
                prefix={<CrownOutlined style={{ color: '#faad14' }} />}
              />
            </Card>
          </Col>
          <Col xs={24} sm={8}>
            <Card>
              <Statistic
                title="Regular Users"
                value={stats.regular_users}
                prefix={<UserOutlined style={{ color: '#52c41a' }} />}
              />
            </Card>
          </Col>
        </Row>
      )}

      {/* Filters */}
      <Card style={{ marginBottom: 16 }}>
        <Row gutter={[16, 16]} align="middle">
          <Col xs={24} sm={12} md={8}>
            <Input
              placeholder="Search by username, email, or name"
              prefix={<SearchOutlined />}
              value={searchText}
              onChange={(e) => setSearchText(e.target.value)}
              onPressEnter={handleSearch}
              allowClear
            />
          </Col>
          <Col xs={24} sm={8} md={6}>
            <Select
              placeholder="Filter by role"
              style={{ width: '100%' }}
              allowClear
              onChange={handleAdminFilterChange}
              options={[
                { value: 'all', label: 'All Users' },
                { value: 'admin', label: 'Admins Only' },
                { value: 'user', label: 'Regular Users' },
              ]}
            />
          </Col>
          <Col>
            <Button type="primary" onClick={handleSearch} icon={<SearchOutlined />}>
              Search
            </Button>
          </Col>
        </Row>
      </Card>

      {/* Users Table */}
      <Card>
        <Table
          columns={columns}
          dataSource={users}
          rowKey="id"
          loading={loading}
          pagination={{
            ...pagination,
            showSizeChanger: true,
            showQuickJumper: true,
            showTotal: (total) => `Total ${total} users`,
          }}
          onChange={handleTableChange}
        />
      </Card>
    </div>
  );
};

export default UserManagement;
