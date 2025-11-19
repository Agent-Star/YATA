import { Card, Typography, Button, Tag } from '@douyinfe/semi-ui';
import { IconMapPin, IconBookmark } from '@douyinfe/semi-icons';
import { useTranslation } from 'react-i18next';

const guides = [
  {
    id: 'kyoto',
    city: 'Kyoto',
    country: 'Japan',
    summaryKey: 'guides.kyoto.summary',
    highlightsKey: 'guides.kyoto.highlights',
    tags: ['Heritage', 'Family'],
  },
  {
    id: 'lisbon',
    city: 'Lisbon',
    country: 'Portugal',
    summaryKey: 'guides.lisbon.summary',
    highlightsKey: 'guides.lisbon.highlights',
    tags: ['Food', 'Design'],
  },
  {
    id: 'seattle',
    city: 'Seattle',
    country: 'USA',
    summaryKey: 'guides.seattle.summary',
    highlightsKey: 'guides.seattle.highlights',
    tags: ['Outdoors', 'Coffee'],
  },
];

function CityGuidePanel({ onPlanCity }) {
  const { t } = useTranslation();

  const handlePlan = (guide) => {
    if (onPlanCity) {
      onPlanCity(`${guide.city} ${t(guide.summaryKey)}`);
    }
  };

  return (
    <div className="guides-panel">
      <div className="guides-panel__header">
        <div>
          <Typography.Title heading={3}>
            <IconMapPin style={{ marginRight: 12 }} />
            {t('guides.title')}
          </Typography.Title>
          <Typography.Text type="tertiary">{t('guides.subtitle')}</Typography.Text>
        </div>
      </div>
      <div className="guides-panel__list">
        {guides.map((guide) => (
          <Card key={guide.id} className="guide-card">
            <div className="guide-card__header">
              <div>
                <Typography.Title heading={4}>{guide.city}</Typography.Title>
                <Typography.Text type="tertiary">{guide.country}</Typography.Text>
              </div>
              <IconBookmark className="guide-card__bookmark" />
            </div>
            <Typography.Paragraph>{t(guide.summaryKey)}</Typography.Paragraph>
            <Typography.Text type="tertiary">{t(guide.highlightsKey)}</Typography.Text>
            <div className="guide-card__footer">
              <div className="guide-card__tags">
                {guide.tags.map((tag) => (
                  <Tag key={tag} size="small">
                    {tag}
                  </Tag>
                ))}
              </div>
              <Button theme="solid" onClick={() => handlePlan(guide)}>
                {t('guides.planAction')}
              </Button>
            </div>
          </Card>
        ))}
      </div>
    </div>
  );
}

CityGuidePanel.defaultProps = {
  onPlanCity: null,
};

export default CityGuidePanel;
