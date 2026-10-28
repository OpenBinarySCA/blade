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
  Select,
  Tooltip,
  Progress,
  Popconfirm,
} from 'antd';
import {
  SearchOutlined,
  FileOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
  ClockCircleOutlined,
  SyncOutlined,
  HistoryOutlined,
  StopOutlined,
  MinusCircleOutlined,
} from '@ant-design/icons';
import type { ColumnsType, TablePaginationConfig } from 'antd/es/table';
import { tasksAPI } from '../services/api';
import type { AnalysisTask, TaskStats } from '../types/api';

const { Title, Text } = Typography;

const statusConfig: Record<string, { color: string; icon: React.ReactNode }> = {
  pending: { color: 'gold', icon: <ClockCircleOutlined /> },
  running: { color: 'processing', icon: <SyncOutlined spin /> },
  file_downloading: { color: 'processing', icon: <SyncOutlined spin /> },
  unpacking: { color: 'processing', icon: <SyncOutlined spin /> },
  unpacking_result_uploading: { color: 'processing', icon: <SyncOutlined spin /> },
  analyzing: { color: 'processing', icon: <SyncOutlined spin /> },
  result_uploading: { color: 'processing', icon: <SyncOutlined spin /> },
  success: { color: 'success', icon: <CheckCircleOutlined /> },
  failed: { color: 'error', icon: <CloseCircleOutlined /> },
  cancelling: { color: 'warning', icon: <SyncOutlined spin /> },
  cancelled: { color: 'default', icon: <MinusCircleOutlined /> },
};

