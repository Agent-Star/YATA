import { Card, Typography, Tag, Button } from '@douyinfe/semi-ui';
import { IconImage, IconSun, IconHelm, IconGlobe, IconSend } from '@douyinfe/semi-icons';
import { useTranslation } from 'react-i18next';

const inspirationData = [
  {
    id: 'sunny-coast',
    titleKey: 'inspiration.sunnyCoast.title',
    descriptionKey: 'inspiration.sunnyCoast.description',
    tags: ['Beach', 'Relax'],
    accent: 'orange',
  },
  {
    id: 'mountain-retreat',
    titleKey: 'inspiration.mountainRetreat.title',
    descriptionKey: 'inspiration.mountainRetreat.description',
    tags: ['Nature', 'Family'],
    accent: 'green',
  },
  {
    id: 'city-weekend',
    titleKey: 'inspiration.cityWeekend.title',
    descriptionKey: 'inspiration.cityWeekend.description',
    tags: ['Art', 'Food'],
    accent: 'purple',
  },
];

function TravelInspirationPanel({ onTryPrompt }) {
  const { t } = useTranslation();

  const handleTry = (titleKey) => {
    if (onTryPrompt) {
      onTryPrompt(t(titleKey));
    }
  };

  return (
    <div className="inspiration-panel">
      <div className="inspiration-panel__header">
        <div>
          <Typography.Title heading={3}>
            <IconImage style={{ marginRight: 12 }} />
            {t('inspiration.title')}
          </Typography.Title>
          <Typography.Text type="tertiary">{t('inspiration.subtitle')}</Typography.Text>
        </div>
      </div>

      <div className="inspiration-panel__grid">
        {inspirationData.map((card) => (
          <Card key={card.id} className={`inspiration-card inspiration-card--${card.accent}`}>
            <div className="inspiration-card__icon">
              {card.accent === 'orange' ? (
                <IconSun />
              ) : card.accent === 'green' ? (
                <IconHelm />
              ) : (
                <IconGlobe />
              )}
            </div>
            <Typography.Title heading={4}>{t(card.titleKey)}</Typography.Title>
            <Typography.Paragraph type="tertiary">
              {t(card.descriptionKey)}
            </Typography.Paragraph>
            <div className="inspiration-card__tags">
              {card.tags.map((tag) => (
                <Tag key={tag} type="ghost" color="grey">
                  {tag}
                </Tag>
              ))}
            </div>
            <Button
              theme="solid"
              icon={<IconSend />}
              onClick={() => handleTry(card.titleKey)}
            >
              {t('inspiration.tryPrompt')}
            </Button>
          </Card>
        ))}
      </div>
    </div>
  );
}

TravelInspirationPanel.defaultProps = {
  onTryPrompt: null,
};

export default TravelInspirationPanel;
