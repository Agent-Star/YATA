import { useMemo } from 'react';
import { Card, Button, Typography } from '@douyinfe/semi-ui';
import { IconLikeHeart } from '@douyinfe/semi-icons';
import ReactMarkdown from 'react-markdown';
import { useTranslation } from 'react-i18next';
import EmptyState from '@components/common/EmptyState';
import { usePlanner } from '@lib/hooks/usePlanner';

function SavedTripsPanel() {
  const { t } = useTranslation();
  const {
    state: { favorites },
    removeFavorite,
    setActiveSection,
  } = usePlanner();

  const sortedFavorites = useMemo(
    () => [...favorites].sort((a, b) => (b.savedAt || 0) - (a.savedAt || 0)),
    [favorites]
  );

  if (!favorites.length) {
    return (
      <EmptyState
        title={t('chat.favoritesEmptyTitle')}
        description={t('chat.favoritesEmptyDescription')}
        actionText={t('chat.favoritesBackToChat')}
        onAction={() => setActiveSection('ai-planner')}
      />
    );
  }

  return (
    <div className="saved-trips">
      <div className="saved-trips__header">
        <Typography.Title heading={3}>{t('chat.favoritesTitle')}</Typography.Title>
        <Typography.Text type="tertiary">
          {t('chat.favoritesDescription')}
        </Typography.Text>
      </div>
      <div className="saved-trips__list">
        {sortedFavorites.map((favorite) => (
          <Card key={favorite.id} className="saved-trip-card" bordered>
            <div className="saved-trip-card__meta">
              <Typography.Text strong>
                {favorite.role === 'user' ? t('chat.you') : t('chat.assistant')}
              </Typography.Text>
              <Typography.Text type="tertiary">
                {favorite.savedAt
                  ? new Date(favorite.savedAt).toLocaleString()
                  : ''}
              </Typography.Text>
            </div>
            <div className="saved-trip-card__content">
              <ReactMarkdown>{favorite.content}</ReactMarkdown>
            </div>
            <div className="saved-trip-card__actions">
              <Button
                icon={<IconLikeHeart />}
                type="tertiary"
                theme="borderless"
                onClick={() => removeFavorite(favorite.messageId)}
              >
                {t('chat.removeFromFavorites')}
              </Button>
            </div>
          </Card>
        ))}
      </div>
    </div>
  );
}

export default SavedTripsPanel;
