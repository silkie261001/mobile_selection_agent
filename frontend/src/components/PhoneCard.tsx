'use client';

import { Check, Star, Battery, Camera, Monitor, Info } from 'lucide-react';

interface Phone {
  id: string;
  name: string;
  brand: string;
  price: number;
  image_url: string;
  display: string;
  camera: string;
  battery: string;
  rating: number;
  highlights: string[];
}

interface PhoneCardProps {
  phone: Phone;
  isSelected: boolean;
  onSelect: () => void;
  onViewDetails: () => void;
}

export function PhoneCard({ phone, isSelected, onSelect, onViewDetails }: PhoneCardProps) {
  const formatPrice = (price: number) => {
    return new Intl.NumberFormat('en-IN', {
      style: 'currency',
      currency: 'INR',
      maximumFractionDigits: 0,
    }).format(price);
  };

  return (
    <div
      className={`bg-white dark:bg-slate-800 rounded-xl border-2 transition-all duration-200 overflow-hidden ${
        isSelected
          ? 'border-primary-500 shadow-lg shadow-primary-500/20'
          : 'border-slate-200 dark:border-slate-700 hover:border-slate-300 dark:hover:border-slate-600'
      }`}
    >
      {/* Header with brand and selection */}
      <div className="flex items-center justify-between px-4 py-2 bg-slate-50 dark:bg-slate-700/50">
        <span className="text-xs font-medium text-slate-500 dark:text-slate-400 uppercase tracking-wide">
          {phone.brand}
        </span>
        <button
          onClick={onSelect}
          className={`w-6 h-6 rounded-full border-2 flex items-center justify-center transition-colors ${
            isSelected
              ? 'bg-primary-500 border-primary-500 text-white'
              : 'border-slate-300 dark:border-slate-600 hover:border-primary-400'
          }`}
        >
          {isSelected && <Check className="w-3 h-3" />}
        </button>
      </div>

      {/* Content */}
      <div className="p-4">
        {/* Phone name and price */}
        <h3 className="font-semibold text-slate-800 dark:text-white mb-1 line-clamp-2">
          {phone.name}
        </h3>
        <div className="flex items-center gap-2 mb-3">
          <span className="text-lg font-bold text-primary-600 dark:text-primary-400">
            {formatPrice(phone.price)}
          </span>
          {phone.rating > 0 && (
            <span className="flex items-center gap-1 text-xs text-amber-600 dark:text-amber-400">
              <Star className="w-3 h-3 fill-current" />
              {phone.rating}
            </span>
          )}
        </div>

        {/* Specs */}
        <div className="space-y-2 text-sm text-slate-600 dark:text-slate-400">
          <div className="flex items-center gap-2">
            <Monitor className="w-4 h-4 text-slate-400" />
            <span className="truncate">{phone.display}</span>
          </div>
          <div className="flex items-center gap-2">
            <Camera className="w-4 h-4 text-slate-400" />
            <span className="truncate">{phone.camera}</span>
          </div>
          <div className="flex items-center gap-2">
            <Battery className="w-4 h-4 text-slate-400" />
            <span className="truncate">{phone.battery}</span>
          </div>
        </div>

        {/* Highlights */}
        {phone.highlights && phone.highlights.length > 0 && (
          <div className="mt-3 flex flex-wrap gap-1">
            {phone.highlights.slice(0, 2).map((highlight, index) => (
              <span
                key={index}
                className="text-xs px-2 py-1 bg-slate-100 dark:bg-slate-700 text-slate-600 dark:text-slate-300 rounded-full"
              >
                {highlight}
              </span>
            ))}
          </div>
        )}

        {/* View Details button */}
        <button
          onClick={onViewDetails}
          className="mt-3 w-full flex items-center justify-center gap-2 px-3 py-2 text-sm font-medium text-primary-600 dark:text-primary-400 hover:bg-primary-50 dark:hover:bg-primary-900/20 rounded-lg transition-colors"
        >
          <Info className="w-4 h-4" />
          View Details
        </button>
      </div>
    </div>
  );
}
