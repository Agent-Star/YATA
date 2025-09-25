import { sidebarGroups } from '@data/sidebarSections';
import { quickActions } from '@data/quickActions';

export const initialPlannerState = {
  activeSection: 'ai-planner',
  sidebarGroups,
  quickActions,
  messages: [
    {
      id: 'welcome',
      role: 'assistant',
      contentKey: 'chat.initialMessage',
    },
  ],
  isLoading: false,
};

export function plannerReducer(state, action) {
  switch (action.type) {
    case 'SET_ACTIVE_SECTION':
      return {
        ...state,
        activeSection: action.payload,
      };
    case 'ADD_MESSAGE':
      return {
        ...state,
        messages: [...state.messages, action.payload],
      };
    case 'SET_LOADING':
      return {
        ...state,
        isLoading: action.payload,
      };
    case 'PREPEND_QUICK_ACTION':
      if (state.quickActions.some((item) => item.key === action.payload.key)) {
        return state;
      }

      return {
        ...state,
        quickActions: [action.payload, ...state.quickActions],
      };
    default:
      return state;
  }
}
