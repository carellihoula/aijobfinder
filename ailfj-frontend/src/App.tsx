import { useEffect } from "react"
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom"
import { SidebarProvider }   from "./lib/sidebarContext"
import { UserProvider, useUser } from "./lib/userContext"
import LandingPage         from "./pages/LandingPage"
import LoginPage           from "./pages/LoginPage"
import RegisterPage        from "./pages/RegisterPage"
import OnboardingPage      from "./pages/OnboardingPage"
import DashboardPage       from "./pages/DashboardPage"
import SettingsPage        from "./pages/SettingsPage"
import ApplyPage           from "./pages/ApplyPage"
import ApplicationsPage    from "./pages/ApplicationsPage"
import DocumentsPage       from "./pages/DocumentsPage"
import SavedJobsPage       from "./pages/SavedJobsPage"
import StatsPage           from "./pages/StatsPage"
import NotificationsPage   from "./pages/NotificationsPage"
import ProfilePage         from "./pages/ProfilePage"
import AdminPage           from "./pages/AdminPage"
import ForgotPasswordPage  from "./pages/ForgotPasswordPage"
import ResetPasswordPage   from "./pages/ResetPasswordPage"
import VerifyEmailPage     from "./pages/VerifyEmailPage"

function PrivateRoute({ children }: { children: React.ReactNode }) {
  const { me, loading } = useUser()
  if (loading) return null
  return me ? <>{children}</> : <Navigate to="/login" replace />
}

// Catch-all: send logged-in users back to their dashboard, everyone else to the landing page.
function FallbackRoute() {
  const { me, loading } = useUser()
  if (loading) return null
  return <Navigate to={me ? "/dashboard" : "/"} replace />
}

function AdminRoute({ children }: { children: React.ReactNode }) {
  const { me, isAdmin, loading } = useUser()
  if (loading) return null
  if (!me) return <Navigate to="/login" replace />
  return isAdmin ? <>{children}</> : <Navigate to="/dashboard" replace />
}

function AppRoutes() {
  return (
    <Routes>
      <Route path="/login"            element={<LoginPage />} />
      <Route path="/register"         element={<RegisterPage />} />
      <Route path="/forgot-password"  element={<ForgotPasswordPage />} />
      <Route path="/reset-password"   element={<ResetPasswordPage />} />
      <Route path="/verify-email"     element={<VerifyEmailPage />} />
      <Route path="/setup"    element={<PrivateRoute><OnboardingPage /></PrivateRoute>} />
      <Route path="/settings" element={<PrivateRoute><SettingsPage /></PrivateRoute>} />
      <Route path="/apply/:analysisId/:jobIndex" element={<PrivateRoute><ApplyPage /></PrivateRoute>} />
      <Route path="/applications"  element={<PrivateRoute><ApplicationsPage /></PrivateRoute>} />
      <Route path="/documents"     element={<PrivateRoute><DocumentsPage /></PrivateRoute>} />
      <Route path="/saved"         element={<PrivateRoute><SavedJobsPage /></PrivateRoute>} />
      <Route path="/stats"         element={<PrivateRoute><StatsPage /></PrivateRoute>} />
      <Route path="/notifications" element={<PrivateRoute><NotificationsPage /></PrivateRoute>} />
      <Route path="/profile"       element={<PrivateRoute><ProfilePage /></PrivateRoute>} />
      <Route path="/admin"         element={<AdminRoute><AdminPage /></AdminRoute>} />
      <Route path="/dashboard"     element={<PrivateRoute><DashboardPage /></PrivateRoute>} />
      <Route path="/"              element={<LandingPage />} />
      <Route path="*"              element={<FallbackRoute />} />
    </Routes>
  )
}

export default function App() {
  useEffect(() => {
    const saved = localStorage.getItem("ajf_theme")
    if (saved === "light") {
      document.documentElement.classList.remove("dark")
    } else {
      document.documentElement.classList.add("dark")
    }
  }, [])

  return (
    <UserProvider>
      <SidebarProvider>
        <BrowserRouter>
          <AppRoutes />
        </BrowserRouter>
      </SidebarProvider>
    </UserProvider>
  )
}