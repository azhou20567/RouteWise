import type { Metadata } from 'next'
import './globals.css'

export const metadata: Metadata = {
  title: 'RouteWise — School Bus Route Optimizer',
  description:
    'Analyze school bus route inefficiencies and generate AI-powered optimization recommendations.',
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en" className="h-full">
      <body className="h-full overflow-hidden antialiased">{children}</body>
    </html>
  )
}
