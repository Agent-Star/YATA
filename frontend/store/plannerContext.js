import { createContext, useContext, useReducer } from 'react';
import { initialPlannerState, plannerReducer } from './plannerReducer';

const PlannerContext = createContext(null);

export function PlannerProvider({ children }) {
  const [state, dispatch] = useReducer(plannerReducer, initialPlannerState);

  return (
    <PlannerContext.Provider value={{ state, dispatch }}>
      {children}
    </PlannerContext.Provider>
  );
}

export function usePlannerContext() {
  const context = useContext(PlannerContext);

  if (!context) {
    throw new Error('usePlannerContext must be used within PlannerProvider');
  }

  return context;
}
