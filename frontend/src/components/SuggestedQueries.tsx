'use client';

import { Camera, Battery, Gamepad2, Smartphone, DollarSign, HelpCircle } from 'lucide-react';

interface SuggestedQueriesProps {
  onQueryClick: (query: string) => void;
}

const suggestions = [
  {
    icon: Camera,
    label: 'Best Camera',
    query: 'Best camera phone under ₹30,000?',
    color: 'text-purple-600 bg-purple-100 dark:bg-purple-900/30',
  },
  {
    icon: Battery,
    label: 'Battery King',
    query: 'Battery king with fast charging, around ₹15k',
    color: 'text-green-600 bg-green-100 dark:bg-green-900/30',
  },
  {
    icon: Gamepad2,
    label: 'Gaming Phone',
    query: 'Best gaming phone under ₹50,000?',
    color: 'text-red-600 bg-red-100 dark:bg-red-900/30',
  },
  {
    icon: Smartphone,
    label: 'Compact Phone',
    query: 'Compact Android with good one-hand use',
    color: 'text-blue-600 bg-blue-100 dark:bg-blue-900/30',
  },
  {
    icon: DollarSign,
    label: 'Budget 5G',
    query: 'Best 5G phone under ₹20,000?',
    color: 'text-amber-600 bg-amber-100 dark:bg-amber-900/30',
  },
  {
    icon: HelpCircle,
    label: 'Compare',
    query: 'Compare Pixel 8a vs OnePlus 12R',
    color: 'text-cyan-600 bg-cyan-100 dark:bg-cyan-900/30',
  },
];

export function SuggestedQueries({ onQueryClick }: SuggestedQueriesProps) {
  return (
    <div className="grid grid-cols-2 md:grid-cols-3 gap-3 max-w-2xl mx-auto">
      {suggestions.map((suggestion, index) => (
        <button
          key={index}
          onClick={() => onQueryClick(suggestion.query)}
          className="flex items-center gap-3 p-4 bg-white dark:bg-slate-800 rounded-xl border border-slate-200 dark:border-slate-700 hover:border-primary-400 dark:hover:border-primary-500 hover:shadow-md transition-all text-left group"
        >
          <div className={`w-10 h-10 rounded-lg flex items-center justify-center ${suggestion.color}`}>
            <suggestion.icon className="w-5 h-5" />
          </div>
          <div>
            <p className="font-medium text-slate-800 dark:text-white text-sm">
              {suggestion.label}
            </p>
            <p className="text-xs text-slate-500 dark:text-slate-400 line-clamp-1">
              {suggestion.query}
            </p>
          </div>
        </button>
      ))}
    </div>
  );
}
