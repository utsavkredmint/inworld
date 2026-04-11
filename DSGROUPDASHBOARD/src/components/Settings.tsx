import { 
  Settings as SettingsIcon, 
  User, 
  Bell, 
  Lock, 
  Globe, 
  Database, 
  Shield, 
  CreditCard,
  ChevronRight,
  Save,
  Clock
} from 'lucide-react';
import { useState } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import { cn } from '@/src/lib/utils';

const settingsSections = [
  { id: 'profile', label: 'Profile Settings', icon: User, description: 'Manage your personal information and preferences' },
  { id: 'notifications', label: 'Notifications', icon: Bell, description: 'Configure how you receive alerts and updates' },
  { id: 'security', label: 'Security', icon: Lock, description: 'Update your password and security settings' },
  { id: 'billing', label: 'Billing & Plans', icon: CreditCard, description: 'Manage your subscription and payment methods' },
  { id: 'api', label: 'API & Webhooks', icon: Database, description: 'Configure API keys and webhook endpoints' },
  { id: 'compliance', label: 'Compliance', icon: Shield, description: 'Manage data privacy and compliance settings' },
];

export function Settings() {
  const [activeSection, setActiveSection] = useState('profile');

  return (
    <div className="p-8 space-y-8 overflow-y-auto h-full bg-white">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-zinc-900 font-semibold text-xl">Settings</h3>
          <p className="text-zinc-500 text-sm">Configure your account and platform preferences</p>
        </div>
        <button className="bg-orange-500 hover:bg-orange-600 text-white px-6 py-2.5 rounded-xl font-bold flex items-center gap-2 transition-all shadow-lg shadow-orange-500/20 active:scale-95">
          <Save className="w-5 h-5" />
          Save Changes
        </button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* Left: Navigation */}
        <div className="lg:col-span-1 space-y-2">
          {settingsSections.map((section) => {
            const Icon = section.icon;
            const isActive = activeSection === section.id;
            return (
              <button
                key={section.id}
                onClick={() => setActiveSection(section.id)}
                className={cn(
                  "w-full flex items-center gap-4 p-4 rounded-2xl border transition-all text-left group",
                  isActive 
                    ? "bg-orange-500/10 border-orange-500/20 text-orange-500" 
                    : "bg-zinc-50 border-zinc-200 text-zinc-500 hover:border-zinc-300 hover:text-zinc-900"
                )}
              >
                <div className={cn(
                  "w-10 h-10 rounded-xl flex items-center justify-center transition-all",
                  isActive ? "bg-orange-500 text-white" : "bg-zinc-100 text-zinc-400 group-hover:text-zinc-600"
                )}>
                  <Icon className="w-5 h-5" />
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-bold truncate">{section.label}</p>
                  <p className="text-[10px] text-zinc-500 truncate">{section.description}</p>
                </div>
                <ChevronRight className={cn("w-4 h-4 transition-all", isActive ? "opacity-100 translate-x-0" : "opacity-0 -translate-x-2")} />
              </button>
            );
          })}
        </div>

        {/* Right: Content Area */}
        <div className="lg:col-span-2">
          <AnimatePresence mode="wait">
            {activeSection === 'profile' ? (
              <motion.div 
                key="profile"
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -10 }}
                className="bg-white border border-zinc-200 rounded-2xl p-8 space-y-8"
              >
                <div className="space-y-6">
                  <h4 className="text-zinc-900 font-bold text-lg border-b border-zinc-100 pb-4">Personal Information</h4>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                    <div className="space-y-2">
                      <label className="text-xs font-bold text-zinc-500 uppercase tracking-wider">Full Name</label>
                      <input 
                        type="text" 
                        defaultValue="Amit Kumar"
                        className="w-full bg-zinc-50 border border-zinc-200 rounded-xl px-4 py-3 text-sm text-zinc-900 focus:outline-none focus:ring-1 focus:ring-orange-500 transition-all"
                      />
                    </div>
                    <div className="space-y-2">
                      <label className="text-xs font-bold text-zinc-500 uppercase tracking-wider">Email Address</label>
                      <input 
                        type="email" 
                        defaultValue="amit.kumar@kredmint.com"
                        className="w-full bg-zinc-50 border border-zinc-200 rounded-xl px-4 py-3 text-sm text-zinc-900 focus:outline-none focus:ring-1 focus:ring-orange-500 transition-all"
                      />
                    </div>
                    <div className="space-y-2">
                      <label className="text-xs font-bold text-zinc-500 uppercase tracking-wider">Phone Number</label>
                      <input 
                        type="tel" 
                        defaultValue="+91 98765 43210"
                        className="w-full bg-zinc-50 border border-zinc-200 rounded-xl px-4 py-3 text-sm text-zinc-900 focus:outline-none focus:ring-1 focus:ring-orange-500 transition-all"
                      />
                    </div>
                    <div className="space-y-2">
                      <label className="text-xs font-bold text-zinc-500 uppercase tracking-wider">Company Name</label>
                      <input 
                        type="text" 
                        defaultValue="kredmint DS Distributor"
                        className="w-full bg-zinc-50 border border-zinc-200 rounded-xl px-4 py-3 text-sm text-zinc-900 focus:outline-none focus:ring-1 focus:ring-orange-500 transition-all"
                      />
                    </div>
                  </div>
                </div>

                <div className="space-y-6">
                  <h4 className="text-zinc-900 font-bold text-lg border-b border-zinc-100 pb-4">Platform Preferences</h4>
                  <div className="space-y-4">
                    <div className="flex items-center justify-between p-4 bg-zinc-50 rounded-xl border border-zinc-200">
                      <div>
                        <p className="text-sm font-bold text-zinc-900">Email Notifications</p>
                        <p className="text-xs text-zinc-500">Receive daily summary reports via email</p>
                      </div>
                      <div className="w-12 h-6 bg-zinc-200 rounded-full relative cursor-pointer">
                        <div className="absolute left-1 top-1 w-4 h-4 bg-zinc-400 rounded-full" />
                      </div>
                    </div>
                  </div>
                </div>
              </motion.div>
            ) : (
              <motion.div 
                key="coming-soon"
                initial={{ opacity: 0, scale: 0.95 }}
                animate={{ opacity: 1, scale: 1 }}
                exit={{ opacity: 0, scale: 0.95 }}
                className="bg-white border border-zinc-200 rounded-2xl p-12 flex flex-col items-center justify-center text-center space-y-6 min-h-[400px]"
              >
                <div className="w-20 h-20 rounded-full bg-orange-50 border border-orange-100 flex items-center justify-center">
                  <Clock className="w-10 h-10 text-orange-500 animate-pulse" />
                </div>
                <div className="space-y-2">
                  <h4 className="text-2xl font-bold text-zinc-900">Coming Soon</h4>
                  <p className="text-zinc-500 max-w-xs mx-auto">
                    We are working on the <span className="font-bold text-zinc-900">{settingsSections.find(s => s.id === activeSection)?.label}</span> section. Stay tuned for updates!
                  </p>
                </div>
                <div className="flex gap-2">
                  <div className="w-2 h-2 rounded-full bg-orange-500 animate-bounce" style={{ animationDelay: '0ms' }} />
                  <div className="w-2 h-2 rounded-full bg-orange-500 animate-bounce" style={{ animationDelay: '150ms' }} />
                  <div className="w-2 h-2 rounded-full bg-orange-500 animate-bounce" style={{ animationDelay: '300ms' }} />
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </div>
    </div>
  );
}