const AnalysisHistory: React.FC = () => {
  const [loading, setLoading] = useState(true);
  const [tasks, setTasks] = useState<AnalysisTask[]>([]);
  const [stats, setStats] = useState<TaskStats | null>(null);
  const [pagination, setPagination] = useState({
    current: 1,
    pageSize: 20,
    total: 0,
  });
  const [searchText, setSearchText] = useState('');
  const [statusFilter, setStatusFilter] = useState<string | undefined>(undefined);

  const loadTasks = useCallback(async (page: number, pageSize: number, search?: string, status?: string) => {
    setLoading(true);
    try {
      const data = await tasksAPI.getTasks(page, pageSize, search, status);
      setTasks(data.items);
      setPagination({
        current: data.page,
        pageSize: data.page_size,
        total: data.total,
      });
    } catch (error: unknown) {
      const err = error as { response?: { data?: { detail?: string } } };
      message.error(err.response?.data?.detail || 'Failed to load tasks');
    } finally {
      setLoading(false);
    }
  }, []);

  const loadStats = useCallback(async () => {
    try {
      const data = await tasksAPI.getTaskStats();
      setStats(data);
    } catch (error: unknown) {
      console.error('Failed to load task stats:', error);
    }
  }, []);

  useEffect(() => {
    loadTasks(1, 20);
    loadStats();
  }, [loadTasks, loadStats]);

  const handleTableChange = (paginationConfig: TablePaginationConfig) => {
    loadTasks(
      paginationConfig.current || 1,
      paginationConfig.pageSize || 20,
      searchText || undefined,
      statusFilter
    );
  };

  const handleSearch = () => {
    loadTasks(1, pagination.pageSize, searchText || undefined, statusFilter);
  };

  const handleStatusFilterChange = (value: string) => {
    const status = value === 'all' ? undefined : value;
    setStatusFilter(status);
    loadTasks(1, pagination.pageSize, searchText || undefined, status);
  };

  const handleCancelTask = async (taskId: string) => {
    try {
      await tasksAPI.cancelTask(taskId);
      message.success('Cancel request sent');
      // Refresh the task list
      loadTasks(pagination.current, pagination.pageSize, searchText || undefined, statusFilter);
      loadStats();
    } catch (error: unknown) {
      const err = error as { response?: { data?: { detail?: string } } };
      message.error(err.response?.data?.detail || 'Failed to cancel task');
    }
  };

  const canCancelTask = (status: string) => {
    const nonCancellable = ['success', 'failed', 'cancelled', 'cancelling'];
    return !nonCancellable.includes(status);
  };

  const getStatusTag = (status: string) => {
    const config = statusConfig[status] || { color: 'default', icon: null };
    return (
      <Tag color={config.color} icon={config.icon}>
        {status.charAt(0).toUpperCase() + status.slice(1)}
      </Tag>
    );
  };

  const formatDuration = (startAt: string | null, endAt: string | null) => {
    if (!startAt) return '-';
    const start = new Date(startAt).getTime();
    const end = endAt ? new Date(endAt).getTime() : Date.now();
    const duration = Math.round((end - start) / 1000);

    if (duration < 60) return `${duration}s`;
    if (duration < 3600) return `${Math.floor(duration / 60)}m ${duration % 60}s`;
    return `${Math.floor(duration / 3600)}h ${Math.floor((duration % 3600) / 60)}m`;
  };

  const columns: ColumnsType<AnalysisTask> = [
    {
      title: 'Task ID',
      dataIndex: 'task_id',
      key: 'task_id',
      width: 120,
      render: (taskId: string) => (
        <Text style={{ fontSize: 12 }} copyable={{ text: taskId }}>
          {taskId.slice(0, 8)}...
        </Text>
      ),
    },
    {
      title: 'File',
      key: 'file',
      width: 200,
      ellipsis: true,
      render: (_, record) => (
        <Space direction="vertical" size={0}>
          <Tooltip title={record.file_name}>
            <Text strong ellipsis style={{ maxWidth: 180 }}>
              <FileOutlined style={{ marginRight: 4 }} />
              {record.file_name}
            </Text>
          </Tooltip>
          <Text type="secondary" style={{ fontSize: 11 }} copyable={{ text: record.input_file_sha256 }}>
            {record.input_file_sha256.slice(0, 8)}...
          </Text>
        </Space>
      ),
    },
    {
      title: 'User',
      key: 'user',
      width: 160,
      render: (_, record) => (
        record.user ? (
          <Text ellipsis style={{ maxWidth: 140 }}>{record.user.username}</Text>
        ) : (
          <Tag color="default">Guest</Tag>
        )
      ),
    },
    {
      title: 'Status',
      dataIndex: 'status',
      key: 'status',
      width: 100,
      render: (status: string) => getStatusTag(status),
    },
    {
      title: 'Progress',
      key: 'progress',
      width: 120,
      render: (_, record) => {
        if (record.status === 'pending') return <Text type="secondary">Waiting</Text>;
        if (record.analysis_total_files === 0) return <Text type="secondary">-</Text>;

        const percent = Math.round((record.analysis_completed_files / record.analysis_total_files) * 100);
        return (
          <Tooltip title={`${record.analysis_completed_files} / ${record.analysis_total_files} files`}>
            <Progress
              percent={percent}
              size="small"
              status={record.status === 'failed' ? 'exception' : record.status === 'success' ? 'success' : 'active'}
            />
          </Tooltip>
        );
      },
    },
    {
      title: 'Duration',
      key: 'duration',
      width: 80,
      render: (_, record) => formatDuration(record.start_at, record.end_at),
    },
    {
      title: 'Engine',
      dataIndex: 'engine_version',
      key: 'engine_version',
      width: 70,
      render: (version: string) => <Tag>{version}</Tag>,
    },
    {
      title: 'Started',
      dataIndex: 'start_at',
      key: 'start_at',
      width: 150,
      render: (date: string | null) => {
        if (!date) return '-';
        return new Date(date).toLocaleString();
      },
    },
    {
      title: 'Ended',
      dataIndex: 'end_at',
      key: 'end_at',
      width: 150,
      render: (date: string | null) => {
        if (!date) return '-';
        return new Date(date).toLocaleString();
      },
    },
    {
      title: 'Action',
      key: 'action',
      width: 100,
      fixed: 'right',
      render: (_, record) => (
        <Space size="small">
          {canCancelTask(record.status) && (
            <Popconfirm
              title="Cancel Task"
              description="Are you sure you want to cancel this task?"
              onConfirm={() => handleCancelTask(record.task_id)}
              okText="Yes"
              cancelText="No"
              okButtonProps={{ danger: true }}
            >
              <Tooltip title="Cancel task">
                <Button
                  type="text"
                  danger
                  size="small"
                  icon={<StopOutlined />}
                />
              </Tooltip>
            </Popconfirm>
          )}
        </Space>
      ),
    },
  ];

  // Calculate success rate
  const successRate = stats && stats.total > 0
    ? Math.round((stats.success / stats.total) * 100)
    : 0;

  return (
    <div>
      <Title level={4} style={{ marginBottom: 24 }}>
        <HistoryOutlined style={{ marginRight: 8 }} />
        Analysis History
      </Title>

      {/* Stats Cards */}
      {stats && (
        <Row gutter={[16, 16]} style={{ marginBottom: 24 }}>
          <Col xs={12} sm={8} lg={4}>
            <Card>
              <Statistic
                title="Total"
                value={stats.total}
                valueStyle={{ color: '#1890ff' }}
              />
            </Card>
          </Col>
          <Col xs={12} sm={8} lg={4}>
            <Card>
              <Statistic
                title="Success"
                value={stats.success}
                valueStyle={{ color: '#52c41a' }}
                prefix={<CheckCircleOutlined />}
              />
            </Card>
          </Col>
          <Col xs={12} sm={8} lg={4}>
            <Card>
              <Statistic
                title="Failed"
                value={stats.failed}
                valueStyle={{ color: '#ff4d4f' }}
                prefix={<CloseCircleOutlined />}
              />
            </Card>
          </Col>
          <Col xs={12} sm={8} lg={4}>
            <Card>
              <Statistic
                title="Running"
                value={stats.running}
                valueStyle={{ color: '#1890ff' }}
                prefix={<SyncOutlined spin={stats.running > 0} />}
              />
            </Card>
          </Col>
          <Col xs={12} sm={8} lg={4}>
            <Card>
              <Statistic
                title="Pending"
                value={stats.pending}
                valueStyle={{ color: '#faad14' }}
                prefix={<ClockCircleOutlined />}
              />
            </Card>
          </Col>
          <Col xs={12} sm={8} lg={4}>
            <Card>
              <Statistic
                title="Cancelled"
                value={stats.cancelled || 0}
                valueStyle={{ color: '#8c8c8c' }}
                prefix={<MinusCircleOutlined />}
              />
            </Card>
          </Col>
          <Col xs={12} sm={8} lg={4}>
            <Card>
              <Statistic
                title="Success Rate"
                value={successRate}
                suffix="%"
                valueStyle={{ color: successRate >= 80 ? '#52c41a' : successRate >= 50 ? '#faad14' : '#ff4d4f' }}
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
              placeholder="Search by file name or task ID"
              prefix={<SearchOutlined />}
              value={searchText}
              onChange={(e) => setSearchText(e.target.value)}
              onPressEnter={handleSearch}
              allowClear
            />
          </Col>
          <Col xs={24} sm={8} md={6}>
            <Select
              placeholder="Filter by status"
              style={{ width: '100%' }}
              allowClear
              onChange={handleStatusFilterChange}
              options={[
                { value: 'all', label: 'All Status' },
                { value: 'pending', label: 'Pending' },
                { value: 'running', label: 'Running' },
                { value: 'success', label: 'Success' },
                { value: 'failed', label: 'Failed' },
                { value: 'cancelled', label: 'Cancelled' },
                { value: 'cancelling', label: 'Cancelling' },
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

      {/* Tasks Table */}
      <Card>
        <Table
          columns={columns}
          dataSource={tasks}
          rowKey="task_id"
          loading={loading}
          pagination={{
            ...pagination,
            showSizeChanger: true,
            showQuickJumper: true,
            showTotal: (total) => `Total ${total} tasks`,
          }}
          onChange={handleTableChange}
          scroll={{ x: 1000 }}
        />
      </Card>
    </div>
  );
};

export default AnalysisHistory;
