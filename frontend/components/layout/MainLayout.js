import { Layout } from '@douyinfe/semi-ui';

function MainLayout({ sidebar, children, topbar }) {
  return (
    <Layout className="app-layout">
      <Layout.Sider className="app-sidebar" width={260} collapsible={false}>
        {sidebar}
      </Layout.Sider>
      <Layout className="app-main">
        {topbar ? <Layout.Header className="app-topbar">{topbar}</Layout.Header> : null}
        <Layout.Content className="app-content">{children}</Layout.Content>
      </Layout>
    </Layout>
  );
}

export default MainLayout;
