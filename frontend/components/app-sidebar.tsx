"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { motion } from "framer-motion";
import {
  Sidebar,
  SidebarContent,
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  useSidebar,
} from "@/components/ui/sidebar";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  FileText,
  PanelLeft,
} from "lucide-react";
import { Button } from "@/components/ui/button";

const mainMenuItems = [
  {
    title: "PDF",
    url: "/pdf",
    icon: FileText,
  },
];

export function AppSidebar() {
  const pathname = usePathname();
  const { openMobile, setOpenMobile, isMobile, toggleSidebar } = useSidebar();
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  if (!mounted) {
    return null;
  }

  const menuItemVariants = {
    hidden: { opacity: 0, x: -20 },
    visible: {
      opacity: 1,
      x: 0,
      transition: {
        duration: 0.3
      }
    }
  };

  return (
    <Sidebar collapsible="icon">
      <SidebarHeader className="!px-3 !pt-4 !pb-3 group-data-[collapsible=icon]:!pt-4 group-data-[collapsible=icon]:!px-0">
        <div className="flex items-start justify-between gap-2 group-data-[collapsible=icon]:flex-col group-data-[collapsible=icon]:gap-2 group-data-[collapsible=icon]:items-center">
          <Link
            href="/pdf"
            className="flex items-center gap-3 flex-1 min-w-0 pl-2 pr-2 group-data-[collapsible=icon]:flex-none group-data-[collapsible=icon]:p-0 overflow-hidden"
            onClick={() => isMobile && setOpenMobile(!openMobile)}
          >
            {/* Text layout - hidden when collapsed */}
            <div className="flex flex-col flex-1 min-w-0 group-data-[collapsible=icon]:!hidden group-data-[collapsible=icon]:!w-0 group-data-[collapsible=icon]:!h-0 overflow-hidden">
              <div className="flex items-center gap-2">
                <span className="font-bold text-base truncate">
                  PDF Analysis
                </span>
              </div>
              <span className="text-xs text-gray-400 truncate">
                AI Document Analyzer
              </span>
            </div>
          </Link>
          <Button
            variant="ghost"
            size="icon"
            onClick={toggleSidebar}
            className="h-7 w-7 flex-shrink-0 -mt-1"
          >
            <PanelLeft className="h-4 w-4" />
            <span className="sr-only">Toggle Sidebar</span>
          </Button>
        </div>
      </SidebarHeader>
      <ScrollArea className="overflow-x-hidden">
        <SidebarContent className="gap-0 overflow-x-hidden">
          <SidebarGroup>
            <SidebarGroupLabel>Navigation</SidebarGroupLabel>
            <SidebarGroupContent>
              <SidebarMenu>
                {mainMenuItems.map((item) => {
                  const isActive = pathname === item.url;
                  return (
                    <motion.div
                      key={item.title}
                      initial="hidden"
                      animate="visible"
                      variants={menuItemVariants}
                    >
                      <SidebarMenuItem>
                        <SidebarMenuButton
                          isActive={isActive}
                          onClick={() => isMobile && setOpenMobile(!openMobile)}
                          asChild
                          tooltip={item.title}
                          className="transition-all duration-200"
                        >
                          <Link href={item.url}>
                            <item.icon className="h-4 w-4" />
                            <span>{item.title}</span>
                          </Link>
                        </SidebarMenuButton>
                      </SidebarMenuItem>
                    </motion.div>
                  );
                })}
              </SidebarMenu>
            </SidebarGroupContent>
          </SidebarGroup>
        </SidebarContent>
      </ScrollArea>
    </Sidebar>
  );
}
