import { create } from 'zustand'
import { persist } from 'zustand/middleware'

interface User {
  id: string
  email: string
  full_name?: string
  onboarding_completed?: boolean
}

interface Preferences {
  nickname: string
  ai_teacher_name: string
  ai_gender: string
  teaching_style: string
}

interface Subject {
  id: string
  name: string
  purpose: string
  level: string
  current_topic_index: number
}

interface AppState {
  token: string | null
  user: User | null
  preferences: Preferences | null
  subjects: Subject[]
  activeSubjectId: string | null
  activeTopicId: string | null

  setAuth: (token: string, user: User) => void
  setPreferences: (prefs: Preferences) => void
  setSubjects: (subjects: Subject[]) => void
  addSubject: (subject: Subject) => void
  removeSubject: (id: string) => void
  setActiveSubject: (id: string | null) => void
  setActiveTopic: (id: string | null) => void
  logout: () => void
}

export const useStore = create<AppState>()(
  persist(
    (set) => ({
      token: null,
      user: null,
      preferences: null,
      subjects: [],
      activeSubjectId: null,
      activeTopicId: null,

      setAuth: (token, user) => set({ token, user }),
      setPreferences: (prefs) => set({ preferences: prefs }),
      setSubjects: (subjects) => set({ subjects }),
      addSubject: (subject) =>
        set((state) => ({ subjects: [...state.subjects, subject] })),
      removeSubject: (id) =>
        set((state) => ({ subjects: state.subjects.filter((s) => s.id !== id) })),
      setActiveSubject: (id) => set({ activeSubjectId: id, activeTopicId: null }),
      setActiveTopic: (id) => set({ activeTopicId: id }),
      logout: () =>
        set({ token: null, user: null, preferences: null, subjects: [], activeSubjectId: null }),
    }),
    {
      name: 'one01-store',
      partialize: (state) => ({
        token: state.token,
        user: state.user,
        preferences: state.preferences,
        activeSubjectId: state.activeSubjectId,
      }),
    }
  )
)