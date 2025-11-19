const API_PROXY_TARGET =
  process.env.API_PROXY_TARGET?.replace(/\/$/, '') || 'http://166.117.38.176:8080';

/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  experimental: {
    esmExternals: 'loose',
  },
  transpilePackages: [
    '@douyinfe/semi-ui',
    '@douyinfe/semi-icons',
    '@douyinfe/semi-illustrations',
  ],
  async rewrites() {
    return {
      afterFiles: [
        {
          source: '/api/:path*',
          destination: `${API_PROXY_TARGET}/:path*`,
        },
      ],
    };
  },
};

module.exports = nextConfig;
