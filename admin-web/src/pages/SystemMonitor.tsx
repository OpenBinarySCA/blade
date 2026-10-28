import React, { useState, useEffect, useCallback, useRef } from 'react';
import {
  Card,
  Row,
  Col,
  Progress,
  Typography,
  Statistic,
  Space,
  Tag,
  Table,
  Spin,
  message,
  Switch,
} from 'antd';
import {
  DashboardOutlined,
  HddOutlined,
  CloudServerOutlined,
  SwapOutlined,
  ClockCircleOutlined,
  ReloadOutlined,
} from '@ant-design/icons';
import { systemAPI } from '../services/api';
import type { SystemStatus } from '../types/api';

const { Title, Text } = Typography;

// Format bytes to human readable
const formatBytes = (bytes: number, decimals = 2): string => {
  if (bytes === 0) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(decimals)) + ' ' + sizes[i];
};

// Format uptime
const formatUptime = (seconds: number): string => {
  const days = Math.floor(seconds / 86400);
  const hours = Math.floor((seconds % 86400) / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);

  const parts = [];
  if (days > 0) parts.push(`${days}d`);
  if (hours > 0) parts.push(`${hours}h`);
  if (minutes > 0) parts.push(`${minutes}m`);

  return parts.join(' ') || '< 1m';
};

// Format bytes rate
const formatBytesRate = (bytes: number): string => {
  return formatBytes(bytes) + '/s';
};

