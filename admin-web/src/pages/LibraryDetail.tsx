import React, { useState, useEffect } from 'react';
import {
  Card,
  Descriptions,
  Table,
  Button,
  Space,
  Modal,
  Form,
  Input,
  DatePicker,
  message,
  Popconfirm,
  Tag,
  Typography,
  Spin,
  Row,
  Col,
  Statistic,
  Select,
  Tabs,
  Empty,
  Tooltip,
  Badge,
} from 'antd';
import {
  ArrowLeftOutlined,
  PlusOutlined,
  EditOutlined,
  DeleteOutlined,
  ReloadOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
  BugOutlined,
  FileOutlined,
  CodeOutlined,
  WarningOutlined,
  SearchOutlined,
  SafetyCertificateOutlined,
} from '@ant-design/icons';
import { useParams, useNavigate } from 'react-router-dom';
import dayjs from 'dayjs';
import { libraryAPI, sourceCodeAPI } from '../services/api';
import type {
  LibraryDetail as LibraryDetailType,
  LibraryStatus,
  SourceCode,
  CreateSourceCodeRequest,
  UpdateSourceCodeRequest,
  UpdateLibraryRequest,
  Vulnerability,
  Binary,
  StringFeature,
  FunctionNameFeature,
  License,
} from '../types/api';

const { Title, Text, Paragraph } = Typography;

