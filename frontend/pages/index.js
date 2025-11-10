import { useMemo } from 'react';
import { useTranslation } from 'react-i18next';
import MainLayout from '@components/layout/MainLayout';
import Sidebar from '@components/layout/Sidebar';
import Topbar from '@components/layout/Topbar';
import EmptyState from '@components/common/EmptyState';
import ChatPanel from '@modules/chat/ChatPanel';
import SavedTripsPanel from '@modules/saved/SavedTripsPanel';
import OverviewPanel from '@modules/dashboard/OverviewPanel';
import { usePlanner } from '@lib/hooks/usePlanner';
import AuthPrompt from '@components/auth/AuthPrompt';
import { useAuth } from '@lib/hooks/useAuth';

function HomePage() {
  const { t } = useTranslation();
  const {
    state: { sidebarGroups, activeSection },
    setActiveSection,
  } = usePlanner();
  const {
    state: { isAuthenticated },
  } = useAuth();

  const content = useMemo(() => {
    if (!isAuthenticated) {
      return <AuthPrompt />;
    }

    switch (activeSection) {
      case 'ai-planner':
        return <ChatPanel />;
      case 'saved-trips':
        return <SavedTripsPanel />;
      case 'dashboard':
        return <OverviewPanel />;
      default:
        return (
          <EmptyState
            title={t('emptyState.buildingTitle')}
            description={t('emptyState.buildingDescription')}
            actionText={t('emptyState.buildingAction')}
            onAction={() => setActiveSection('ai-planner')}
          />
        );
    }
  }, [activeSection, isAuthenticated, setActiveSection, t]);

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
