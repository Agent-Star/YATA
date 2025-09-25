import { Button, Space, Typography } from '@douyinfe/semi-ui';
import { useTranslation } from 'react-i18next';

function QuickActionList({ actions, onSelect }) {
  const { t } = useTranslation();

  if (!actions || actions.length === 0) {
    return null;
  }

  return (
    <div className="quick-actions">
      <Typography.Text type="tertiary">{t('quickActions.title')}</Typography.Text>
      <Space wrap spacing={12} style={{ marginTop: 12 }}>
        {actions.map((action) => (
          <Button
            key={action.key}
            theme="light"
            onClick={() => onSelect(action)}
          >
            {t(action.labelKey)}
          </Button>
        ))}
      </Space>
    </div>
  );
}

export default QuickActionList;
