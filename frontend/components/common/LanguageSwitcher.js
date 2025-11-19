import { Button } from '@douyinfe/semi-ui';
import { useTranslation } from 'react-i18next';
import { supportedLanguages } from '@lib/i18n';

function LanguageSwitcher() {
  const { i18n } = useTranslation();

  const handleSwitch = (key) => {
    if (i18n.language !== key) {
      i18n.changeLanguage(key);
    }
  };

  return (
    <div className="language-switcher">
      {supportedLanguages.map((lang) => (
        <Button
          key={lang.key}
          size="small"
          theme={i18n.language === lang.key ? 'solid' : 'light'}
          onClick={() => handleSwitch(lang.key)}
        >
          {lang.label}
        </Button>
      ))}
    </div>
  );
}

export default LanguageSwitcher;
