import { create } from "zustand";

type DashboardView = "overview" | "risk" | "reports" | "analytics" | "ai";

type UiState = {
  view: DashboardView;
  setView: (view: DashboardView) => void;
};

export const useUiStore = create<UiState>((set) => ({
  view: "overview",
  setView: (view) => set({ view })
}));
