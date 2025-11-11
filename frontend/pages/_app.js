import Head from 'next/head';
import { ConfigProvider } from '@douyinfe/semi-ui';
import { PlannerProvider } from '@store/plannerContext';
import { AuthProvider } from '@store/authContext';
import '@lib/i18n';
import '@styles/globals.css';

function App({ Component, pageProps }) {
  return (
    <>
      <Head>
        <title>YATA Travel</title>
        <link rel="icon" href="/logo.png" type="image/png" />
        <link rel="apple-touch-icon" href="/logo.png" />
      </Head>
      <ConfigProvider locale={{}}>
        <AuthProvider>
          <PlannerProvider>
            <Component {...pageProps} />
          </PlannerProvider>
        </AuthProvider>
      </ConfigProvider>
    </>
  );
}

export default App;
