/**
 * Fixed dark-navy sidebar app shell, same pattern as Mandate360's
 * frontend/mandate360-portal/src/components/ui/sidebar.tsx (D:\Finverge\
 * Code\DLP\LOS) — an internal desktop-first operational console, so no
 * mobile drawer/collapse machinery.
 */
import type { ComponentType, ReactNode } from "react"
import { cn } from "@/lib/utils"

export function SidebarShell({ children }: { children: ReactNode }) {
  return <div className="min-h-screen flex bg-background">{children}</div>
}

export function Sidebar({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <aside className={cn("w-64 shrink-0 bg-sidebar text-sidebar-foreground flex flex-col h-screen sticky top-0", className)}>
      {children}
    </aside>
  )
}

export function SidebarHeader({ children }: { children: ReactNode }) {
  return <div className="min-h-16 flex items-center gap-2.5 px-5 border-b border-sidebar-border">{children}</div>
}

export function SidebarNav({ children }: { children: ReactNode }) {
  return <nav className="flex-1 overflow-y-auto px-3 py-4 space-y-0.5">{children}</nav>
}

export function SidebarSectionLabel({ children }: { children: ReactNode }) {
  return <div className="px-3 pt-4 pb-1.5 text-[11px] font-semibold uppercase tracking-wider text-sidebar-foreground/40 first:pt-0">{children}</div>
}

export function SidebarNavItem({
  icon: Icon, label, active, onClick, badge,
}: {
  icon: ComponentType<{ className?: string }>
  label: string
  active?: boolean
  onClick?: () => void
  badge?: ReactNode
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "w-full flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm font-medium transition-colors text-left",
        active
          ? "bg-sidebar-primary text-sidebar-primary-foreground shadow-sm"
          : "text-sidebar-foreground/75 hover:bg-sidebar-accent hover:text-sidebar-accent-foreground",
      )}
    >
      <Icon className="h-4 w-4 shrink-0" />
      <span className="flex-1 truncate">{label}</span>
      {badge}
    </button>
  )
}

export function SidebarFooter({ children }: { children: ReactNode }) {
  return <div className="border-t border-sidebar-border p-3 space-y-2">{children}</div>
}

export function SidebarMain({ children }: { children: ReactNode }) {
  return <div className="flex-1 min-w-0 flex flex-col">{children}</div>
}

export function ContentHeader({ children }: { children: ReactNode }) {
  return (
    <div className="h-16 border-b border-border bg-card px-6 flex items-center justify-end gap-3 shrink-0">
      {children}
    </div>
  )
}

export function ContentBody({ children, className }: { children: ReactNode; className?: string }) {
  return <main className={cn("flex-1 px-6 py-8 max-w-6xl w-full mx-auto", className)}>{children}</main>
}

function initials(name: string) {
  const parts = name.trim().split(/\s+/).filter(Boolean)
  if (parts.length === 0) return "?"
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase()
  return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase()
}

export function UserAvatar({ name, className }: { name: string; className?: string }) {
  return (
    <div className={cn("h-9 w-9 rounded-full bg-primary text-primary-foreground flex items-center justify-center text-sm font-semibold shrink-0", className)}>
      {initials(name)}
    </div>
  )
}

export function PageHeader({ title, description, action }: { title: string; description?: string; action?: ReactNode }) {
  return (
    <div className="flex items-start justify-between gap-4 mb-6">
      <div>
        <h1 className="text-2xl font-bold text-foreground">{title}</h1>
        {description && <p className="text-sm text-muted-foreground mt-1">{description}</p>}
      </div>
      {action && <div className="shrink-0">{action}</div>}
    </div>
  )
}
