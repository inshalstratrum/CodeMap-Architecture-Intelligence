import React from 'react';

export const RulerOverlay: React.FC = () => {
  return (
    <div className="absolute inset-0 pointer-events-none z-10 select-none overflow-hidden">
      {/* Top horizontal ruler */}
      <div className="absolute top-0 left-0 right-0 h-5 bg-[#10141d]/85 border-b border-[#242d3f] flex items-end text-[9px] font-mono text-slate-500">
        {Array.from({ length: 40 }).map((_, i) => (
          <div
            key={i}
            className="flex-1 h-2 border-l border-slate-700/60 pl-1 flex items-center"
          >
            {i % 4 === 0 ? `${i * 100}` : ''}
          </div>
        ))}
      </div>

      {/* Left vertical ruler */}
      <div className="absolute top-5 left-0 bottom-0 w-6 bg-[#10141d]/85 border-r border-[#242d3f] flex flex-col text-[9px] font-mono text-slate-500">
        {Array.from({ length: 30 }).map((_, i) => (
          <div
            key={i}
            className="flex-1 w-full border-t border-slate-700/60 pt-0.5 pl-1 flex items-start"
          >
            {i % 3 === 0 ? `${i * 100}` : ''}
          </div>
        ))}
      </div>
    </div>
  );
};
