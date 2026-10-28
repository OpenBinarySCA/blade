import React, { useState, useEffect } from 'react';
import {
  Card,
  Table,
  Button,
  Input,
  Space,
  Modal,
  Form,
  message,
  Popconfirm,
  Tag,
  Typography,
  Progress,
  Row,
  Col,
  Statistic,
  Tooltip,
  Collapse,
} from 'antd';
import {
  PlusOutlined,
  SearchOutlined,
  EditOutlined,
  DeleteOutlined,
  ReloadOutlined,
  SyncOutlined,
  DatabaseOutlined,
  CheckCircleOutlined,
  CodeOutlined,
  SafetyOutlined,
} from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';
import { libraryAPI, statsAPI } from '../services/api';
import type { Library, CreateLibraryRequest, UpdateLibraryRequest, BatchRefreshTask, Statistics } from '../types/api';

const { Title } = Typography;

const LibraryManagement: React.FC = () => {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(false);
  const [libraries, setLibraries] = useState<Library[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [search, setSearch] = useState('');
  const [modalVisible, setModalVisible] = useState(false);
  const [editingLibrary, setEditingLibrary] = useState<Library | null>(null);
  const [batchRefreshTask, setBatchRefreshTask] = useState<BatchRefreshTask | null>(null);
  const [statistics, setStatistics] = useState<Statistics | null>(null);
  const [form] = Form.useForm();

  useEffect(() => {
    loadLibraries();
    loadStatistics();
  }, [page, pageSize]);

  const loadStatistics = async () => {
    try {
      const data = await statsAPI.getStatistics();
      setStatistics(data);
    } catch {
      // Statistics are optional, don't show error
    }
  };

  const loadLibraries = async (searchTerm?: string) => {
    setLoading(true);
    try {
      const data = await libraryAPI.getLibraries(
        page,
        pageSize,
        searchTerm !== undefined ? searchTerm : search
      );
      setLibraries(data.items);
      setTotal(data.total);
    } catch (error: unknown) {
      const err = error as { response?: { data?: { detail?: string } } };
      message.error(err.response?.data?.detail || 'Failed to load libraries');
    } finally {
      setLoading(false);
    }
  };

  const handleSearch = () => {
    setPage(1);
    loadLibraries(search);
  };

  const handleCreate = () => {
    setEditingLibrary(null);
    form.resetFields();
    setModalVisible(true);
  };

  const handleEdit = (record: Library) => {
    setEditingLibrary(record);
    form.setFieldsValue({
      name: record.name,
      vendor: record.vendor,
      source: record.source?.join(', '),
      homepage: record.homepage,
      giturl: record.giturl,
      alias: record.alias,
    });
    setModalVisible(true);
  };

  const handleDelete = async (id: number) => {
    try {
      await libraryAPI.deleteLibrary(id);
      message.success('Library deleted');
      loadLibraries();
    } catch (error: unknown) {
      const err = error as { response?: { data?: { detail?: string } } };
      message.error(err.response?.data?.detail || 'Failed to delete library');
    }
  };

  const handleSubmit = async (values: {
    name: string;
    vendor?: string;
    source: string;
    homepage?: string;
    giturl?: string;
    alias?: string;
  }) => {
    try {
      const sourceArray = values.source
        .split(',')
        .map(s => s.trim())
        .filter(s => s);

      if (editingLibrary) {
        const updateData: UpdateLibraryRequest = {
          name: values.name,
          vendor: values.vendor,
          source: sourceArray,
          homepage: values.homepage,
          giturl: values.giturl,
          alias: values.alias,
        };
        await libraryAPI.updateLibrary(editingLibrary.id, updateData);
        message.success('Library updated');
      } else {
        const createData: CreateLibraryRequest = {
          name: values.name,
          vendor: values.vendor,
          source: sourceArray,
          homepage: values.homepage,
          giturl: values.giturl,
          alias: values.alias,
        };
        await libraryAPI.createLibrary(createData);
        message.success('Library created');
      }
      setModalVisible(false);
      loadLibraries();
    } catch (error: unknown) {
      const err = error as { response?: { data?: { detail?: string } } };
      message.error(err.response?.data?.detail || 'Operation failed');
    }
  };

  const handleBatchRefresh = async () => {
    try {
      const task = await libraryAPI.batchRefreshStatus();
      setBatchRefreshTask(task);
      message.info('Batch refresh started');
      pollBatchRefreshStatus(task.task_id);
    } catch (error: unknown) {
      const err = error as { response?: { data?: { detail?: string } } };
      message.error(err.response?.data?.detail || 'Failed to start batch refresh');
    }
  };

  const pollBatchRefreshStatus = async (taskId: string) => {
    const poll = async () => {
      try {
        const task = await libraryAPI.getBatchRefreshStatus(taskId);
        setBatchRefreshTask(task);

        if (task.status === 'running' || task.status === 'pending') {
          setTimeout(poll, 2000);
        } else {
          if (task.status === 'success') {
            message.success('Batch refresh completed');
          } else if (task.status === 'partial_success') {
            message.warning('Batch refresh completed with some failures');
          } else {
            message.error('Batch refresh failed');
          }
          setTimeout(() => setBatchRefreshTask(null), 5000);
        }
      } catch {
        setBatchRefreshTask(null);
      }
    };
    poll();
  };

  const columns = [
    {
      title: 'ID',
      dataIndex: 'id',
      key: 'id',
      width: 60,
    },
    {
      title: 'Name',
      dataIndex: 'name',
      key: 'name',
      width: 150,
      render: (text: string, record: Library) => (
        <a onClick={() => navigate(`/libraries/${record.id}`)}>{text}</a>
      ),
    },
    {
      title: 'Vendor',
      dataIndex: 'vendor',
      key: 'vendor',
      width: 120,
      render: (text: string | null) => text || '-',
    },
    {
      title: 'Language',
      dataIndex: 'language',
      key: 'language',
      width: 120,
      render: (languages: string[] | null) => (
        languages && languages.length > 0 ? (
          <Space wrap size={[0, 4]}>
            {languages.map((lang, i) => (
              <Tag key={i} color="green">{lang}</Tag>
            ))}
          </Space>
        ) : '-'
      ),
    },
    {
      title: 'Categories',
      dataIndex: 'categories',
      key: 'categories',
      width: 150,
      render: (categories: string[] | null) => (
        categories && categories.length > 0 ? (
          <Space wrap size={[0, 4]}>
            {categories.map((cat, i) => (
              <Tag key={i} color="purple">{cat}</Tag>
            ))}
          </Space>
        ) : '-'
      ),
    },
    {
      title: 'Metadata',
      key: 'metadata',
      width: 150,
      render: (_: unknown, record: Library) => {
        const hasGiturl = !!record.giturl;
        const hasHomepage = !!record.homepage;
        const hasDescription = !!record.description;
        const hasPurl = !!record.purl;
        return (
          <Space size={[4, 0]} wrap>
            <Tooltip title={hasGiturl ? 'Has Git URL' : 'No Git URL'}>
              <Tag color={hasGiturl ? 'green' : 'default'}>Git</Tag>
            </Tooltip>
            <Tooltip title={hasHomepage ? 'Has Homepage' : 'No Homepage'}>
              <Tag color={hasHomepage ? 'green' : 'default'}>Web</Tag>
            </Tooltip>
            <Tooltip title={hasDescription ? 'Has Description' : 'No Description'}>
              <Tag color={hasDescription ? 'green' : 'default'}>Desc</Tag>
            </Tooltip>
            <Tooltip title={hasPurl ? 'Has PURL' : 'No PURL'}>
              <Tag color={hasPurl ? 'green' : 'default'}>PURL</Tag>
            </Tooltip>
          </Space>
        );
      },
    },
    {
      title: 'Source',
      dataIndex: 'source',
      key: 'source',
      width: 100,
      render: (sources: string[]) => (
        <Space wrap size={[0, 4]}>
          {sources?.map((s, i) => (
            <Tag key={i} color="blue">{s}</Tag>
          ))}
        </Space>
      ),
    },
    {
      title: 'Created',
      dataIndex: 'created_at',
      key: 'created_at',
      width: 100,
      render: (text: string | null) => text?.slice(0, 10) || '-',
    },
    {
      title: 'Actions',
      key: 'actions',
      width: 100,
      render: (_: unknown, record: Library) => (
        <Space>
          <Button
            type="text"
            icon={<EditOutlined />}
            onClick={() => handleEdit(record)}
          />
          <Popconfirm
            title="Delete this library?"
            description="This action cannot be undone."
            onConfirm={() => handleDelete(record.id)}
            okText="Yes"
            cancelText="No"
          >
            <Button type="text" danger icon={<DeleteOutlined />} />
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <div>
      <Title level={4} style={{ marginBottom: 24 }}>Library Management</Title>

      {/* Statistics Panel */}
      {statistics && (
        <Row gutter={[16, 16]} style={{ marginBottom: 24 }}>
          <Col xs={24} sm={12} lg={6}>
            <Card>
              <Statistic
                title="Total Libraries"
                value={statistics.library.total}
                prefix={<DatabaseOutlined />}
              />
            </Card>
          </Col>
          <Col xs={24} sm={12} lg={6}>
            <Card bodyStyle={{ padding: 0 }}>
              <Collapse
                ghost
                expandIconPosition="end"
                items={[{
                  key: 'metadata',
                  label: (
                    <div style={{ padding: '12px 0' }}>
                      <Statistic
                        title="Complete Metadata"
                        value={statistics.library.complete_metadata}
                        suffix={`/ ${statistics.library.total}`}
                        prefix={<CheckCircleOutlined style={{ color: '#52c41a' }} />}
                        valueStyle={{ fontSize: 24 }}
                      />
                      <Progress
                        percent={statistics.library.total > 0 ? Math.round((statistics.library.complete_metadata / statistics.library.total) * 100) : 0}
                        size="small"
                        showInfo={false}
                        strokeColor="#52c41a"
                      />
                    </div>
                  ),
                  children: (
                    <div style={{ padding: '0 12px 12px' }}>
                      {[
                        { label: 'Vendor', value: statistics.metadata_fields.has_vendor },
                        { label: 'Git URL', value: statistics.metadata_fields.has_giturl },
                        { label: 'Homepage', value: statistics.metadata_fields.has_homepage },
                        { label: 'Description', value: statistics.metadata_fields.has_description },
                        { label: 'PURL', value: statistics.metadata_fields.has_purl },
                        { label: 'Language', value: statistics.metadata_fields.has_language },
                        { label: 'Source Code', value: statistics.metadata_fields.has_source_code },
                      ].map((item) => {
                        const percent = statistics.library.total > 0 ? Math.round((item.value / statistics.library.total) * 100) : 0;
                        return (
                          <div key={item.label} style={{ marginBottom: 8 }}>
                            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12 }}>
                              <span>{item.label}</span>
                              <span>{item.value} / {statistics.library.total} ({percent}%)</span>
                            </div>
                            <Progress percent={percent} size="small" showInfo={false} strokeColor={percent >= 80 ? '#52c41a' : percent >= 50 ? '#faad14' : '#ff4d4f'} />
                          </div>
                        );
                      })}
                    </div>
                  ),
                }]}
              />
            </Card>
          </Col>
          <Col xs={24} sm={12} lg={6}>
            <Card>
              <Statistic
                title="Has Features"
                value={statistics.library.has_features}
                suffix={`/ ${statistics.library.total}`}
                prefix={<CodeOutlined style={{ color: '#1890ff' }} />}
              />
              <Progress
                percent={statistics.library.total > 0 ? Math.round((statistics.library.has_features / statistics.library.total) * 100) : 0}
                size="small"
                showInfo={false}
                strokeColor="#1890ff"
              />
            </Card>
          </Col>
          <Col xs={24} sm={12} lg={6}>
            <Card>
              <Tooltip title={`${statistics.vulnerability.affected_libraries} affected, ${statistics.vulnerability.high_risk_libraries} high risk`}>
                <Statistic
                  title="Safe Libraries"
                  value={statistics.vulnerability.safe_libraries}
                  suffix={`/ ${statistics.library.total}`}
                  prefix={<SafetyOutlined style={{ color: '#52c41a' }} />}
                />
              </Tooltip>
              <Progress
                percent={statistics.library.total > 0 ? Math.round((statistics.vulnerability.safe_libraries / statistics.library.total) * 100) : 0}
                size="small"
                showInfo={false}
                strokeColor="#52c41a"
              />
            </Card>
          </Col>
        </Row>
      )}

      {/* Batch Refresh Progress */}
      {batchRefreshTask && (
        <Card style={{ marginBottom: 16 }}>
          <Space direction="vertical" style={{ width: '100%' }}>
            <Space>
              <SyncOutlined spin />
              <span>Batch Refresh in Progress</span>
            </Space>
            <Progress
              percent={batchRefreshTask.progress_percent || 0}
              status={
                batchRefreshTask.status === 'success'
                  ? 'success'
                  : batchRefreshTask.status === 'failed'
                  ? 'exception'
                  : 'active'
              }
            />
            <span style={{ color: '#666' }}>
              {batchRefreshTask.completed_libraries} / {batchRefreshTask.total_libraries} libraries processed
              {batchRefreshTask.current_library_name && ` - Current: ${batchRefreshTask.current_library_name}`}
            </span>
          </Space>
        </Card>
      )}

      <Card>
        {/* Toolbar */}
        <Space style={{ marginBottom: 16 }} wrap>
          <Input
            placeholder="Search libraries..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            onPressEnter={handleSearch}
            style={{ width: 300 }}
            prefix={<SearchOutlined />}
            allowClear
          />
          <Button type="primary" onClick={handleSearch}>
            Search
          </Button>
          <Button icon={<ReloadOutlined />} onClick={() => loadLibraries()}>
            Refresh
          </Button>
          <Button type="primary" icon={<PlusOutlined />} onClick={handleCreate}>
            Add Library
          </Button>
          <Button
            icon={<SyncOutlined />}
            onClick={handleBatchRefresh}
            disabled={!!batchRefreshTask}
          >
            Batch Refresh Status
          </Button>
        </Space>

        {/* Table */}
        <Table
          columns={columns}
          dataSource={libraries}
          rowKey="id"
          loading={loading}
          pagination={{
            current: page,
            pageSize: pageSize,
            total: total,
            showSizeChanger: true,
            showTotal: (total) => `Total ${total} libraries`,
            onChange: (p, ps) => {
              setPage(p);
              setPageSize(ps);
            },
          }}
        />
      </Card>

      {/* Create/Edit Modal */}
      <Modal
        title={editingLibrary ? 'Edit Library' : 'Add Library'}
        open={modalVisible}
        onCancel={() => setModalVisible(false)}
        footer={null}
        width={600}
      >
        <Form
          form={form}
          layout="vertical"
          onFinish={handleSubmit}
        >
          <Form.Item
            name="name"
            label="Name"
            rules={[{ required: true, message: 'Please enter library name' }]}
          >
            <Input placeholder="e.g., openssl" />
          </Form.Item>
          <Form.Item
            name="vendor"
            label="Vendor"
          >
            <Input placeholder="e.g., OpenSSL Software Foundation" />
          </Form.Item>
          <Form.Item
            name="source"
            label="Source (comma separated)"
            rules={[{ required: true, message: 'Please enter at least one source' }]}
          >
            <Input placeholder="e.g., github, gitlab" />
          </Form.Item>
          <Form.Item
            name="homepage"
            label="Homepage"
          >
            <Input placeholder="e.g., https://www.openssl.org" />
          </Form.Item>
          <Form.Item
            name="giturl"
            label="Git URL"
          >
            <Input placeholder="e.g., https://github.com/openssl/openssl" />
          </Form.Item>
          <Form.Item
            name="alias"
            label="Alias"
          >
            <Input placeholder="Alternative names" />
          </Form.Item>
          <Form.Item>
            <Space>
              <Button type="primary" htmlType="submit">
                {editingLibrary ? 'Update' : 'Create'}
              </Button>
              <Button onClick={() => setModalVisible(false)}>
                Cancel
              </Button>
            </Space>
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
};

export default LibraryManagement;
