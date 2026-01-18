/**
 * Shared TypeScript types for the Mobile Shopping Agent frontend.
 */

export interface Phone {
  id: string;
  name: string;
  brand: string;
  price: number;
  display: string;
  camera: string;
  battery: string;
  rating: number;
  highlights: string[];
}

export interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  phones?: Phone[];
  timestamp: Date;
}
