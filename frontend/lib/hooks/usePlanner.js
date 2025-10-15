import { useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import { usePlannerContext } from '@store/plannerContext';
import { streamPlan, fetchHistory } from '@lib/services/aiPlanner';

export function usePlanner() {
  const { t, i18n } = useTranslation();
  const { state, dispatch } = usePlannerContext();
  const { hasInitializedHistory } = state;

  const setActiveSection = useCallback(
    (sectionKey) => {
      dispatch({ type: 'SET_ACTIVE_SECTION', payload: sectionKey });
    },
    [dispatch]
  );

  const sendMessage = useCallback(
    async (content) => {
      const trimmed = content.trim();

      if (!trimmed) {
        return;
      }

      const timestamp = Date.now();
      const userMessage = {
        id: `user-${timestamp}`,
        role: 'user',
        content: trimmed,
        metadata: null,
      };

      const conversationHistory = [...state.messages, userMessage].map((message) => ({
        id: message.id,
        role: message.role,
        content:
          message.content ||
          (message.contentKey ? i18n.t(message.contentKey, message.contentParams) : ''),
        metadata: message.metadata || null,
      }));

      dispatch({ type: 'ADD_MESSAGE', payload: userMessage });
      dispatch({ type: 'SET_LOADING', payload: true });

      const assistantMessageId = `assistant-${timestamp}`;
      dispatch({
        type: 'ADD_MESSAGE',
        payload: {
          id: assistantMessageId,
          role: 'assistant',
          content: '',
          metadata: null,
        },
      });

      try {
        let accumulated = '';
        let latestMetadata = null;

        const result = await streamPlan({
          prompt: trimmed,
          language: i18n.language,
          history: conversationHistory,
          onToken: (delta) => {
            if (!delta) {
              return;
            }

            accumulated += delta;
            dispatch({
              type: 'UPDATE_MESSAGE',
              payload: {
                id: assistantMessageId,
                updates: {
                  content: accumulated,
                },
              },
            });
          },
          onMetadata: (metadata) => {
            latestMetadata = metadata;
            dispatch({
              type: 'UPDATE_MESSAGE',
              payload: {
                id: assistantMessageId,
                updates: {
                  metadata,
                },
              },
            });
          },
        });

        const finalMetadata = result?.metadata ?? latestMetadata;

        dispatch({
          type: 'UPDATE_MESSAGE',
          payload: {
            id: assistantMessageId,
            updates: {
              content: accumulated,
              metadata: finalMetadata || null,
              serverMessageId: result?.messageId || null,
            },
          },
        });
      } catch (error) {
        dispatch({
          type: 'UPDATE_MESSAGE',
          payload: {
            id: assistantMessageId,
            updates: {
              content: t('chat.errorMessage'),
              metadata: null,
            },
          },
        });
      } finally {
        dispatch({ type: 'SET_LOADING', payload: false });
      }
    },
    [dispatch, i18n, state.messages, t]
  );

  const triggerQuickAction = useCallback(
    async (action) => {
      dispatch({ type: 'PREPEND_QUICK_ACTION', payload: action });
      const promptValue =
        typeof action.prompt === 'string'
          ? action.prompt
          : action.prompt?.[i18n.language] || action.prompt?.en || '';

      if (promptValue) {
        await sendMessage(promptValue);
      }
    },
    [dispatch, i18n.language, sendMessage]
  );

  const loadHistory = useCallback(async () => {
    try {
      dispatch({ type: 'SET_LOADING', payload: true });
      const history = await fetchHistory();
      const mappedMessages = Array.isArray(history?.messages)
        ? history.messages.map((item) => ({
            id: item.id,
            role: item.role,
            content: item.content,
            metadata: item.metadata || null,
          }))
        : null;

      const fallbackMessage = {
        id: 'assistant-welcome',
        role: 'assistant',
        content: t('chat.initialMessage'),
        metadata: null,
      };

      const nextMessages =
        mappedMessages && mappedMessages.length > 0 ? mappedMessages : [fallbackMessage];

      dispatch({ type: 'SET_MESSAGES', payload: nextMessages });
    } catch (error) {
      dispatch({
        type: 'SET_MESSAGES',
        payload: [
          {
            id: 'assistant-welcome',
            role: 'assistant',
            content: t('chat.initialMessage'),
            metadata: null,
          },
        ],
      });
    } finally {
      dispatch({ type: 'SET_HISTORY_INITIALIZED' });
      dispatch({ type: 'SET_LOADING', payload: false });
    }
  }, [dispatch, t]);

  return {
    state,
    sendMessage,
    triggerQuickAction,
    setActiveSection,
    loadHistory,
    hasInitializedHistory,
  };
}