const SystemMonitor: React.FC = () => {
  const [loading, setLoading] = useState(true);
  const [status, setStatus] = useState<SystemStatus | null>(null);
  const [autoRefresh, setAutoRefresh] = useState(true);
  const [lastUpdate, setLastUpdate] = useState<Date | null>(null);

  // Store previous IO values for rate calculation
  const prevIORef = useRef<{
    disk_read: number;
    disk_write: number;
    net_sent: number;
    net_recv: number;
    timestamp: number;
  } | null>(null);

  const [ioRates, setIORates] = useState({
    diskReadRate: 0,
    diskWriteRate: 0,
    netSentRate: 0,
    netRecvRate: 0,
  });

  const loadStatus = useCallback(async () => {
    try {
      const data = await systemAPI.getSystemStatus();
      setStatus(data);
      setLastUpdate(new Date());

      // Calculate IO rates
      const now = Date.now();
      if (prevIORef.current && data.disk_io) {
        const timeDiff = (now - prevIORef.current.timestamp) / 1000; // seconds
        if (timeDiff > 0) {
          setIORates({
            diskReadRate: Math.max(0, (data.disk_io.read_bytes - prevIORef.current.disk_read) / timeDiff),
            diskWriteRate: Math.max(0, (data.disk_io.write_bytes - prevIORef.current.disk_write) / timeDiff),
            netSentRate: Math.max(0, (data.network_io.bytes_sent - prevIORef.current.net_sent) / timeDiff),
            netRecvRate: Math.max(0, (data.network_io.bytes_recv - prevIORef.current.net_recv) / timeDiff),
          });
        }
      }

      // Update previous values
      prevIORef.current = {
        disk_read: data.disk_io?.read_bytes || 0,
        disk_write: data.disk_io?.write_bytes || 0,
        net_sent: data.network_io.bytes_sent,
        net_recv: data.network_io.bytes_recv,
        timestamp: now,
      };

      setLoading(false);
    } catch (error: unknown) {
      const err = error as { response?: { data?: { detail?: string } } };
      message.error(err.response?.data?.detail || 'Failed to load system status');
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadStatus();

    let interval: ReturnType<typeof setInterval> | null = null;
    if (autoRefresh) {
      interval = setInterval(loadStatus, 2000); // Refresh every 2 seconds
    }

    return () => {
      if (interval) clearInterval(interval);
    };
  }, [loadStatus, autoRefresh]);

  const getProgressStatus = (percent: number): 'success' | 'normal' | 'exception' => {
    if (percent >= 90) return 'exception';
    if (percent >= 70) return 'normal';
    return 'success';
  };

  const getProgressColor = (percent: number): string => {
    if (percent >= 90) return '#ff4d4f';
    if (percent >= 70) return '#faad14';
    return '#52c41a';
  };

  const diskColumns = [
    {
      title: 'Mount',
      dataIndex: 'mountpoint',
      key: 'mountpoint',
      width: 150,
      ellipsis: true,
    },
    {
      title: 'Total',
      dataIndex: 'total',
      key: 'total',
      width: 100,
      render: (bytes: number) => formatBytes(bytes),
    },
    {
      title: 'Used',
      dataIndex: 'used',
      key: 'used',
      width: 100,
      render: (bytes: number) => formatBytes(bytes),
    },
    {
      title: 'Free',
      dataIndex: 'free',
      key: 'free',
      width: 100,
      render: (bytes: number) => formatBytes(bytes),
    },
    {
      title: 'Usage',
      dataIndex: 'percent',
      key: 'percent',
      width: 200,
      render: (percent: number) => (
        <Progress
          percent={percent}
          size="small"
          status={getProgressStatus(percent)}
          strokeColor={getProgressColor(percent)}
        />
      ),
    },
  ];

  if (loading && !status) {
    return (
      <div style={{ textAlign: 'center', padding: 100 }}>
        <Spin size="large" />
      </div>
    );
  }

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24 }}>
        <Title level={4} style={{ margin: 0 }}>
          <DashboardOutlined style={{ marginRight: 8 }} />
          System Monitor
        </Title>
        <Space>
          <Text type="secondary">
            {lastUpdate && `Last update: ${lastUpdate.toLocaleTimeString()}`}
          </Text>
          <Space>
            <Text>Auto Refresh</Text>
            <Switch checked={autoRefresh} onChange={setAutoRefresh} />
          </Space>
          <Tag icon={<ReloadOutlined spin={autoRefresh} />} color={autoRefresh ? 'processing' : 'default'}>
            {autoRefresh ? 'Live' : 'Paused'}
          </Tag>
        </Space>
      </div>

      {status && (
        <>
          {/* System Info */}
          <Row gutter={[16, 16]} style={{ marginBottom: 24 }}>
            <Col xs={24} sm={12} lg={6}>
              <Card>
                <Statistic
                  title="Uptime"
                  value={formatUptime(status.uptime_seconds)}
                  prefix={<ClockCircleOutlined />}
                />
              </Card>
            </Col>
            <Col xs={24} sm={12} lg={6}>
              <Card>
                <Statistic
                  title="CPU Cores"
                  value={`${status.cpu.count} / ${status.cpu.count_logical}`}
                  suffix="physical / logical"
                />
              </Card>
            </Col>
            <Col xs={24} sm={12} lg={6}>
              <Card>
                <Statistic
                  title="Total Memory"
                  value={formatBytes(status.memory.total)}
                />
              </Card>
            </Col>
            <Col xs={24} sm={12} lg={6}>
              <Card>
                <Statistic
                  title="Boot Time"
                  value={new Date(status.boot_time).toLocaleString()}
                  valueStyle={{ fontSize: 14 }}
                />
              </Card>
            </Col>
          </Row>

          {/* CPU & Memory */}
          <Row gutter={[16, 16]} style={{ marginBottom: 24 }}>
            <Col xs={24} lg={12}>
              <Card title={<><CloudServerOutlined /> CPU Usage</>}>
                <div style={{ textAlign: 'center', padding: '20px 0' }}>
                  <Progress
                    type="dashboard"
                    percent={status.cpu.percent}
                    status={getProgressStatus(status.cpu.percent)}
                    strokeColor={getProgressColor(status.cpu.percent)}
                    format={(percent) => (
                      <div>
                        <div style={{ fontSize: 24, fontWeight: 'bold' }}>{percent}%</div>
                        <div style={{ fontSize: 12, color: '#999' }}>CPU</div>
                      </div>
                    )}
                  />
                </div>
                {status.cpu.freq_current && (
                  <div style={{ textAlign: 'center', marginTop: 16 }}>
                    <Text type="secondary">
                      Frequency: {Math.round(status.cpu.freq_current)} MHz
                      {status.cpu.freq_max && ` / ${Math.round(status.cpu.freq_max)} MHz`}
                    </Text>
                  </div>
                )}
              </Card>
            </Col>
            <Col xs={24} lg={12}>
              <Card title={<><HddOutlined /> Memory Usage</>}>
                <div style={{ textAlign: 'center', padding: '20px 0' }}>
                  <Progress
                    type="dashboard"
                    percent={status.memory.percent}
                    status={getProgressStatus(status.memory.percent)}
                    strokeColor={getProgressColor(status.memory.percent)}
                    format={(percent) => (
                      <div>
                        <div style={{ fontSize: 24, fontWeight: 'bold' }}>{percent}%</div>
                        <div style={{ fontSize: 12, color: '#999' }}>Memory</div>
                      </div>
                    )}
                  />
                </div>
                <Row gutter={16} style={{ marginTop: 16 }}>
                  <Col span={8}>
                    <Statistic title="Used" value={formatBytes(status.memory.used)} valueStyle={{ fontSize: 14 }} />
                  </Col>
                  <Col span={8}>
                    <Statistic title="Available" value={formatBytes(status.memory.available)} valueStyle={{ fontSize: 14 }} />
                  </Col>
                  <Col span={8}>
                    <Statistic title="Total" value={formatBytes(status.memory.total)} valueStyle={{ fontSize: 14 }} />
                  </Col>
                </Row>
              </Card>
            </Col>
          </Row>

          {/* IO Rates */}
          <Row gutter={[16, 16]} style={{ marginBottom: 24 }}>
            <Col xs={24} lg={12}>
              <Card title={<><SwapOutlined /> Disk I/O</>}>
                <Row gutter={16}>
                  <Col span={12}>
                    <Statistic
                      title="Read Rate"
                      value={formatBytesRate(ioRates.diskReadRate)}
                      valueStyle={{ color: '#52c41a' }}
                    />
                  </Col>
                  <Col span={12}>
                    <Statistic
                      title="Write Rate"
                      value={formatBytesRate(ioRates.diskWriteRate)}
                      valueStyle={{ color: '#1890ff' }}
                    />
                  </Col>
                </Row>
                {status.disk_io && (
                  <Row gutter={16} style={{ marginTop: 16 }}>
                    <Col span={12}>
                      <Text type="secondary">Total Read: {formatBytes(status.disk_io.read_bytes)}</Text>
                    </Col>
                    <Col span={12}>
                      <Text type="secondary">Total Write: {formatBytes(status.disk_io.write_bytes)}</Text>
                    </Col>
                  </Row>
                )}
              </Card>
            </Col>
            <Col xs={24} lg={12}>
              <Card title={<><SwapOutlined /> Network I/O</>}>
                <Row gutter={16}>
                  <Col span={12}>
                    <Statistic
                      title="Upload Rate"
                      value={formatBytesRate(ioRates.netSentRate)}
                      valueStyle={{ color: '#722ed1' }}
                    />
                  </Col>
                  <Col span={12}>
                    <Statistic
                      title="Download Rate"
                      value={formatBytesRate(ioRates.netRecvRate)}
                      valueStyle={{ color: '#13c2c2' }}
                    />
                  </Col>
                </Row>
                <Row gutter={16} style={{ marginTop: 16 }}>
                  <Col span={12}>
                    <Text type="secondary">Total Sent: {formatBytes(status.network_io.bytes_sent)}</Text>
                  </Col>
                  <Col span={12}>
                    <Text type="secondary">Total Recv: {formatBytes(status.network_io.bytes_recv)}</Text>
                  </Col>
                </Row>
              </Card>
            </Col>
          </Row>

          {/* Disk Usage */}
          <Card title={<><HddOutlined /> Disk Usage</>}>
            <Table
              columns={diskColumns}
              dataSource={status.disks}
              rowKey="mountpoint"
              pagination={false}
              size="small"
            />
          </Card>
        </>
      )}
    </div>
  );
};

export default SystemMonitor;
