import React, { useState, useEffect, useCallback } from 'react';
import {
  Card,
  Table,
  Button,
  Space,
  message,
  Typography,
  Tag,
  Row,
  Col,
  Popconfirm,
  Select,
  Switch,
  Modal,
  Form,
  InputNumber,
  Input,
  Drawer,
} from 'antd';
import {
  PlusOutlined,
  DeleteOutlined,
  EditOutlined,
  FileOutlined,
  EyeOutlined,
} from '@ant-design/icons';
import type { ColumnsType, TablePaginationConfig } from 'antd/es/table';
import { samplesAPI } from '../services/api';
import type { Sample, SampleView, CreateSampleRequest, UpdateSampleRequest } from '../types/api';

const { Title, Text } = Typography;

const SampleManagement: React.FC = () => {
  const [loading, setLoading] = useState(true);
  const [samples, setSamples] = useState<Sample[]>([]);
  const [pagination, setPagination] = useState({
    current: 1,
    pageSize: 20,
    total: 0,
  });
  const [activeFilter, setActiveFilter] = useState<boolean | undefined>(undefined);

  // Modal state
  const [modalVisible, setModalVisible] = useState(false);
  const [modalMode, setModalMode] = useState<'create' | 'edit'>('create');
  const [editingSample, setEditingSample] = useState<Sample | null>(null);
  const [form] = Form.useForm();
  const [submitting, setSubmitting] = useState(false);

  // Views drawer state
  const [viewsDrawerVisible, setViewsDrawerVisible] = useState(false);
  const [viewsSample, setViewsSample] = useState<Sample | null>(null);
  const [views, setViews] = useState<SampleView[]>([]);
  const [viewsLoading, setViewsLoading] = useState(false);
  const [viewsPagination, setViewsPagination] = useState({
    current: 1,
    pageSize: 50,
    total: 0,
  });

  const loadSamples = useCallback(async (page: number, pageSize: number, isActive?: boolean) => {
    setLoading(true);
    try {
      const data = await samplesAPI.getSamples(page, pageSize, isActive);
      setSamples(data.items);
      setPagination({
        current: data.page,
        pageSize: data.page_size,
        total: data.total,
      });
    } catch (error: unknown) {
      const err = error as { response?: { data?: { detail?: string } } };
      message.error(err.response?.data?.detail || 'Failed to load samples');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadSamples(1, 20);
  }, [loadSamples]);

  const handleTableChange = (paginationConfig: TablePaginationConfig) => {
    loadSamples(
      paginationConfig.current || 1,
      paginationConfig.pageSize || 20,
      activeFilter
    );
  };

  const handleActiveFilterChange = (value: string) => {
    const isActive = value === 'active' ? true : value === 'inactive' ? false : undefined;
    setActiveFilter(isActive);
    loadSamples(1, pagination.pageSize, isActive);
  };

  const handleToggleActive = async (sample: Sample) => {
    try {
      await samplesAPI.updateSample(sample.id, { is_active: !sample.is_active });
      message.success(`Sample ${sample.file_name} status updated`);
      loadSamples(pagination.current, pagination.pageSize, activeFilter);
    } catch (error: unknown) {
      const err = error as { response?: { data?: { detail?: string } } };
      message.error(err.response?.data?.detail || 'Failed to update sample status');
    }
  };

  const handleDelete = async (sample: Sample) => {
    try {
      await samplesAPI.deleteSample(sample.id);
      message.success(`Sample ${sample.file_name} deleted`);
      loadSamples(pagination.current, pagination.pageSize, activeFilter);
    } catch (error: unknown) {
      const err = error as { response?: { data?: { detail?: string } } };
      message.error(err.response?.data?.detail || 'Failed to delete sample');
    }
  };

  const openCreateModal = () => {
    setModalMode('create');
    setEditingSample(null);
    form.resetFields();
    form.setFieldsValue({
      sort_order: 0,
      is_active: true,
    });
    setModalVisible(true);
  };

  const openEditModal = (sample: Sample) => {
    setModalMode('edit');
    setEditingSample(sample);
    form.setFieldsValue({
      file_name: sample.file_name,
      description: sample.description,
      task_id: sample.task_id,
      sort_order: sample.sort_order,
      is_active: sample.is_active,
    });
    setModalVisible(true);
  };

  const handleModalSubmit = async () => {
    try {
      const values = await form.validateFields();
      setSubmitting(true);

      if (modalMode === 'create') {
        const data: CreateSampleRequest = {
          file_name: values.file_name,
          description: values.description,
          task_id: values.task_id,
          sort_order: values.sort_order ?? 0,
          is_active: values.is_active ?? true,
        };
        await samplesAPI.createSample(data);
        message.success('Sample created successfully');
      } else if (editingSample) {
        const data: UpdateSampleRequest = {
          file_name: values.file_name,
          description: values.description,
          task_id: values.task_id,
          sort_order: values.sort_order,
          is_active: values.is_active,
        };
        await samplesAPI.updateSample(editingSample.id, data);
        message.success('Sample updated successfully');
      }

      setModalVisible(false);
      loadSamples(pagination.current, pagination.pageSize, activeFilter);
    } catch (error: unknown) {
      const err = error as { response?: { data?: { detail?: string } } };
      if (err.response?.data?.detail) {
        message.error(err.response.data.detail);
      }
    } finally {
      setSubmitting(false);
    }
  };

  // Views drawer functions
  const loadViews = useCallback(async (sampleId: number, page: number, pageSize: number) => {
    setViewsLoading(true);
    try {
      const data = await samplesAPI.getSampleViews(sampleId, page, pageSize);
      setViews(data.items);
      setViewsPagination({
        current: data.page,
        pageSize: data.page_size,
        total: data.total,
      });
    } catch (error: unknown) {
      const err = error as { response?: { data?: { detail?: string } } };
      message.error(err.response?.data?.detail || 'Failed to load views');
    } finally {
      setViewsLoading(false);
    }
  }, []);

  const openViewsDrawer = (sample: Sample) => {
    setViewsSample(sample);
    setViewsDrawerVisible(true);
    loadViews(sample.id, 1, 50);
  };

  const handleViewsTableChange = (paginationConfig: TablePaginationConfig) => {
    if (viewsSample) {
      loadViews(
        viewsSample.id,
        paginationConfig.current || 1,
        paginationConfig.pageSize || 50
      );
    }
  };

  const viewsColumns: ColumnsType<SampleView> = [
    {
      title: 'IP Address',
      dataIndex: 'ip_address',
      key: 'ip_address',
      width: 150,
    },
    {
      title: 'User Agent',
      dataIndex: 'user_agent',
      key: 'user_agent',
      ellipsis: true,
      render: (ua: string | null) => ua || '-',
    },
    {
      title: 'Viewed At',
      dataIndex: 'viewed_at',
      key: 'viewed_at',
      width: 180,
      render: (date: string | null) => {
        if (!date) return '-';
        return new Date(date).toLocaleString();
      },
    },
  ];

  const columns: ColumnsType<Sample> = [
    {
      title: 'File Name',
      key: 'file_name',
      render: (_, record) => (
        <Space>
          <FileOutlined style={{ color: '#1890ff' }} />
          <Text strong>{record.file_name}</Text>
        </Space>
      ),
    },
    {
      title: 'Description',
      dataIndex: 'description',
      key: 'description',
    },
    {
      title: 'Task ID',
      dataIndex: 'task_id',
      key: 'task_id',
      render: (taskId: string) => (
        <Text code copyable style={{ fontSize: 12 }}>
          {taskId}
        </Text>
      ),
    },
    {
      title: 'Views',
      dataIndex: 'view_count',
      key: 'view_count',
      width: 100,
      align: 'center',
      render: (count: number, record) => (
        <Button
          type="link"
          size="small"
          icon={<EyeOutlined />}
          onClick={() => openViewsDrawer(record)}
        >
          {count}
        </Button>
      ),
    },
    {
      title: 'Sort',
      dataIndex: 'sort_order',
      key: 'sort_order',
      width: 80,
      align: 'center',
    },
    {
      title: 'Status',
      key: 'status',
      width: 100,
      render: (_, record) => (
        record.is_active ? (
          <Tag color="green">Active</Tag>
        ) : (
          <Tag color="default">Inactive</Tag>
        )
      ),
    },
    {
      title: 'Active',
      key: 'active_toggle',
      width: 80,
      render: (_, record) => (
        <Switch
          checked={record.is_active}
          checkedChildren="Yes"
          unCheckedChildren="No"
          size="small"
          onChange={() => handleToggleActive(record)}
        />
      ),
    },
    {
      title: 'Actions',
      key: 'actions',
      width: 150,
      render: (_, record) => (
        <Space>
          <Button
            type="link"
            icon={<EditOutlined />}
            size="small"
            onClick={() => openEditModal(record)}
          >
            Edit
          </Button>
          <Popconfirm
            title="Delete sample?"
            description={`Are you sure you want to delete "${record.file_name}"?`}
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
        </Space>
      ),
    },
  ];

  return (
    <div>
      <Title level={4} style={{ marginBottom: 24 }}>Sample Management</Title>

      {/* Filters */}
      <Card style={{ marginBottom: 16 }}>
        <Row gutter={[16, 16]} align="middle" justify="space-between">
          <Col>
            <Space>
              <Select
                placeholder="Filter by status"
                style={{ width: 150 }}
                allowClear
                onChange={handleActiveFilterChange}
                options={[
                  { value: 'all', label: 'All Samples' },
                  { value: 'active', label: 'Active Only' },
                  { value: 'inactive', label: 'Inactive Only' },
                ]}
              />
            </Space>
          </Col>
          <Col>
            <Button type="primary" icon={<PlusOutlined />} onClick={openCreateModal}>
              Add Sample
            </Button>
          </Col>
        </Row>
      </Card>

      {/* Samples Table */}
      <Card>
        <Table
          columns={columns}
          dataSource={samples}
          rowKey="id"
          loading={loading}
          pagination={{
            ...pagination,
            showSizeChanger: true,
            showQuickJumper: true,
            showTotal: (total) => `Total ${total} samples`,
          }}
          onChange={handleTableChange}
        />
      </Card>

      {/* Create/Edit Modal */}
      <Modal
        title={modalMode === 'create' ? 'Add Sample' : 'Edit Sample'}
        open={modalVisible}
        onOk={handleModalSubmit}
        onCancel={() => setModalVisible(false)}
        confirmLoading={submitting}
        width={500}
      >
        <Form
          form={form}
          layout="vertical"
          style={{ marginTop: 16 }}
        >
          <Form.Item
            name="file_name"
            label="File Name"
            rules={[{ required: true, message: 'Please enter file name' }]}
          >
            <Input placeholder="e.g., busybox" />
          </Form.Item>

          <Form.Item
            name="description"
            label="Description"
            rules={[{ required: true, message: 'Please enter description' }]}
          >
            <Input placeholder="e.g., SCA, Malware analysis" />
          </Form.Item>

          <Form.Item
            name="task_id"
            label="Task ID"
            rules={[{ required: true, message: 'Please enter task ID' }]}
          >
            <Input placeholder="Enter the task ID of the completed analysis" />
          </Form.Item>

          <Form.Item
            name="sort_order"
            label="Sort Order"
            tooltip="Lower numbers appear first"
          >
            <InputNumber min={0} style={{ width: '100%' }} />
          </Form.Item>

          <Form.Item
            name="is_active"
            label="Active"
            valuePropName="checked"
          >
            <Switch checkedChildren="Yes" unCheckedChildren="No" />
          </Form.Item>
        </Form>
      </Modal>

      {/* Views Drawer */}
      <Drawer
        title={viewsSample ? `Views for "${viewsSample.file_name}"` : 'Sample Views'}
        placement="right"
        width={700}
        onClose={() => setViewsDrawerVisible(false)}
        open={viewsDrawerVisible}
        extra={
          viewsSample && (
            <Tag color="blue">Total: {viewsSample.view_count} views</Tag>
          )
        }
      >
        <Table
          columns={viewsColumns}
          dataSource={views}
          rowKey="id"
          loading={viewsLoading}
          pagination={{
            ...viewsPagination,
            showSizeChanger: true,
            showTotal: (total) => `Total ${total} views`,
          }}
          onChange={handleViewsTableChange}
          size="small"
        />
      </Drawer>
    </div>
  );
};

export default SampleManagement;
