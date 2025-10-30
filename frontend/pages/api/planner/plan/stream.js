const BACKEND_BASE_URL =
  process.env.API_PROXY_TARGET?.replace(/\/$/, '') || 'http://166.117.38.176:8080';

export const config = {
  api: {
    responseLimit: false,
  },
};

export default async function handler(req, res) {
  if (req.method !== 'POST') {
    res.setHeader('Allow', 'POST');
    res.status(405).json({ message: 'Method Not Allowed' });
    return;
  }

  const controller = new AbortController();
  const { signal } = controller;

  req.on('close', () => {
    controller.abort();
  });

  try {
    const backendResponse = await fetch(`${BACKEND_BASE_URL}/planner/plan/stream`, {
      method: 'POST',
      credentials: 'include',
      signal,
      headers: {
        'Content-Type': 'application/json',
        Accept: 'text/event-stream',
        'Accept-Encoding': 'identity',
        Cookie: req.headers.cookie || '',
      },
      body: JSON.stringify(req.body),
    });

    if (!backendResponse.ok || !backendResponse.body) {
      const fallbackMessage = '获取行程规划流时发生错误。';
      let message = fallbackMessage;

      try {
        const data = await backendResponse.json();
        message = data?.message || fallbackMessage;
      } catch {
        // ignore
      }

      res.status(backendResponse.status).json({ message });
      return;
    }

    res.writeHead(200, {
      'Content-Type': 'text/event-stream',
      'Cache-Control': 'no-cache, no-transform',
      Connection: 'keep-alive',
      'X-Accel-Buffering': 'no',
    });

    if (typeof res.flushHeaders === 'function') {
      res.flushHeaders();
    }

    const reader = backendResponse.body.getReader();

    async function pump() {
      try {
        const { done, value } = await reader.read();

        if (done) {
          res.end();
          return;
        }

        if (value) {
          res.write(Buffer.from(value));
        }

        pump();
      } catch (error) {
        if (signal.aborted) {
          return;
        }
        res.end();
      }
    }

    pump();
  } catch (error) {
    if (signal.aborted) {
      return;
    }
    res.status(500).json({ message: '获取行程规划流时发生错误。' });
  }
}
