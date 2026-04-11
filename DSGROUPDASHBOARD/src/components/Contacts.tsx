import { 
  Users, 
  Search, 
  Filter, 
  Plus, 
  MoreVertical, 
  Phone, 
  Mail, 
  Tag,
  ChevronRight
} from 'lucide-react';
import { motion } from 'motion/react';
import { cn } from '@/src/lib/utils';
import { Contact } from '@/src/types';

const contacts: Contact[] = [];

export function Contacts() {
  return (
    <div className="p-8 space-y-8 overflow-y-auto h-full bg-white">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-zinc-900 font-semibold text-xl">Contacts</h3>
          <p className="text-zinc-500 text-sm">Manage your customer database and call history</p>
        </div>
        <button className="bg-orange-500 hover:bg-orange-600 text-white px-6 py-2.5 rounded-xl font-bold flex items-center gap-2 transition-all shadow-lg shadow-orange-500/20 active:scale-95">
          <Plus className="w-5 h-5" />
          Add Contact
        </button>
      </div>

      <div className="flex items-center gap-4">
        <div className="flex-1 relative group">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-zinc-400 group-focus-within:text-orange-500 transition-colors" />
          <input 
            type="text" 
            placeholder="Search contacts..." 
            className="w-full bg-zinc-50 border border-zinc-200 rounded-xl pl-10 pr-4 py-2.5 text-sm text-zinc-600 focus:outline-none focus:ring-1 focus:ring-orange-500/50 focus:border-orange-500/50 transition-all"
          />
        </div>
        <button className="p-2.5 bg-zinc-50 border border-zinc-200 rounded-xl text-zinc-400 hover:text-zinc-900 transition-all">
          <Filter className="w-5 h-5" />
        </button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-6">
        {contacts.map((contact, i) => (
          <motion.div
            key={contact.id}
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ delay: i * 0.05 }}
            className="bg-zinc-50 border border-zinc-200 p-6 rounded-2xl group hover:border-zinc-300 transition-all"
          >
            <div className="flex items-start justify-between mb-6">
              <div className="w-12 h-12 rounded-full bg-white border border-zinc-200 flex items-center justify-center group-hover:border-orange-500/50 transition-all">
                <Users className="w-6 h-6 text-orange-500" />
              </div>
              <button className="p-1 text-zinc-400 hover:text-zinc-900 transition-colors">
                <MoreVertical className="w-4 h-4" />
              </button>
            </div>

            <h4 className="text-zinc-900 font-bold text-lg mb-1">{contact.name}</h4>
            <p className="text-zinc-500 text-xs mb-6 flex items-center gap-1">
              Last call: {contact.lastCall}
            </p>

            <div className="space-y-3 mb-6">
              <div className="flex items-center gap-3 text-sm text-zinc-600">
                <Phone className="w-4 h-4" />
                {contact.phone}
              </div>
              <div className="flex items-center gap-3 text-sm text-zinc-600">
                <Mail className="w-4 h-4" />
                {contact.email}
              </div>
            </div>

            <div className="flex flex-wrap gap-2 mb-6">
              {contact.tags.map(tag => (
                <span key={tag} className="px-2 py-1 bg-white text-zinc-500 text-[10px] font-bold uppercase tracking-wider rounded-md border border-zinc-200">
                  {tag}
                </span>
              ))}
            </div>

            <button className="w-full bg-zinc-900 hover:bg-zinc-800 text-white py-2.5 rounded-xl text-xs font-bold flex items-center justify-center gap-2 transition-all">
              View Profile
              <ChevronRight className="w-3 h-3" />
            </button>
          </motion.div>
        ))}
      </div>
    </div>
  );
}
