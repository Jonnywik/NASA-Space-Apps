'use client';

import StatsSidebar from './StatsSidebar';
import { mockFloodData } from './mockData';

export default function Home() {
  return (
    <main className="relative w-screen h-screen bg-slate-950 overflow-hidden flex items-center justify-center">
      {/* Map placeholder until Leaflet is connected */}
      <div className="text-slate-500 font-mono text-sm border border-dashed border-slate-700 p-8 rounded-xl">
        [ Map layer renders here ]
      </div>

      {/* Your Floating Sidebar */}
      <StatsSidebar data={mockFloodData} />
    </main>
  );
}