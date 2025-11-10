export const sidebarGroups = [
  {
    key: 'workspace',
    titleKey: 'sidebar.workspace',
    items: [
      { key: 'dashboard', labelKey: 'sidebar.overview', icon: 'IconHome' },
      { key: 'ai-planner', labelKey: 'sidebar.aiPlanner', icon: 'IconSend' },
      { key: 'saved-trips', labelKey: 'sidebar.savedTrips', icon: 'IconBookmark' },
    ],
  },
  {
    key: 'collections',
    titleKey: 'sidebar.collections',
    items: [
      { key: 'inspiration', labelKey: 'sidebar.inspiration', icon: 'IconImage' },
      { key: 'guides', labelKey: 'sidebar.guides', icon: 'IconMapPin' },
    ],
  },
];
