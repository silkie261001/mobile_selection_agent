'use client';

import { Smartphone, Trash2, Sun, Moon } from 'lucide-react';
import { useState, useEffect } from 'react';

interface HeaderProps {
  onClearChat: () => void;
}

export function Header({ onClearChat }: HeaderProps) {
  const [isDark, setIsDark] = useState(true);

  useEffect(() => {
    // Set dark mode by default on first load
    document.documentElement.classList.add('dark');
    setIsDark(true);
  }, []);

  const toggleDarkMode = () => {
    document.documentElement.classList.toggle('dark');
    setIsDark(!isDark);
  };

  return (
    <header className="bg-white dark:bg-slate-800 border-b border-slate-200 dark:border-slate-700 px-4 py-3 shadow-sm">
      <div className="max-w-4xl mx-auto flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 bg-primary-600 rounded-xl flex items-center justify-center">
            <Smartphone className="w-6 h-6 text-white" />
          </div>
          <div>
            <h1 className="font-bold text-lg text-slate-800 dark:text-white">
              Mobile Shopping Assistant
            </h1>
            <p className="text-xs text-slate-500 dark:text-slate-400">
              AI-powered phone recommendations
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={toggleDarkMode}
            className="p-2 text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-700 rounded-lg transition-colors"
            aria-label="Toggle dark mode"
          >
            {isDark ? <Sun className="w-5 h-5" /> : <Moon className="w-5 h-5" />}
          </button>
          <button
            onClick={onClearChat}
            className="p-2 text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-700 rounded-lg transition-colors"
            aria-label="Clear chat"
          >
            <Trash2 className="w-5 h-5" />
          </button>
        </div>
      </div>
    </header>
  );
}
