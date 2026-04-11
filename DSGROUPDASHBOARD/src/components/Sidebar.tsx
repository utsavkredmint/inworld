import React from 'react';
import { 
  LayoutDashboard, 
  Bot, 
  Database, 
  MessageSquare, 
  Users, 
  Megaphone, 
  Settings,
  ChevronRight,
  LogOut,
  Mic
} from 'lucide-react';
import { cn } from '@/src/lib/utils';
import { NavItem } from '@/src/types';

interface SidebarProps {
  activeItem: NavItem;
  onItemClick: (item: NavItem) => void;
}

const navItems: { name: NavItem; icon: React.ElementType }[] = [
  { name: 'Dashboard', icon: LayoutDashboard },
  { name: 'Assistants', icon: Bot },
  { name: 'Voices', icon: Mic },
  { name: 'Knowledge Bases', icon: Database },
  { name: 'Threads', icon: MessageSquare },
  { name: 'Contacts', icon: Users },
  { name: 'Campaigns', icon: Megaphone },
  { name: 'Settings', icon: Settings },
];

export function Sidebar({ activeItem, onItemClick }: SidebarProps) {
  return (
    <aside className="w-64 h-screen bg-zinc-50 border-r border-zinc-200 flex flex-col shrink-0">
      <div className="p-6">
        <div className="flex items-center gap-3 mb-8">
          <div className="w-10 h-10 bg-orange-500 rounded-xl flex items-center justify-center">
            <Bot className="text-white w-6 h-6" />
          </div>
          <div>
            <h1 className="text-zinc-900 font-bold text-lg tracking-tight">kredmint</h1>
            <p className="text-zinc-500 text-xs font-medium uppercase tracking-widest">voice bot</p>
          </div>
        </div>

        <nav className="space-y-1">
          {navItems.map((item) => {
            const Icon = item.icon;
            const isActive = activeItem === item.name;
            return (
              <button
                key={item.name}
                onClick={() => onItemClick(item.name)}
                className={cn(
                  "w-full flex items-center gap-3 px-4 py-3 rounded-lg text-sm font-medium transition-all duration-200 group",
                  isActive 
                    ? "bg-orange-500/10 text-orange-600" 
                    : "text-zinc-500 hover:bg-zinc-100 hover:text-zinc-900"
                )}
              >
                <Icon className={cn(
                  "w-5 h-5",
                  isActive ? "text-orange-600" : "text-zinc-400 group-hover:text-zinc-600"
                )} />
                <span>{item.name}</span>
                {isActive && <ChevronRight className="ml-auto w-4 h-4" />}
              </button>
            );
          })}
        </nav>
      </div>

      <div className="mt-auto p-6 border-t border-zinc-200">
        <button className="w-full flex items-center gap-3 px-4 py-3 text-zinc-500 hover:text-zinc-900 transition-colors text-sm font-medium">
          <LogOut className="w-5 h-5" />
          <span>Logout</span>
        </button>
      </div>
    </aside>
  );
}
