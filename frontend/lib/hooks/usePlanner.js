import { useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import { usePlannerContext } from '@store/plannerContext';
import { requestPlan } from '@lib/services/aiPlanner';

export function usePlanner() {
  const { t, i18n } = useTranslation();
  const { state, dispatch } = usePlannerContext();

  const formatPlanResponse = useCallback(
    (plan) => {
      const itinerary = plan.itinerary
        .map((item) =>
          t('chat.plan.dailyTemplate', {
            day: item.day,
            highlight: t(item.highlightKey, { city: plan.city }),
          })
        )
        .join('\n');

      const tips = plan.tips.map((tipKey) => `- ${t(tipKey)}`).join('\n');

      return `${t('chat.plan.headline', { city: plan.city })}\n\n${t(
        'chat.plan.itineraryTitle'
      )}\n${itinerary}\n\n${t('chat.plan.tipsTitle')}\n${tips}`;
    },
    [t]
  );

  const setActiveSection = useCallback(
    (sectionKey) => {
      dispatch({ type: 'SET_ACTIVE_SECTION', payload: sectionKey });
    },
    [dispatch]
  );

  const addAssistantError = useCallback(() => {
    dispatch({
      type: 'ADD_MESSAGE',
      payload: {
        id: `assistant-${Date.now()}`,
        role: 'assistant',
        contentKey: 'chat.errorMessage',
      },
    });
  }, [dispatch]);

  const sendMessage = useCallback(
    async (content) => {
      const trimmed = content.trim();

      if (!trimmed) {
        return;
      }

      const userMessage = {
        id: `user-${Date.now()}`,
        role: 'user',
        content: trimmed,
      };

      dispatch({ type: 'ADD_MESSAGE', payload: userMessage });
      dispatch({ type: 'SET_LOADING', payload: true });

      try {
        const plan = await requestPlan(trimmed);
        const assistantMessage = {
          id: `assistant-${Date.now()}`,
          role: 'assistant',
          content: formatPlanResponse(plan),
        };

        dispatch({ type: 'ADD_MESSAGE', payload: assistantMessage });
      } catch (error) {
        addAssistantError();
      } finally {
        dispatch({ type: 'SET_LOADING', payload: false });
      }
    },
    [addAssistantError, dispatch, formatPlanResponse]
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

  return {
    state,
    sendMessage,
    triggerQuickAction,
    setActiveSection,
  };
}
