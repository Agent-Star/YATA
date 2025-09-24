import { useMemo } from 'react';
import MainLayout from '@components/layout/MainLayout';
import Sidebar from '@components/layout/Sidebar';
import Topbar from '@components/layout/Topbar';
import EmptyState from '@components/common/EmptyState';
import ChatPanel from '@modules/chat/ChatPanel';
import { usePlanner } from '@lib/hooks/usePlanner';

function HomePage() {
  const {
    state: { sidebarGroups, activeSection },
    setActiveSection,
  } = usePlanner();

  const content = useMemo(() => {
    switch (activeSection) {
      case 'ai-planner':
        return <ChatPanel />;
      case 'dashboard':
        return (
          <EmptyState
            title="旅行数据总览即将到来"
            description="在这里你可以查看旅行灵感、收藏和出行安排。"
            actionText="返回AI规划"
            onAction={() => setActiveSection('ai-planner')}
          />
        );
      default:
        return (
          <EmptyState
            title="功能建设中"
            description="我们正在为这个栏目构建体验，先尝试使用AI旅行规划吧。"
            actionText="打开AI旅行助手"
            onAction={() => setActiveSection('ai-planner')}
          />
        );
    }
  }, [activeSection, setActiveSection]);

  return (
    <MainLayout
      sidebar={
        <Sidebar
          groups={sidebarGroups}
          activeKey={activeSection}
          onSelect={setActiveSection}
        />
      }
      topbar={<Topbar />}
    >
      {content}
    </MainLayout>
  );
}

export default HomePage;
