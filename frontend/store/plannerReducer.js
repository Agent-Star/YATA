import { sidebarGroups } from '@data/sidebarSections';
import { quickActions } from '@data/quickActions';

export const initialPlannerState = {
  activeSection: 'ai-planner',
  sidebarGroups,
  quickActions,
  messages: [],
  isLoading: false,
  hasInitializedHistory: false,
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
    case 'SET_MESSAGES':
      return {
        ...state,
        messages: Array.isArray(action.payload) ? action.payload : [],
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
    case 'UPDATE_MESSAGE':
      return {
        ...state,
        messages: state.messages.map((message) =>
          message.id === action.payload.id
            ? { ...message, ...action.payload.updates }
            : message
        ),
      };
    case 'SET_HISTORY_INITIALIZED':
      return {
        ...state,
        hasInitializedHistory: true,
      };
    default:
      return state;
  }
}
