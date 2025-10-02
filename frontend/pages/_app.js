import { ConfigProvider } from '@douyinfe/semi-ui';
import { PlannerProvider } from '@store/plannerContext';
import { AuthProvider } from '@store/authContext';
import '@lib/i18n';
import '@styles/globals.css';

function App({ Component, pageProps }) {
  return (
    <ConfigProvider locale={{}}>
      <AuthProvider>
        <PlannerProvider>
          <Component {...pageProps} />
        </PlannerProvider>
      </AuthProvider>
    </ConfigProvider>
  );
}

export default App;