const LibraryDetail: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [library, setLibrary] = useState<LibraryDetailType | null>(null);
  const [status, setStatus] = useState<LibraryStatus | null>(null);
  const [activeTab, setActiveTab] = useState('source_codes');

  // Source Code state
  const [sourceCodes, setSourceCodes] = useState<SourceCode[]>([]);
  const [sourceCodeTotal, setSourceCodeTotal] = useState(0);
  const [sourceCodePage, setSourceCodePage] = useState(1);
  const [sourceCodePageSize, setSourceCodePageSize] = useState(20);
  const [sourceCodeLoading, setSourceCodeLoading] = useState(false);

  // Vulnerability state
  const [vulnerabilities, setVulnerabilities] = useState<Vulnerability[]>([]);
  const [vulnTotal, setVulnTotal] = useState(0);
  const [vulnPage, setVulnPage] = useState(1);
  const [vulnPageSize, setVulnPageSize] = useState(20);
  const [vulnLoading, setVulnLoading] = useState(false);

  // Binary state
  const [binaries, setBinaries] = useState<Binary[]>([]);
  const [binaryTotal, setBinaryTotal] = useState(0);
  const [binaryPage, setBinaryPage] = useState(1);
  const [binaryPageSize, setBinaryPageSize] = useState(20);
  const [binaryLoading, setBinaryLoading] = useState(false);

  // String Feature state
  const [stringFeatures, setStringFeatures] = useState<StringFeature[]>([]);
  const [stringTotal, setStringTotal] = useState(0);
  const [stringPage, setStringPage] = useState(1);
  const [stringPageSize, setStringPageSize] = useState(50);
  const [stringSearch, setStringSearch] = useState('');
  const [stringLoading, setStringLoading] = useState(false);

  // Function Name state
  const [functionNames, setFunctionNames] = useState<FunctionNameFeature[]>([]);
  const [funcTotal, setFuncTotal] = useState(0);
  const [funcPage, setFuncPage] = useState(1);
  const [funcPageSize, setFuncPageSize] = useState(50);
  const [funcSearch, setFuncSearch] = useState('');
  const [funcLoading, setFuncLoading] = useState(false);

  // License state
  const [licenses, setLicenses] = useState<License[]>([]);
  const [licenseTotal, setLicenseTotal] = useState(0);
  const [licensePage, setLicensePage] = useState(1);
  const [licensePageSize, setLicensePageSize] = useState(20);
  const [licenseLoading, setLicenseLoading] = useState(false);

  // Modal states
  const [modalVisible, setModalVisible] = useState(false);
  const [editingSourceCode, setEditingSourceCode] = useState<SourceCode | null>(null);
  const [refreshing, setRefreshing] = useState(false);
  const [libraryEditModalVisible, setLibraryEditModalVisible] = useState(false);
  const [form] = Form.useForm();
  const [libraryForm] = Form.useForm();

  const libraryId = id ? parseInt(id) : 0;

  useEffect(() => {
    if (libraryId) {
      loadLibraryDetail();
      loadLibraryStatus();
    }
  }, [libraryId]);

  // Load data based on active tab
  useEffect(() => {
    if (libraryId) {
      if (activeTab === 'source_codes') {
        loadSourceCodes();
      } else if (activeTab === 'vulnerabilities') {
        loadVulnerabilities();
      } else if (activeTab === 'binaries') {
        loadBinaries();
      } else if (activeTab === 'strings') {
        loadStringFeatures();
      } else if (activeTab === 'functions') {
        loadFunctionNames();
      } else if (activeTab === 'licenses') {
        loadLicenses();
      }
    }
  }, [libraryId, activeTab, sourceCodePage, sourceCodePageSize, vulnPage, vulnPageSize,
      binaryPage, binaryPageSize, stringPage, stringPageSize, funcPage, funcPageSize,
      licensePage, licensePageSize]);

  const loadLibraryDetail = async () => {
    setLoading(true);
    try {
      const data = await libraryAPI.getLibrary(libraryId);
      setLibrary(data);
    } catch (error: unknown) {
      const err = error as { response?: { data?: { detail?: string } } };
      message.error(err.response?.data?.detail || 'Failed to load library');
    } finally {
      setLoading(false);
    }
  };

  const loadLibraryStatus = async () => {
    try {
      const data = await libraryAPI.getLibraryStatus(libraryId);
      setStatus(data);
    } catch {
      // Status might not exist yet
    }
  };

  const loadSourceCodes = async () => {
    setSourceCodeLoading(true);
    try {
      const data = await sourceCodeAPI.getLibrarySourceCodes(
        libraryId,
        sourceCodePage,
        sourceCodePageSize
      );
      setSourceCodes(data.items);
      setSourceCodeTotal(data.total);
    } catch (error: unknown) {
      const err = error as { response?: { data?: { detail?: string } } };
      message.error(err.response?.data?.detail || 'Failed to load source codes');
    } finally {
      setSourceCodeLoading(false);
    }
  };

  const loadVulnerabilities = async () => {
    setVulnLoading(true);
    try {
      const data = await libraryAPI.getLibraryVulnerabilities(libraryId, vulnPage, vulnPageSize);
      setVulnerabilities(data.items);
      setVulnTotal(data.total);
    } catch (error: unknown) {
      const err = error as { response?: { data?: { detail?: string } } };
      message.error(err.response?.data?.detail || 'Failed to load vulnerabilities');
    } finally {
      setVulnLoading(false);
    }
  };

  const loadBinaries = async () => {
    setBinaryLoading(true);
    try {
      const data = await libraryAPI.getLibraryBinaries(libraryId, binaryPage, binaryPageSize);
      setBinaries(data.items);
      setBinaryTotal(data.total);
    } catch (error: unknown) {
      const err = error as { response?: { data?: { detail?: string } } };
      message.error(err.response?.data?.detail || 'Failed to load binaries');
    } finally {
      setBinaryLoading(false);
    }
  };

  const loadStringFeatures = async () => {
    setStringLoading(true);
    try {
      const data = await libraryAPI.getLibraryStringFeatures(
        libraryId, stringPage, stringPageSize, stringSearch || undefined
      );
      setStringFeatures(data.items);
      setStringTotal(data.total);
    } catch (error: unknown) {
      const err = error as { response?: { data?: { detail?: string } } };
      message.error(err.response?.data?.detail || 'Failed to load string features');
    } finally {
      setStringLoading(false);
    }
  };

  const loadFunctionNames = async () => {
    setFuncLoading(true);
    try {
      const data = await libraryAPI.getLibraryFunctionNames(
        libraryId, funcPage, funcPageSize, funcSearch || undefined
      );
      setFunctionNames(data.items);
      setFuncTotal(data.total);
    } catch (error: unknown) {
      const err = error as { response?: { data?: { detail?: string } } };
      message.error(err.response?.data?.detail || 'Failed to load function names');
    } finally {
      setFuncLoading(false);
    }
  };

  const loadLicenses = async () => {
    setLicenseLoading(true);
    try {
      const data = await libraryAPI.getLibraryLicenses(
        libraryId, licensePage, licensePageSize
      );
      setLicenses(data.items);
      setLicenseTotal(data.total);
    } catch (error: unknown) {
      const err = error as { response?: { data?: { detail?: string } } };
      message.error(err.response?.data?.detail || 'Failed to load licenses');
    } finally {
      setLicenseLoading(false);
    }
  };

  const handleRefreshStatus = async () => {
    setRefreshing(true);
    try {
      const data = await libraryAPI.refreshLibraryStatus(libraryId);
      setStatus(data);
      message.success('Status refreshed');
    } catch (error: unknown) {
      const err = error as { response?: { data?: { detail?: string } } };
      message.error(err.response?.data?.detail || 'Failed to refresh status');
    } finally {
      setRefreshing(false);
    }
  };

  const handleCreateSourceCode = () => {
    setEditingSourceCode(null);
    form.resetFields();
    setModalVisible(true);
  };

  const handleEditSourceCode = (record: SourceCode) => {
    setEditingSourceCode(record);
    form.setFieldsValue({
      commit_id: record.commit_id,
      version_source: record.version_source,
      semantic_version_str: record.semantic_version_str,
      original_version_strs: record.original_version_strs?.join(', '),
      commit_datetime: record.commit_datetime ? dayjs(record.commit_datetime) : null,
      tag_datetime: record.tag_datetime ? dayjs(record.tag_datetime) : null,
    });
    setModalVisible(true);
  };

  const handleDeleteSourceCode = async (sourceCodeId: number) => {
    try {
      await sourceCodeAPI.deleteSourceCode(sourceCodeId);
      message.success('Source code deleted');
      loadSourceCodes();
      loadLibraryStatus();
    } catch (error: unknown) {
      const err = error as { response?: { data?: { detail?: string } } };
      message.error(err.response?.data?.detail || 'Failed to delete source code');
    }
  };

  const handleEditLibrary = () => {
    if (library) {
      libraryForm.setFieldsValue({
        name: library.name,
        vendor: library.vendor,
        alias: library.alias,
        source: library.source?.join(', '),
        homepage: library.homepage,
        giturl: library.giturl,
        purl: library.purl,
        language: library.language,
        categories: library.categories,
        description: library.description,
      });
      setLibraryEditModalVisible(true);
    }
  };

  const handleSubmitLibrary = async (values: {
    name: string;
    vendor?: string;
    alias?: string;
    source?: string;
    homepage?: string;
    giturl?: string;
    purl?: string;
    language?: string[];
    categories?: string[];
    description?: string;
  }) => {
    try {
      const sourceArray = values.source
        ?.split(',')
        .map(s => s.trim())
        .filter(s => s);

      const updateData: UpdateLibraryRequest = {
        name: values.name,
        vendor: values.vendor || undefined,
        alias: values.alias || undefined,
        source: sourceArray && sourceArray.length > 0 ? sourceArray : undefined,
        homepage: values.homepage || undefined,
        giturl: values.giturl || undefined,
        purl: values.purl || undefined,
        language: values.language && values.language.length > 0 ? values.language : undefined,
        categories: values.categories && values.categories.length > 0 ? values.categories : undefined,
        description: values.description || undefined,
      };

      await libraryAPI.updateLibrary(libraryId, updateData);
      message.success('Library updated');
      setLibraryEditModalVisible(false);
      loadLibraryDetail();
    } catch (error: unknown) {
      const err = error as { response?: { data?: { detail?: string } } };
      message.error(err.response?.data?.detail || 'Failed to update library');
    }
  };

  const handleSubmitSourceCode = async (values: {
    commit_id: string;
    version_source?: string;
    semantic_version_str?: string;
    original_version_strs?: string;
    commit_datetime?: dayjs.Dayjs;
    tag_datetime?: dayjs.Dayjs;
  }) => {
    try {
      const originalVersions = values.original_version_strs
        ?.split(',')
        .map(s => s.trim())
        .filter(s => s);

      if (editingSourceCode) {
        const updateData: UpdateSourceCodeRequest = {
          commit_id: values.commit_id,
          version_source: values.version_source,
          semantic_version_str: values.semantic_version_str,
          original_version_strs: originalVersions,
          commit_datetime: values.commit_datetime?.toISOString(),
          tag_datetime: values.tag_datetime?.toISOString(),
        };
        await sourceCodeAPI.updateSourceCode(editingSourceCode.id, updateData);
        message.success('Source code updated');
      } else {
        const createData: CreateSourceCodeRequest = {
          library_id: libraryId,
          commit_id: values.commit_id,
          version_source: values.version_source,
          semantic_version_str: values.semantic_version_str,
          original_version_strs: originalVersions,
          commit_datetime: values.commit_datetime?.toISOString(),
          tag_datetime: values.tag_datetime?.toISOString(),
        };
        await sourceCodeAPI.createSourceCode(createData);
        message.success('Source code created');
      }
      setModalVisible(false);
      loadSourceCodes();
      loadLibraryStatus();
    } catch (error: unknown) {
      const err = error as { response?: { data?: { detail?: string } } };
      message.error(err.response?.data?.detail || 'Operation failed');
    }
  };

  const handleStringSearch = () => {
    setStringPage(1);
    loadStringFeatures();
  };

  const handleFuncSearch = () => {
    setFuncPage(1);
    loadFunctionNames();
  };

  // Table columns
  const sourceCodeColumns = [
    { title: 'ID', dataIndex: 'id', key: 'id', width: 60 },
    {
      title: 'Original Version',
      dataIndex: 'original_version_strs',
      key: 'original_version_strs',
      render: (strs: string[] | null) =>
        strs && strs.length > 0 ? strs.join(', ') : '-',
    },
    {
      title: 'Semantic Version',
      dataIndex: 'semantic_version_str',
      key: 'semantic_version_str',
      width: 130,
      render: (text: string | null) =>
        text ? <Tag color="blue">{text}</Tag> : '-',
    },
    {
      title: 'Commit ID',
      dataIndex: 'commit_id',
      key: 'commit_id',
      render: (text: string | null) => (
        <Text code style={{ fontSize: 12 }}>{text?.slice(0, 8) || '-'}</Text>
      ),
    },
    {
      title: 'Source',
      dataIndex: 'version_source',
      key: 'version_source',
      width: 100,
      render: (text: string | null) => text ? <Tag>{text}</Tag> : '-',
    },
    {
      title: 'Commit Date',
      dataIndex: 'commit_datetime',
      key: 'commit_datetime',
      width: 120,
      render: (text: string | null) => {
        if (!text) return '-';
        // Handle ISO format or other date formats
        try {
          const date = new Date(text);
          return date.toISOString().slice(0, 10);
        } catch {
          return text.slice(0, 10);
        }
      },
    },
    {
      title: 'Features',
      dataIndex: 'has_features',
      key: 'has_features',
      width: 90,
      render: (has: boolean) => has ? (
        <Tag color="green">✓ Yes</Tag>
      ) : (
        <Tag color="default">No</Tag>
      ),
    },
    {
      title: 'Actions',
      key: 'actions',
      width: 100,
      render: (_: unknown, record: SourceCode) => (
        <Space>
          <Button type="text" icon={<EditOutlined />} onClick={() => handleEditSourceCode(record)} />
          <Popconfirm
            title="Delete this source code?"
            onConfirm={() => handleDeleteSourceCode(record.id)}
            okText="Yes"
            cancelText="No"
          >
            <Button type="text" danger icon={<DeleteOutlined />} />
          </Popconfirm>
        </Space>
      ),
    },
  ];

  const vulnerabilityColumns = [
    {
      title: 'CVE ID',
      dataIndex: 'cve_id',
      key: 'cve_id',
      render: (text: string | null) => (
        <a href={`https://nvd.nist.gov/vuln/detail/${text}`} target="_blank" rel="noopener noreferrer">
          {text || '-'}
        </a>
      ),
    },
    {
      title: 'Severity',
      dataIndex: 'severity',
      key: 'severity',
      width: 100,
      render: (text: string | null) => {
        const colors: Record<string, string> = {
          critical: 'magenta',
          high: 'red',
          medium: 'orange',
          low: 'green',
        };
        return text ? <Tag color={colors[text.toLowerCase()] || 'default'}>{text.toUpperCase()}</Tag> : '-';
      },
    },
    {
      title: 'Description',
      dataIndex: 'description',
      key: 'description',
      ellipsis: true,
      render: (text: string | null) => (
        <Tooltip title={text}>
          <Paragraph ellipsis={{ rows: 2 }} style={{ margin: 0, maxWidth: 400 }}>
            {text || '-'}
          </Paragraph>
        </Tooltip>
      ),
    },
    {
      title: 'Published',
      dataIndex: 'published_date',
      key: 'published_date',
      width: 110,
      render: (text: string | null) => text?.slice(0, 10) || '-',
    },
    {
      title: 'Confirmed',
      dataIndex: 'confirmed',
      key: 'confirmed',
      width: 100,
      render: (val: boolean) => val ? <Tag color="green">Yes</Tag> : <Tag>No</Tag>,
    },
  ];

  const binaryColumns = [
    { title: 'ID', dataIndex: 'id', key: 'id', width: 60 },
    {
      title: 'Binary Name',
      dataIndex: 'binary_name',
      key: 'binary_name',
      render: (text: string | null) => text || '-',
    },
    {
      title: 'Architecture',
      dataIndex: 'architecture',
      key: 'architecture',
      width: 100,
      render: (text: string | null) => text ? <Tag>{text}</Tag> : '-',
    },
    {
      title: 'File Size',
      dataIndex: 'file_size',
      key: 'file_size',
      width: 100,
      render: (size: number | null) => {
        if (!size) return '-';
        if (size < 1024) return `${size} B`;
        if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`;
        return `${(size / (1024 * 1024)).toFixed(1)} MB`;
      },
    },
    {
      title: 'Hash',
      dataIndex: 'binary_hash',
      key: 'binary_hash',
      render: (text: string | null) => (
        <Text code style={{ fontSize: 11 }}>{text?.slice(0, 16) || '-'}...</Text>
      ),
    },
    {
      title: 'Confidence',
      dataIndex: 'confidence',
      key: 'confidence',
      width: 100,
      render: (val: number | null) => val !== null ? `${(val * 100).toFixed(1)}%` : '-',
    },
    {
      title: 'Detection',
      dataIndex: 'detection_method',
      key: 'detection_method',
      render: (text: string | null) => text ? <Tag color="blue">{text}</Tag> : '-',
    },
  ];

  const stringFeatureColumns = [
    { title: 'ID', dataIndex: 'id', key: 'id', width: 80 },
    {
      title: 'String Value',
      dataIndex: 'string_value',
      key: 'string_value',
      ellipsis: true,
      render: (text: string | null) => (
        <Tooltip title={text}>
          <Text code style={{ fontSize: 12 }}>{text || '-'}</Text>
        </Tooltip>
      ),
    },
    {
      title: 'Hash',
      dataIndex: 'string_hash',
      key: 'string_hash',
      width: 180,
      render: (text: string | null) => (
        <Text type="secondary" style={{ fontSize: 11 }}>{text?.slice(0, 16) || '-'}...</Text>
      ),
    },
    {
      title: 'Context',
      dataIndex: 'context',
      key: 'context',
      render: (text: string | null) => text || '-',
    },
  ];

  const functionNameColumns = [
    { title: 'ID', dataIndex: 'id', key: 'id', width: 80 },
    {
      title: 'Function Name',
      dataIndex: 'function_name',
      key: 'function_name',
      render: (text: string | null) => <Text code>{text || '-'}</Text>,
    },
    {
      title: 'Hash',
      dataIndex: 'function_hash',
      key: 'function_hash',
      width: 180,
      render: (text: string | null) => (
        <Text type="secondary" style={{ fontSize: 11 }}>{text?.slice(0, 16) || '-'}...</Text>
      ),
    },
    {
      title: 'Context',
      dataIndex: 'context',
      key: 'context',
      render: (text: string | null) => text || '-',
    },
  ];

  const licenseColumns = [
    { title: 'ID', dataIndex: 'id', key: 'id', width: 60 },
    {
      title: 'License Name',
      dataIndex: 'name',
      key: 'name',
      render: (text: string | null) => <Tag color="blue">{text || '-'}</Tag>,
    },
    {
      title: 'File Path',
      dataIndex: 'file_path',
      key: 'file_path',
      render: (text: string | null) => text ? <Text code>{text}</Text> : '-',
    },
    {
      title: 'Content',
      dataIndex: 'content',
      key: 'content',
      ellipsis: true,
      render: (text: string | null) => (
        <Tooltip title={text ? 'Click to view full content' : 'No content'}>
          <Paragraph ellipsis={{ rows: 2 }} style={{ margin: 0, maxWidth: 400 }}>
            {text?.slice(0, 200) || '-'}
          </Paragraph>
        </Tooltip>
      ),
    },
    {
      title: 'Hash',
      dataIndex: 'content_hash',
      key: 'content_hash',
      width: 150,
      render: (text: string | null) => (
        <Text type="secondary" style={{ fontSize: 11 }}>{text?.slice(0, 12) || '-'}...</Text>
      ),
    },
  ];

  if (loading) {
    return (
      <div style={{ textAlign: 'center', padding: 100 }}>
        <Spin size="large" />
      </div>
    );
  }

  if (!library) {
    return <div>Library not found</div>;
  }

  const StatusIcon = ({ value }: { value: boolean }) =>
    value ? (
      <CheckCircleOutlined style={{ color: '#52c41a' }} />
    ) : (
      <CloseCircleOutlined style={{ color: '#ff4d4f' }} />
    );

  return (
    <div>
      {/* Header */}
      <Space style={{ marginBottom: 24 }}>
        <Button icon={<ArrowLeftOutlined />} onClick={() => navigate('/libraries')}>
          Back
        </Button>
        <Title level={4} style={{ margin: 0 }}>{library.name}</Title>
        {library.vendor && <Tag color="blue">{library.vendor}</Tag>}
      </Space>

      <Row gutter={[16, 16]}>
        {/* Library Info */}
        <Col xs={24} lg={16}>
          <Card
            title="Library Information"
            extra={
              <Button icon={<EditOutlined />} onClick={handleEditLibrary}>
                Edit
              </Button>
            }
          >
            <Descriptions column={{ xs: 1, sm: 2 }}>
              <Descriptions.Item label="ID">{library.id}</Descriptions.Item>
              <Descriptions.Item label="Name">{library.name}</Descriptions.Item>
              <Descriptions.Item label="Vendor">{library.vendor || '-'}</Descriptions.Item>
              <Descriptions.Item label="Alias">{library.alias || '-'}</Descriptions.Item>
              <Descriptions.Item label="Source">
                <Space wrap>
                  {library.source?.map((s, i) => <Tag key={i} color="blue">{s}</Tag>)}
                </Space>
              </Descriptions.Item>
              <Descriptions.Item label="Homepage">
                {library.homepage ? (
                  <a href={library.homepage} target="_blank" rel="noopener noreferrer">
                    {library.homepage}
                  </a>
                ) : '-'}
              </Descriptions.Item>
              <Descriptions.Item label="Git URL">
                {library.giturl ? (
                  <a href={library.giturl} target="_blank" rel="noopener noreferrer">
                    {library.giturl}
                  </a>
                ) : '-'}
              </Descriptions.Item>
              <Descriptions.Item label="PURL">
                {library.purl ? <Text code style={{ fontSize: 12 }}>{library.purl}</Text> : '-'}
              </Descriptions.Item>
              <Descriptions.Item label="Language">
                {library.language && library.language.length > 0 ? (
                  <Space wrap>
                    {library.language.map((lang, i) => <Tag key={i} color="green">{lang}</Tag>)}
                  </Space>
                ) : '-'}
              </Descriptions.Item>
              <Descriptions.Item label="Categories">
                {library.categories && library.categories.length > 0 ? (
                  <Space wrap>
                    {library.categories.map((cat, i) => <Tag key={i} color="purple">{cat}</Tag>)}
                  </Space>
                ) : '-'}
              </Descriptions.Item>
              <Descriptions.Item label="Created">
                {library.created_at?.slice(0, 19).replace('T', ' ') || '-'}
              </Descriptions.Item>
              <Descriptions.Item label="Description" span={2}>
                {library.description || '-'}
              </Descriptions.Item>
            </Descriptions>
          </Card>
        </Col>

        {/* Status Card */}
        <Col xs={24} lg={8}>
          <Card
            title="Library Status"
            extra={
              <Button
                icon={<ReloadOutlined spin={refreshing} />}
                onClick={handleRefreshStatus}
                loading={refreshing}
              >
                Refresh
              </Button>
            }
          >
            {status ? (
              <Space direction="vertical" style={{ width: '100%' }}>
                <Row gutter={[8, 8]}>
                  <Col span={12}>
                    <Statistic title="Source Codes" value={status.source_code_count} />
                  </Col>
                  <Col span={12}>
                    <Statistic title="Vulnerabilities" value={status.vulnerability_count} />
                  </Col>
                  <Col span={12}>
                    <Statistic title="String Features" value={status.string_feature_count} />
                  </Col>
                  <Col span={12}>
                    <Statistic title="Function Names" value={status.function_name_feature_count} />
                  </Col>
                  <Col span={12}>
                    <Statistic title="Binaries" value={status.binary_count} />
                  </Col>
                </Row>
                <div style={{ marginTop: 16 }}>
                  <Space wrap>
                    <span><StatusIcon value={status.has_basic_info} /> Basic Info</span>
                    <span><StatusIcon value={status.has_features} /> Features</span>
                    <span><StatusIcon value={status.has_binaries} /> Binaries</span>
                    <span><StatusIcon value={status.has_vulnerabilities} /> Vulns</span>
                  </Space>
                </div>
              </Space>
            ) : (
              <Text type="secondary">No status data. Click Refresh to generate.</Text>
            )}
          </Card>
        </Col>
      </Row>

      {/* Tabs for related data */}
      <Card style={{ marginTop: 16 }}>
        <Tabs
          activeKey={activeTab}
          onChange={setActiveTab}
          items={[
            {
              key: 'source_codes',
              label: (
                <span>
                  <CodeOutlined />
                  Source Codes
                  {status && <Badge count={status.source_code_count} style={{ marginLeft: 8 }} showZero overflowCount={999} />}
                </span>
              ),
              children: (
                <>
                  <div style={{ marginBottom: 16 }}>
                    <Button type="primary" icon={<PlusOutlined />} onClick={handleCreateSourceCode}>
                      Add Source Code
                    </Button>
                  </div>
                  <Table
                    columns={sourceCodeColumns}
                    dataSource={sourceCodes}
                    rowKey="id"
                    loading={sourceCodeLoading}
                    pagination={{
                      current: sourceCodePage,
                      pageSize: sourceCodePageSize,
                      total: sourceCodeTotal,
                      showSizeChanger: true,
                      showTotal: (total) => `Total ${total} source codes`,
                      onChange: (p, ps) => {
                        setSourceCodePage(p);
                        setSourceCodePageSize(ps);
                      },
                    }}
                  />
                </>
              ),
            },
            {
              key: 'vulnerabilities',
              label: (
                <span>
                  <BugOutlined />
                  Vulnerabilities
                  {status && status.vulnerability_count > 0 && (
                    <Badge count={status.vulnerability_count} style={{ marginLeft: 8 }} overflowCount={999} />
                  )}
                </span>
              ),
              children: vulnTotal === 0 && !vulnLoading ? (
                <Empty description="No vulnerabilities found" image={Empty.PRESENTED_IMAGE_SIMPLE} />
              ) : (
                <Table
                  columns={vulnerabilityColumns}
                  dataSource={vulnerabilities}
                  rowKey="id"
                  loading={vulnLoading}
                  pagination={{
                    current: vulnPage,
                    pageSize: vulnPageSize,
                    total: vulnTotal,
                    showSizeChanger: true,
                    showTotal: (total) => `Total ${total} vulnerabilities`,
                    onChange: (p, ps) => {
                      setVulnPage(p);
                      setVulnPageSize(ps);
                    },
                  }}
                />
              ),
            },
            {
              key: 'binaries',
              label: (
                <span>
                  <FileOutlined />
                  Binaries
                  {status && status.binary_count > 0 && (
                    <Badge count={status.binary_count} style={{ marginLeft: 8 }} overflowCount={999} />
                  )}
                </span>
              ),
              children: binaryTotal === 0 && !binaryLoading ? (
                <Empty description="No binaries found" image={Empty.PRESENTED_IMAGE_SIMPLE} />
              ) : (
                <Table
                  columns={binaryColumns}
                  dataSource={binaries}
                  rowKey="id"
                  loading={binaryLoading}
                  pagination={{
                    current: binaryPage,
                    pageSize: binaryPageSize,
                    total: binaryTotal,
                    showSizeChanger: true,
                    showTotal: (total) => `Total ${total} binaries`,
                    onChange: (p, ps) => {
                      setBinaryPage(p);
                      setBinaryPageSize(ps);
                    },
                  }}
                />
              ),
            },
            {
              key: 'strings',
              label: (
                <span>
                  <WarningOutlined />
                  Strings
                  {status && status.string_feature_count > 0 && (
                    <Badge count={status.string_feature_count} style={{ marginLeft: 8 }} overflowCount={9999} />
                  )}
                </span>
              ),
              children: (
                <>
                  <div style={{ marginBottom: 16 }}>
                    <Space>
                      <Input
                        placeholder="Search strings..."
                        value={stringSearch}
                        onChange={(e) => setStringSearch(e.target.value)}
                        onPressEnter={handleStringSearch}
                        style={{ width: 300 }}
                        allowClear
                      />
                      <Button icon={<SearchOutlined />} onClick={handleStringSearch}>
                        Search
                      </Button>
                    </Space>
                  </div>
                  {stringTotal === 0 && !stringLoading ? (
                    <Empty description="No string features found" image={Empty.PRESENTED_IMAGE_SIMPLE} />
                  ) : (
                    <Table
                      columns={stringFeatureColumns}
                      dataSource={stringFeatures}
                      rowKey="id"
                      loading={stringLoading}
                      pagination={{
                        current: stringPage,
                        pageSize: stringPageSize,
                        total: stringTotal,
                        showSizeChanger: true,
                        pageSizeOptions: ['20', '50', '100'],
                        showTotal: (total) => `Total ${total} strings`,
                        onChange: (p, ps) => {
                          setStringPage(p);
                          setStringPageSize(ps);
                        },
                      }}
                    />
                  )}
                </>
              ),
            },
            {
              key: 'functions',
              label: (
                <span>
                  <CodeOutlined />
                  Functions
                  {status && status.function_name_feature_count > 0 && (
                    <Badge count={status.function_name_feature_count} style={{ marginLeft: 8 }} overflowCount={9999} />
                  )}
                </span>
              ),
              children: (
                <>
                  <div style={{ marginBottom: 16 }}>
                    <Space>
                      <Input
                        placeholder="Search function names..."
                        value={funcSearch}
                        onChange={(e) => setFuncSearch(e.target.value)}
                        onPressEnter={handleFuncSearch}
                        style={{ width: 300 }}
                        allowClear
                      />
                      <Button icon={<SearchOutlined />} onClick={handleFuncSearch}>
                        Search
                      </Button>
                    </Space>
                  </div>
                  {funcTotal === 0 && !funcLoading ? (
                    <Empty description="No function names found" image={Empty.PRESENTED_IMAGE_SIMPLE} />
                  ) : (
                    <Table
                      columns={functionNameColumns}
                      dataSource={functionNames}
                      rowKey="id"
                      loading={funcLoading}
                      pagination={{
                        current: funcPage,
                        pageSize: funcPageSize,
                        total: funcTotal,
                        showSizeChanger: true,
                        pageSizeOptions: ['20', '50', '100'],
                        showTotal: (total) => `Total ${total} functions`,
                        onChange: (p, ps) => {
                          setFuncPage(p);
                          setFuncPageSize(ps);
                        },
                      }}
                    />
                  )}
                </>
              ),
            },
            {
              key: 'licenses',
              label: (
                <span>
                  <SafetyCertificateOutlined />
                  Licenses
                  {licenseTotal > 0 && (
                    <Badge count={licenseTotal} style={{ marginLeft: 8 }} overflowCount={99} />
                  )}
                </span>
              ),
              children: licenseTotal === 0 && !licenseLoading ? (
                <Empty description="No licenses found" image={Empty.PRESENTED_IMAGE_SIMPLE} />
              ) : (
                <Table
                  columns={licenseColumns}
                  dataSource={licenses}
                  rowKey="id"
                  loading={licenseLoading}
                  pagination={{
                    current: licensePage,
                    pageSize: licensePageSize,
                    total: licenseTotal,
                    showSizeChanger: true,
                    showTotal: (total) => `Total ${total} licenses`,
                    onChange: (p, ps) => {
                      setLicensePage(p);
                      setLicensePageSize(ps);
                    },
                  }}
                />
              ),
            },
          ]}
        />
      </Card>

      {/* Source Code Modal */}
      <Modal
        title={editingSourceCode ? 'Edit Source Code' : 'Add Source Code'}
        open={modalVisible}
        onCancel={() => setModalVisible(false)}
        footer={null}
        width={600}
      >
        <Form form={form} layout="vertical" onFinish={handleSubmitSourceCode}>
          <Form.Item
            name="commit_id"
            label="Commit ID"
            rules={[{ required: true, message: 'Please enter commit ID' }]}
          >
            <Input placeholder="e.g., abc123..." maxLength={40} />
          </Form.Item>
          <Form.Item name="semantic_version_str" label="Semantic Version">
            <Input placeholder="e.g., 1.2.3" />
          </Form.Item>
          <Form.Item name="version_source" label="Version Source">
            <Input placeholder="e.g., git_tag, github_release" />
          </Form.Item>
          <Form.Item name="original_version_strs" label="Original Versions (comma separated)">
            <Input placeholder="e.g., v1.2.3, release-1.2.3" />
          </Form.Item>
          <Form.Item name="commit_datetime" label="Commit Date">
            <DatePicker showTime style={{ width: '100%' }} />
          </Form.Item>
          <Form.Item name="tag_datetime" label="Tag Date">
            <DatePicker showTime style={{ width: '100%' }} />
          </Form.Item>
          <Form.Item>
            <Space>
              <Button type="primary" htmlType="submit">
                {editingSourceCode ? 'Update' : 'Create'}
              </Button>
              <Button onClick={() => setModalVisible(false)}>Cancel</Button>
            </Space>
          </Form.Item>
        </Form>
      </Modal>

      {/* Library Edit Modal */}
      <Modal
        title="Edit Library"
        open={libraryEditModalVisible}
        onCancel={() => setLibraryEditModalVisible(false)}
        footer={null}
        width={700}
      >
        <Form form={libraryForm} layout="vertical" onFinish={handleSubmitLibrary}>
          <Row gutter={16}>
            <Col span={12}>
              <Form.Item
                name="name"
                label="Name"
                rules={[{ required: true, message: 'Please enter library name' }]}
              >
                <Input placeholder="Library name" />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item name="vendor" label="Vendor">
                <Input placeholder="Vendor name" />
              </Form.Item>
            </Col>
          </Row>
          <Row gutter={16}>
            <Col span={12}>
              <Form.Item name="alias" label="Alias">
                <Input placeholder="Library alias" />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item
                name="source"
                label="Source (comma separated)"
                rules={[{ required: true, message: 'Please enter at least one source' }]}
              >
                <Input placeholder="e.g., github, gitlab" />
              </Form.Item>
            </Col>
          </Row>
          <Row gutter={16}>
            <Col span={12}>
              <Form.Item name="homepage" label="Homepage">
                <Input placeholder="https://..." />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item name="giturl" label="Git URL">
                <Input placeholder="https://github.com/..." />
              </Form.Item>
            </Col>
          </Row>
          <Row gutter={16}>
            <Col span={12}>
              <Form.Item name="purl" label="PURL (Package URL)">
                <Input placeholder="pkg:type/namespace/name@version" />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item name="language" label="Language">
                <Select
                  mode="tags"
                  placeholder="Select or enter languages"
                  options={[
                    { value: 'C', label: 'C' },
                    { value: 'C++', label: 'C++' },
                    { value: 'Java', label: 'Java' },
                    { value: 'Python', label: 'Python' },
                    { value: 'JavaScript', label: 'JavaScript' },
                    { value: 'TypeScript', label: 'TypeScript' },
                    { value: 'Go', label: 'Go' },
                    { value: 'Rust', label: 'Rust' },
                    { value: 'Assembly', label: 'Assembly' },
                  ]}
                />
              </Form.Item>
            </Col>
          </Row>
          <Form.Item name="categories" label="Categories">
            <Select
              mode="tags"
              placeholder="Select or enter categories"
              options={[
                { value: 'crypto', label: 'Crypto' },
                { value: 'network', label: 'Network' },
                { value: 'compression', label: 'Compression' },
                { value: 'database', label: 'Database' },
                { value: 'parser', label: 'Parser' },
                { value: 'image', label: 'Image' },
                { value: 'audio', label: 'Audio' },
                { value: 'video', label: 'Video' },
                { value: 'ui', label: 'UI' },
                { value: 'utility', label: 'Utility' },
              ]}
            />
          </Form.Item>
          <Form.Item name="description" label="Description">
            <Input.TextArea rows={3} placeholder="Library description" />
          </Form.Item>
          <Form.Item>
            <Space>
              <Button type="primary" htmlType="submit">Update</Button>
              <Button onClick={() => setLibraryEditModalVisible(false)}>Cancel</Button>
            </Space>
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
};

export default LibraryDetail;
