/**
 * Ant Design Vue Plugin Configuration
 *
 * Only includes components needed for data management pages
 * to minimize bundle size.
 */
import {
  // Layout
  Layout,
  Row,
  Col,
  Space,
  Divider,

  // Data Display
  Table,
  Card,
  Statistic,
  Descriptions,
  Tag,
  Typography,
  Empty,
  Avatar,

  // Data Entry
  Form,
  Input,
  Select,
  Button,

  // Feedback
  Modal,
  message,
  Popconfirm,
  Spin,

  // Navigation
  Tabs,
  PageHeader,
  Breadcrumb,
  Dropdown,
  Menu
} from 'ant-design-vue'

export default {
  install(app) {
    // Layout
    app.use(Layout)
    app.use(Row)
    app.use(Col)
    app.use(Space)
    app.use(Divider)

    // Data Display
    app.use(Table)
    app.use(Card)
    app.use(Statistic)
    app.use(Descriptions)
    app.use(Tag)
    app.use(Typography)
    app.use(Empty)
    app.use(Avatar)

    // Data Entry
    app.use(Form)
    app.use(Input)
    app.use(Select)
    app.use(Button)

    // Feedback
    app.use(Modal)
    app.use(Popconfirm)
    app.use(Spin)

    // Navigation
    app.use(Tabs)
    app.use(PageHeader)
    app.use(Breadcrumb)
    app.use(Dropdown)
    app.use(Menu)

    // Global methods
    app.config.globalProperties.$message = message
  }
}
