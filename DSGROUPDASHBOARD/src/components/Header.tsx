import { Search, Bell, User, Settings as SettingsIcon, HelpCircle } from 'lucide-react';
import { NavItem } from '@/src/types';

interface HeaderProps {
  activeItem: NavItem;
}

export function Header({ activeItem }: HeaderProps) {
  return (
    <header className="h-16 border-b border-zinc-200 bg-white flex items-center justify-between px-8 shrink-0">
      <div className="flex items-center gap-4">
        <h2 className="text-zinc-900 font-semibold text-lg">{activeItem}</h2>
        <div className="h-4 w-px bg-zinc-200" />
        <div className="relative group">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-zinc-400 group-focus-within:text-orange-500 transition-colors" />
          <input 
            type="text" 
            placeholder="Search everything..." 
            className="bg-zinc-50 border border-zinc-200 rounded-lg pl-10 pr-4 py-1.5 text-sm text-zinc-600 focus:outline-none focus:ring-1 focus:ring-orange-500/50 focus:border-orange-500/50 w-64 transition-all"
          />
        </div>
      </div>

      <div className="flex items-center gap-4">
        <button className="p-2 text-zinc-400 hover:text-zinc-900 hover:bg-zinc-100 rounded-lg transition-all relative">
          <Bell className="w-5 h-5" />
          <span className="absolute top-2 right-2 w-2 h-2 bg-orange-500 rounded-full border-2 border-white" />
        </button>
        <button className="p-2 text-zinc-400 hover:text-zinc-900 hover:bg-zinc-100 rounded-lg transition-all">
          <HelpCircle className="w-5 h-5" />
        </button>
        <div className="h-8 w-px bg-zinc-200 mx-2" />
        <button className="flex items-center gap-3 pl-2 pr-1 py-1 rounded-full hover:bg-zinc-100 transition-all border border-transparent hover:border-zinc-200">
          <div className="flex flex-col items-end">
            <span className="text-sm font-medium text-zinc-900">Divyanshu</span>
            <span className="text-[10px] text-zinc-500 font-medium uppercase tracking-wider">Admin</span>
          </div>
          <div className="w-8 h-8 rounded-full bg-zinc-100 border border-zinc-200 flex items-center justify-center overflow-hidden">
            <User className="w-5 h-5 text-zinc-400" />
          </div>
        </button>
      </div>
    </header>
  );
}
