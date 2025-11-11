import i18n from 'i18next';
import { initReactI18next } from 'react-i18next';
import resources from './resources';

export const defaultLanguage = 'zh';
export const fallbackLanguage = 'en';

export const supportedLanguages = [
  { key: 'zh', label: '中文' },
  { key: 'en', label: 'English' },
];

if (!i18n.isInitialized) {
  i18n.use(initReactI18next).init({
    resources,
    lng: defaultLanguage,
    fallbackLng: fallbackLanguage,
    interpolation: {
      escapeValue: false,
    },
    debug: false,
  });
}

export default i18n;
