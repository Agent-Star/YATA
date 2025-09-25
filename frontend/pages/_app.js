import { ConfigProvider } from '@douyinfe/semi-ui';
import { PlannerProvider } from '@store/plannerContext';
import '@lib/i18n';
import '@styles/globals.css';

function App({ Component, pageProps }) {
  return (
    <ConfigProvider locale={{}}>
      <PlannerProvider>
        <Component {...pageProps} />
      </PlannerProvider>
    </ConfigProvider>
  );
}

export default App;
