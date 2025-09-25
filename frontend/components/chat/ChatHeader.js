import { Typography } from '@douyinfe/semi-ui';
import { useTranslation } from 'react-i18next';

function ChatHeader() {
  const { t } = useTranslation();

  return (
    <div className="chat-header">
      <Typography.Title heading={2}>{t('chat.headerTitle')}</Typography.Title>
      <Typography.Text type="tertiary">
        {t('chat.headerSubtitle')}
      </Typography.Text>
    </div>
  );
}

export default ChatHeader;
