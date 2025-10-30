import { apiRequest } from './apiClient';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || '';

export function streamPlan({ prompt, language, history, onToken, onMetadata }) {
  return new Promise((resolve, reject) => {
    if (typeof window === 'undefined' || typeof window.fetch === 'undefined') {
      reject(new Error('当前环境不支持流式请求。'));
      return;
    }

    const payload = {
      prompt,
      context: {
        language,
        history,
      },
    };

    const url = `${API_BASE_URL}/planner/plan/stream`;
    const controller = new AbortController();
    let resolved = false;
    let finalMessageId = null;
    let finalMetadata = null;

    const finalize = () => {
      if (resolved) {
        return;
      }
      resolved = true;
      controller.abort();
      resolve({
        messageId: finalMessageId || `assistant-${Date.now()}`,
        metadata: finalMetadata,
      });
    };

    const fail = (error) => {
      if (resolved) {
        return;
      }
      resolved = true;
      controller.abort();
      reject(error);
    };

    fetch(url, {
      method: 'POST',
      credentials: 'include',
      signal: controller.signal,
      headers: {
        'Content-Type': 'application/json',
        Accept: 'text/event-stream',
      },
      body: JSON.stringify(payload),
    })
      .then(async (response) => {
        if (!response.ok) {
          const contentType = response.headers.get('content-type') || '';
          let errorMessage = '获取行程规划流时发生错误。';

          if (contentType.includes('application/json')) {
            try {
              const data = await response.json();
              errorMessage = data?.message || errorMessage;
            } catch {
              // ignore json parse errors
            }
          }

          fail(new Error(errorMessage));
          return;
        }

        if (!response.body) {
          fail(new Error('浏览器不支持所需的流式响应能力。'));
          return;
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder('utf-8');
        let buffer = '';

        const findEventSeparator = (value) => {
          const doubleLfIndex = value.indexOf('\n\n');
          const doubleCrlfIndex = value.indexOf('\r\n\r\n');

          if (doubleLfIndex === -1) {
            return doubleCrlfIndex;
          }
          if (doubleCrlfIndex === -1) {
            return doubleLfIndex;
          }
          return Math.min(doubleLfIndex, doubleCrlfIndex);
        };

        const separatorLengthAt = (value, index) => {
          if (index < 0 || index >= value.length) {
            return 0;
          }
          return value.startsWith('\r\n\r\n', index) ? 4 : 2;
        };

        const processEvent = (rawEvent) => {
          if (!rawEvent) {
            return;
          }

          const lines = rawEvent.split(/\r?\n/);
          const dataLine = lines.find((line) => line.startsWith('data:'));
          if (!dataLine) {
            return;
          }

          const data = dataLine.slice(5).trim();
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
          } catch {
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
            case 'error':
              fail(new Error(parsed.content || '获取行程规划流时发生错误。'));
              break;
            default:
              break;
          }
        };

        const pump = () => {
          reader
            .read()
            .then(({ value, done }) => {
              if (done) {
                const remaining = buffer.trim();
                if (remaining) {
                  processEvent(remaining);
                }
                finalize();
                return;
              }

              buffer += decoder.decode(value, { stream: true });

              let separatorIndex = findEventSeparator(buffer);
              while (separatorIndex !== -1) {
                const separatorLength = separatorLengthAt(buffer, separatorIndex);
                const rawEvent = buffer.slice(0, separatorIndex).trim();
                buffer = buffer.slice(separatorIndex + separatorLength);
                processEvent(rawEvent);
                separatorIndex = findEventSeparator(buffer);
              }

              pump();
            })
            .catch((error) => {
              fail(error instanceof Error ? error : new Error('获取行程规划流时发生错误。'));
            });
        };

        pump();
      })
      .catch((error) => {
        fail(error instanceof Error ? error : new Error('获取行程规划流时发生错误。'));
      });
  });
}

export async function fetchHistory() {
  const data = await apiRequest('/planner/history', {
    method: 'GET',
  });

  return data;
}
