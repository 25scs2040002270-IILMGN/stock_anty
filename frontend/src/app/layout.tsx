import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: 'MarketPulse AI — Real-Time Stock Market Terminal',
  description: 'Production-oriented personal stock market analysis application for HDFCBANK and ICICIBANK.',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark">
      <body className="bg-terminal-bg text-terminal-text antialiased min-h-screen">
        {children}
      </body>
    </html>
  );
}

