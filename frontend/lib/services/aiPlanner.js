import { apiRequest } from './apiClient';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || '';

export function streamPlan({ prompt, language, history, onToken, onMetadata }) {
  return new Promise((resolve, reject) => {
    if (typeof window === 'undefined' || typeof window.EventSource === 'undefined') {
      reject(new Error('当前环境不支持 EventSource。'));
      return;
    }

    const payload = {
      prompt,
      context: {
        language,
        history,
      },
    };

    const query = encodeURIComponent(JSON.stringify(payload));
    const url = `${API_BASE_URL}/planner/plan/stream?payload=${query}`;
    const eventSource = new EventSource(url, { withCredentials: true });

    let finalMessageId = null;
    let finalMetadata = null;
    let resolved = false;

    const cleanup = () => {
      eventSource.close();
    };

    const finalize = () => {
      if (resolved) {
        return;
      }
      resolved = true;
      cleanup();
      resolve({
        messageId: finalMessageId || `assistant-${Date.now()}`,
        metadata: finalMetadata,
      });
    };

    eventSource.onmessage = (event) => {
      const { data } = event;

      if (!data) {
        return;
      }

      if (data === '[DONE]') {
        finalize();
        return;
      }

      let parsed;
      try {
        parsed = JSON.parse(data);
      } catch (error) {
        return;
      }

      switch (parsed.type) {
        case 'token':
          if (parsed.delta && onToken) {
            onToken(parsed.delta);
          }
          break;
        case 'metadata':
          if (parsed.metadata) {
            finalMetadata = parsed.metadata;
            if (onMetadata) {
              onMetadata(parsed.metadata);
            }
          }
          break;
        case 'end':
          if (parsed.messageId) {
            finalMessageId = parsed.messageId;
          }
          if (parsed.metadata) {
            finalMetadata = parsed.metadata;
            if (onMetadata) {
              onMetadata(parsed.metadata);
            }
          }
          if (parsed.delta && onToken) {
            onToken(parsed.delta);
          }
          finalize();
          break;
        default:
          break;
      }
    };

    eventSource.onerror = () => {
      cleanup();
      reject(new Error('获取行程规划流时发生错误。'));
    };
  });
}

export async function fetchHistory() {
  const data = await apiRequest('/planner/history', {
    method: 'GET',
  });

  return data;
}
