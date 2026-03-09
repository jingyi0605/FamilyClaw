import {
  createContext,
  useContext,
  useEffect,
  useMemo,
  useState,
  type PropsWithChildren,
} from "react";

import { api } from "../lib/api";
import type { Household } from "../types";

const STORAGE_KEY = "familyclaw.currentHouseholdId";

type HouseholdContextValue = {
  household: Household | null;
  currentHouseholdId: string;
  setCurrentHouseholdId: (value: string) => void;
  refreshHousehold: (householdId?: string) => Promise<void>;
};

const HouseholdContext = createContext<HouseholdContextValue | undefined>(undefined);

export function HouseholdProvider({ children }: PropsWithChildren) {
  const [currentHouseholdId, setCurrentHouseholdIdState] = useState(
    () => window.localStorage.getItem(STORAGE_KEY) ?? "",
  );
  const [household, setHousehold] = useState<Household | null>(null);

  async function refreshHousehold(householdId = currentHouseholdId) {
    if (!householdId) {
      setHousehold(null);
      return;
    }

    const nextHousehold = await api.getHousehold(householdId);
    setHousehold(nextHousehold);
  }

  function setCurrentHouseholdId(value: string) {
    setCurrentHouseholdIdState(value);
    if (value) {
      window.localStorage.setItem(STORAGE_KEY, value);
    } else {
      window.localStorage.removeItem(STORAGE_KEY);
      setHousehold(null);
    }
  }

  useEffect(() => {
    if (!currentHouseholdId) {
      return;
    }

    refreshHousehold().catch(() => setHousehold(null));
  }, [currentHouseholdId]);

  const value = useMemo<HouseholdContextValue>(
    () => ({
      household,
      currentHouseholdId,
      setCurrentHouseholdId,
      refreshHousehold,
    }),
    [household, currentHouseholdId],
  );

  return <HouseholdContext.Provider value={value}>{children}</HouseholdContext.Provider>;
}

export function useHousehold() {
  const context = useContext(HouseholdContext);
  if (!context) {
    throw new Error("useHousehold must be used within HouseholdProvider");
  }
  return context;
}

