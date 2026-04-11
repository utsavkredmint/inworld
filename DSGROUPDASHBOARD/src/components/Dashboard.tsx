import { 
  BarChart, 
  Bar, 
  XAxis, 
  YAxis, 
  CartesianGrid, 
  Tooltip, 
  ResponsiveContainer, 
  AreaChart, 
  Area,
  Cell
} from 'recharts';
import { 
  Phone, 
  Clock, 
  CheckCircle2, 
  TrendingUp, 
  ArrowUpRight, 
  ArrowDownRight,
  Activity,
  Users,
  MessageSquare
} from 'lucide-react';
import { useState, useEffect } from 'react';
import { motion } from 'motion/react';
import { cn } from '@/src/lib/utils';
import { api } from '@/src/lib/api';

export function Dashboard() {
  const [stats, setStats] = useState([
    { label: 'Total Calls', value: '0', change: '', trend: 'up' as const, icon: Phone, color: 'text-blue-500', bg: 'bg-blue-500/10' },
    { label: 'Avg. Duration', value: '0s', change: '', trend: 'up' as const, icon: Clock, color: 'text-purple-500', bg: 'bg-purple-500/10' },
    { label: 'Success Rate', value: '0%', change: '', trend: 'up' as const, icon: CheckCircle2, color: 'text-emerald-500', bg: 'bg-emerald-500/10' },
    { label: 'Active Bots', value: '0', change: '', trend: 'up' as const, icon: Activity, color: 'text-orange-500', bg: 'bg-orange-500/10' },
  ]);
  const [data, setData] = useState<any[]>([]);

  useEffect(() => {
    const loadStats = async () => {
      try {
        const [agentsRes, callsRes] = await Promise.all([
          api.listAgents(),
          api.listCalls(undefined, 200),
        ]);
        const calls = callsRes.calls;
        const totalCalls = calls.length;
        const completed = calls.filter(c => c.status === 'completed');
        const avgDuration = completed.length > 0
          ? Math.round(completed.reduce((s, c) => s + (c.duration_sec || 0), 0) / completed.length)
          : 0;
        const successRate = totalCalls > 0
          ? Math.round((completed.length / totalCalls) * 100)
          : 0;
        const activeBots = agentsRes.filter(a => a.status === 'active').length;

        setStats([
          { label: 'Total Calls', value: String(totalCalls), change: `${completed.length} completed`, trend: 'up', icon: Phone, color: 'text-blue-500', bg: 'bg-blue-500/10' },
          { label: 'Avg. Duration', value: `${avgDuration}s`, change: `${completed.length} calls`, trend: 'up', icon: Clock, color: 'text-purple-500', bg: 'bg-purple-500/10' },
          { label: 'Success Rate', value: `${successRate}%`, change: `${completed.length}/${totalCalls}`, trend: successRate >= 50 ? 'up' : 'down', icon: CheckCircle2, color: 'text-emerald-500', bg: 'bg-emerald-500/10' },
          { label: 'Active Bots', value: String(activeBots), change: `${agentsRes.length} total`, trend: 'up', icon: Activity, color: 'text-orange-500', bg: 'bg-orange-500/10' },
        ]);
      } catch (e) {
        console.error('Dashboard stats error:', e);
      }
    };
    loadStats();
    const interval = setInterval(loadStats, 10000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="p-8 space-y-8 overflow-y-auto h-full bg-white">
      {/* Stats Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        {stats.map((stat, i) => {
          const Icon = stat.icon;
          return (
            <motion.div
              key={stat.label}
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: i * 0.1 }}
              className="bg-zinc-50 border border-zinc-200 p-6 rounded-2xl group hover:border-zinc-300 transition-all"
            >
              <div className="flex items-center justify-between mb-4">
                <div className={cn("p-3 rounded-xl", stat.bg)}>
                  <Icon className={cn("w-6 h-6", stat.color)} />
                </div>
                <div className={cn(
                  "flex items-center gap-1 text-xs font-bold px-2 py-1 rounded-full",
                  stat.trend === 'up' ? "bg-emerald-500/10 text-emerald-600" : "bg-rose-500/10 text-rose-600"
                )}>
                  {stat.trend === 'up' ? <ArrowUpRight className="w-3 h-3" /> : <ArrowDownRight className="w-3 h-3" />}
                  {stat.change}
                </div>
              </div>
              <h3 className="text-zinc-500 text-sm font-medium mb-1">{stat.label}</h3>
              <p className="text-2xl font-bold text-zinc-900 tracking-tight">{stat.value}</p>
            </motion.div>
          );
        })}
      </div>

      {/* Charts Section */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 bg-zinc-50 border border-zinc-200 p-6 rounded-2xl">
          <div className="flex items-center justify-between mb-8">
            <div>
              <h3 className="text-zinc-900 font-semibold text-lg">Call Volume</h3>
              <p className="text-zinc-500 text-sm">Daily call and success distribution</p>
            </div>
            <select className="bg-white border border-zinc-200 text-zinc-600 text-xs rounded-lg px-3 py-1.5 focus:outline-none focus:ring-1 focus:ring-orange-500">
              <option>Last 7 Days</option>
              <option>Last 30 Days</option>
            </select>
          </div>
          <div className="h-[300px] w-full">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={data}>
                <defs>
                  <linearGradient id="colorCalls" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#f97316" stopOpacity={0.3}/>
                    <stop offset="95%" stopColor="#f97316" stopOpacity={0}/>
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="#e4e4e7" vertical={false} />
                <XAxis 
                  dataKey="name" 
                  stroke="#a1a1aa" 
                  fontSize={12} 
                  tickLine={false} 
                  axisLine={false} 
                  dy={10}
                />
                <YAxis 
                  stroke="#a1a1aa" 
                  fontSize={12} 
                  tickLine={false} 
                  axisLine={false} 
                  dx={-10}
                />
                <Tooltip 
                  contentStyle={{ backgroundColor: '#fff', border: '1px solid #e4e4e7', borderRadius: '8px', color: '#18181b' }}
                  itemStyle={{ color: '#f97316' }}
                />
                <Area 
                  type="monotone" 
                  dataKey="calls" 
                  stroke="#f97316" 
                  fillOpacity={1} 
                  fill="url(#colorCalls)" 
                  strokeWidth={3}
                />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="bg-zinc-50 border border-zinc-200 p-6 rounded-2xl">
          <h3 className="text-zinc-900 font-semibold text-lg mb-6">Recent Activity</h3>
          <div className="space-y-6">
            <div className="flex flex-col items-center justify-center py-12 text-center space-y-3">
              <div className="w-12 h-12 rounded-full bg-zinc-100 flex items-center justify-center">
                <MessageSquare className="w-6 h-6 text-zinc-300" />
              </div>
              <p className="text-sm text-zinc-400 font-medium">No recent activity</p>
            </div>
          </div>
          <button className="w-full mt-8 py-2 text-sm font-medium text-zinc-500 hover:text-zinc-900 hover:bg-zinc-100 border border-zinc-200 rounded-lg transition-all">
            View All Activity
          </button>
        </div>
      </div>

      {/* Bottom Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 pb-8">
        <div className="bg-zinc-50 border border-zinc-200 p-6 rounded-2xl">
          <h3 className="text-zinc-900 font-semibold text-lg mb-6">Top Performing Assistants</h3>
          <div className="space-y-4">
            <div className="flex flex-col items-center justify-center py-12 text-center space-y-3 bg-white rounded-xl border border-zinc-200 border-dashed">
              <Users className="w-8 h-8 text-zinc-200" />
              <p className="text-xs text-zinc-400 font-medium">No assistants found</p>
            </div>
          </div>
        </div>

        <div className="bg-zinc-50 border border-zinc-200 p-6 rounded-2xl">
          <h3 className="text-zinc-900 font-semibold text-lg mb-6">Campaign Performance</h3>
          <div className="h-[200px] w-full">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={data}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e4e4e7" vertical={false} />
                <XAxis dataKey="name" stroke="#a1a1aa" fontSize={12} tickLine={false} axisLine={false} />
                <YAxis stroke="#a1a1aa" fontSize={12} tickLine={false} axisLine={false} />
                <Tooltip 
                  cursor={{ fill: '#f4f4f5' }}
                  contentStyle={{ backgroundColor: '#fff', border: '1px solid #e4e4e7', borderRadius: '8px', color: '#18181b' }}
                />
                <Bar dataKey="success" fill="#f97316" radius={[4, 4, 0, 0]} barSize={24} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>
    </div>
  );
}
