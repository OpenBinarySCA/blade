import React, { useState, useEffect } from 'react';
import { Card, Row, Col, Statistic, Spin, message, Progress, Typography } from 'antd';
import {
  DatabaseOutlined,
  CodeOutlined,
  CheckCircleOutlined,
  WarningOutlined,
  FileOutlined,
  BugOutlined,
} from '@ant-design/icons';
import { statsAPI } from '../services/api';
import type { Statistics } from '../types/api';

const { Title } = Typography;

const Dashboard: React.FC = () => {
  const [loading, setLoading] = useState(true);
  const [stats, setStats] = useState<Statistics | null>(null);

  useEffect(() => {
    loadStatistics();
  }, []);

  const loadStatistics = async () => {
    setLoading(true);
    try {
      const data = await statsAPI.getStatistics();
      setStats(data);
    } catch (error: unknown) {
      const err = error as { response?: { data?: { detail?: string } } };
      message.error(err.response?.data?.detail || 'Failed to load statistics');
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div style={{ textAlign: 'center', padding: 100 }}>
        <Spin size="large" />
      </div>
    );
  }

  if (!stats) {
    return <div>Failed to load statistics</div>;
  }

  const featurePercent = stats.library.total > 0
    ? Math.round((stats.library.has_features / stats.library.total) * 100)
    : 0;

  const sourceCodePercent = stats.library.total > 0
    ? Math.round((stats.source_code.libraries_with_source / stats.library.total) * 100)
    : 0;

  return (
    <div>
      <Title level={4} style={{ marginBottom: 24 }}>Dashboard</Title>

      {/* Library Statistics */}
      <Row gutter={[16, 16]}>
        <Col xs={24} sm={12} lg={6}>
          <Card>
            <Statistic
              title="Total Libraries"
              value={stats.library.total}
              prefix={<DatabaseOutlined style={{ color: '#1890ff' }} />}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card>
            <Statistic
              title="Total Source Codes"
              value={stats.source_code.total}
              prefix={<CodeOutlined style={{ color: '#52c41a' }} />}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card>
            <Statistic
              title="Libraries with Features"
              value={stats.library.has_features}
              prefix={<CheckCircleOutlined style={{ color: '#722ed1' }} />}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card>
            <Statistic
              title="Avg Source Codes / Library"
              value={stats.source_code.avg_per_library}
              precision={1}
              prefix={<FileOutlined style={{ color: '#faad14' }} />}
            />
          </Card>
        </Col>
      </Row>

      {/* Progress Cards */}
      <Row gutter={[16, 16]} style={{ marginTop: 24 }}>
        <Col xs={24} sm={12}>
          <Card title="Feature Coverage">
            <Progress
              percent={featurePercent}
              status={featurePercent > 80 ? 'success' : featurePercent > 50 ? 'normal' : 'exception'}
              strokeColor={featurePercent > 80 ? '#52c41a' : featurePercent > 50 ? '#1890ff' : '#ff4d4f'}
            />
            <div style={{ marginTop: 16, color: '#666' }}>
              {stats.library.has_features} of {stats.library.total} libraries have extracted features
            </div>
          </Card>
        </Col>
        <Col xs={24} sm={12}>
          <Card title="Source Code Coverage">
            <Progress
              percent={sourceCodePercent}
              status={sourceCodePercent > 80 ? 'success' : sourceCodePercent > 50 ? 'normal' : 'exception'}
              strokeColor={sourceCodePercent > 80 ? '#52c41a' : sourceCodePercent > 50 ? '#1890ff' : '#ff4d4f'}
            />
            <div style={{ marginTop: 16, color: '#666' }}>
              {stats.source_code.libraries_with_source} of {stats.library.total} libraries have source codes
            </div>
          </Card>
        </Col>
      </Row>

      {/* Additional Stats */}
      <Row gutter={[16, 16]} style={{ marginTop: 24 }}>
        <Col xs={24} sm={12} lg={6}>
          <Card>
            <Statistic
              title="Libraries without Source"
              value={stats.source_code.libraries_without_source}
              prefix={<WarningOutlined style={{ color: '#faad14' }} />}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card>
            <Statistic
              title="Total Binaries"
              value={stats.binary.total}
              prefix={<FileOutlined style={{ color: '#13c2c2' }} />}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card>
            <Statistic
              title="Total Vulnerabilities"
              value={stats.vulnerability.total}
              prefix={<BugOutlined style={{ color: '#f5222d' }} />}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card>
            <Statistic
              title="Affected Libraries"
              value={stats.vulnerability.affected_libraries}
              prefix={<WarningOutlined style={{ color: '#fa8c16' }} />}
            />
          </Card>
        </Col>
      </Row>
    </div>
  );
};

export default Dashboard;
