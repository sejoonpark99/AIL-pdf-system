"use client"

import { Toaster } from "sonner"
import { LenisProvider } from "@/components/lenis-provider"
import { SidebarProvider } from "@/components/ui/sidebar"
import { AppSidebar } from "@/components/app-sidebar"
import { FileText } from "lucide-react"
import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbList,
  BreadcrumbPage,
} from "@/components/ui/breadcrumb"


function SidebarContentWrapper({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex h-screen w-screen overflow-hidden relative" style={{ background: '#111111' }}>
      <AppSidebar />
      <main className="flex-1 flex flex-col overflow-hidden relative" style={{ background: '#111111' }}>
          <div className="sticky top-0 z-10 bg-background px-4 h-14 flex items-center">
            <div className="flex items-center justify-between w-full">
              <div className="flex items-center gap-3">
                <Breadcrumb>
                  <BreadcrumbList>
                    <BreadcrumbItem>
                      <BreadcrumbPage className="flex items-center gap-2 text-sm font-medium text-gray-400">
                        <FileText className="w-4 h-4 text-gray-400" />
                        PDF Viewer
                      </BreadcrumbPage>
                    </BreadcrumbItem>
                  </BreadcrumbList>
                </Breadcrumb>
              </div>
            </div>
          </div>
          <div className="flex-1 overflow-hidden">
            {children}
          </div>
        </main>
      </div>
  )
}

export function ClientLayout({ children }: { children: React.ReactNode }) {
  return (
    <LenisProvider>
      <SidebarProvider>
        <SidebarContentWrapper>{children}</SidebarContentWrapper>
        <Toaster position="top-center" duration={2000} />
      </SidebarProvider>
    </LenisProvider>
  )
}
