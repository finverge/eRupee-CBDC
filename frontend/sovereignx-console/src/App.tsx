import { useState } from "react"
import { Login } from "@/components/Login"
import { Dashboard } from "@/components/Dashboard"
import { Schemes } from "@/components/Schemes"
import { Compliance } from "@/components/Compliance"
import { Agents } from "@/components/Agents"
import { Button } from "@/components/ui/button"
import {
  SidebarShell, Sidebar, SidebarHeader, SidebarNav, SidebarNavItem, SidebarFooter, SidebarMain,
  ContentHeader, ContentBody, UserAvatar,
} from "@/components/ui/sidebar"
import { getStoredSession, setStoredSession, clearStoredSession, type Session } from "@/lib/auth"
import { setActiveToken } from "@/lib/api"
import { LogOut, LayoutDashboard, FileText, ShieldAlert, Users } from "lucide-react"

type View = "dashboard" | "schemes" | "compliance" | "agents"

function App() {
  const [session, setSession] = useState<Session | null>(() => {
    const s = getStoredSession()
    if (s) setActiveToken(s.accessToken)
    return s
  })
  const [view, setView] = useState<View>("dashboard")

  function handleSignedIn(s: Session) {
    setStoredSession(s)
    setSession(s)
  }

  function signOut() {
    clearStoredSession()
    setActiveToken(null)
    setSession(null)
    setView("dashboard")
  }

  if (!session) {
    return <Login onSignedIn={handleSignedIn} />
  }

  const canManageSchemes = ["scheme_administrator", "platform_admin"].includes(session.role)
  const canReviewCompliance = ["compliance_officer", "platform_admin"].includes(session.role)

  return (
    <SidebarShell>
      <Sidebar>
        <SidebarHeader>
          <div className="h-8 w-8 rounded-md bg-white/95 flex items-center justify-center text-primary font-bold text-sm shrink-0">₹</div>
          <div className="leading-tight min-w-0">
            <div className="text-sm font-semibold text-white truncate">SovereignX</div>
            <div className="text-[11px] text-sidebar-foreground/50 truncate">Scheme Administrator Console</div>
          </div>
        </SidebarHeader>

        <SidebarNav>
          <SidebarNavItem icon={LayoutDashboard} label="Dashboard" active={view === "dashboard"} onClick={() => setView("dashboard")} />
          <SidebarNavItem icon={FileText} label="Schemes" active={view === "schemes"} onClick={() => setView("schemes")} />
          <SidebarNavItem icon={Users} label="Agents" active={view === "agents"} onClick={() => setView("agents")} />
          <SidebarNavItem icon={ShieldAlert} label="Compliance" active={view === "compliance"} onClick={() => setView("compliance")} />
        </SidebarNav>

        <SidebarFooter>
          <div className="px-1 text-xs text-sidebar-foreground/50 truncate">{session.email}</div>
          <Button
            variant="outline" size="sm"
            className="w-full gap-1.5 bg-transparent text-sidebar-foreground border-sidebar-border hover:bg-sidebar-accent hover:text-sidebar-accent-foreground"
            onClick={signOut}
          >
            <LogOut className="h-3.5 w-3.5" /> Sign out
          </Button>
        </SidebarFooter>
      </Sidebar>

      <SidebarMain>
        <ContentHeader>
          <div className="text-right leading-tight">
            <div className="text-sm font-medium">{session.fullName}</div>
            <div className="text-xs text-muted-foreground">{session.role.replace(/_/g, " ")}</div>
          </div>
          <UserAvatar name={session.fullName} />
        </ContentHeader>

        <ContentBody>
          {view === "dashboard" && <Dashboard />}
          {view === "schemes" && <Schemes canManage={canManageSchemes} />}
          {view === "agents" && <Agents canManage={canManageSchemes} />}
          {view === "compliance" && <Compliance canReview={canReviewCompliance} />}
        </ContentBody>
      </SidebarMain>
    </SidebarShell>
  )
}

export default App
