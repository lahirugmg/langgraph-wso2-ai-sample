import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: 'Care-Plan Portal',
  description: 'Doctor-facing workspace for generating evidence-backed plan cards.',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
