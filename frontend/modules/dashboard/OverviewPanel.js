import { Card, Tag, Typography, Divider } from '@douyinfe/semi-ui';
import {
  IconHistogram,
  IconFlag,
  IconMapPin,
  IconCalendar,
  IconStar,
} from '@douyinfe/semi-icons';
import { useTranslation } from 'react-i18next';

const overviewStats = [
  {
    icon: <IconHistogram />,
    key: 'totalTrips',
    value: '48',
    descriptionKey: 'dashboard.totalTrips',
  },
  {
    icon: <IconFlag />,
    key: 'countries',
    value: '12',
    descriptionKey: 'dashboard.countriesExplored',
  },
  {
    icon: <IconCalendar />,
    key: 'avgLength',
    value: '5.6',
    descriptionKey: 'dashboard.avgDays',
    unit: 'dashboard.daysUnit',
  },
];

const countryStats = [
  { flag: '🇯🇵', name: 'Japan', visits: 8 },
  { flag: '🇹🇭', name: 'Thailand', visits: 5 },
  { flag: '🇫🇷', name: 'France', visits: 4 },
  { flag: '🇨🇳', name: 'China', visits: 3 },
];

const cityStats = [
  { flag: '🇯🇵', icon: <IconMapPin />, name: 'Kyoto', country: 'Japan', visits: 3 },
  { flag: '🇫🇷', icon: <IconMapPin />, name: 'Paris', country: 'France', visits: 2 },
  { flag: '🇺🇸', icon: <IconMapPin />, name: 'Seattle', country: 'USA', visits: 2 },
  { flag: '🇵🇹', icon: <IconMapPin />, name: 'Lisbon', country: 'Portugal', visits: 1 },
];

const itineraryTimeline = [
  { year: 2024, title: '春季日本文化游', description: '东京 - 京都 - 奈良，5 天亲子行程' },
  { year: 2023, title: '地中海慢享假期', description: '法国尼斯 + 意大利佛罗伦萨，7 天浪漫之旅' },
  { year: 2022, title: '美国西海岸自驾', description: '旧金山 - 洛杉矶 - 拉斯维加斯，8 天自驾体验' },
];

function OverviewPanel() {
  const { t } = useTranslation();

  return (
    <div className="overview-panel">
      <div className="overview-panel__header">
        <div>
          <Typography.Title heading={2}>
            <IconHistogram style={{ marginRight: 12 }} />
            {t('dashboard.title')}
          </Typography.Title>
          <Typography.Text type="tertiary">
            {t('dashboard.subtitle')}
          </Typography.Text>
        </div>
        <Tag type="solid" color="purple">
          {t('dashboard.updatedAt', { date: '2025-01-04' })}
        </Tag>
      </div>

      <div className="overview-panel__stats">
        {overviewStats.map((stat) => (
          <Card key={stat.key} className="overview-panel__stat-card">
            <div className="overview-panel__stat-icon">{stat.icon}</div>
            <div>
              <Typography.Title heading={3} style={{ marginBottom: 4 }}>
                {stat.value}
                {stat.unit ? <small className="overview-panel__stat-unit">{t(stat.unit)}</small> : null}
              </Typography.Title>
              <Typography.Text type="tertiary">{t(stat.descriptionKey)}</Typography.Text>
            </div>
          </Card>
        ))}
      </div>

      <Divider margin="24px 0" />

      <section className="overview-panel__section">
        <div className="overview-panel__section-header">
          <Typography.Title heading={4}>{t('dashboard.countriesTitle')}</Typography.Title>
          <Typography.Text type="tertiary">{t('dashboard.countriesSubtitle')}</Typography.Text>
        </div>
        <div className="overview-panel__grid">
          {countryStats.map((country) => (
            <Card key={country.name} className="overview-panel__mini-card">
              <div className="overview-panel__mini-flag">{country.flag}</div>
              <Typography.Text strong>{country.name}</Typography.Text>
              <div> </div>
              <Typography.Text type="tertiary" size="small">
                {t('dashboard.visitsCount', { count: country.visits })}
              </Typography.Text>
            </Card>
          ))}
        </div>
      </section>

      <section className="overview-panel__section">
        <div className="overview-panel__section-header">
          <Typography.Title heading={4}>{t('dashboard.citiesTitle')}</Typography.Title>
          <Typography.Text type="tertiary">{t('dashboard.citiesSubtitle')}</Typography.Text>
        </div>
        <div className="overview-panel__grid">
          {cityStats.map((city) => (
            <Card key={city.name} className="overview-panel__city-card">
              <div className="overview-panel__city-icon">{city.icon}</div>
              <div className="overview-panel__city-info">
                <Typography.Text strong>
                  {city.flag} {city.name}
                </Typography.Text>
                <Typography.Text type="tertiary" size="small">
                  {city.country}
                </Typography.Text>
              </div>
              <Tag size="small" theme="light">
                {t('dashboard.visitsCount', { count: city.visits })}
              </Tag>
            </Card>
          ))}
        </div>
      </section>

      <section className="overview-panel__section">
        <div className="overview-panel__section-header">
          <Typography.Title heading={4}>{t('dashboard.timelineTitle')}</Typography.Title>
          <Typography.Text type="tertiary">{t('dashboard.timelineSubtitle')}</Typography.Text>
        </div>
        <div className="overview-panel__timeline">
          {itineraryTimeline.map((trip) => (
            <Card key={trip.year} className="overview-panel__timeline-card">
              <div className="overview-panel__timeline-year">
                <IconStar />
                <Typography.Title heading={4}>{trip.year}</Typography.Title>
              </div>
              <Typography.Text strong>{trip.title}</Typography.Text>
              <Typography.Paragraph type="tertiary">
                {trip.description}
              </Typography.Paragraph>
            </Card>
          ))}
        </div>
      </section>
    </div>
  );
}

export default OverviewPanel;
