import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Evently",
  description: "Discover and manage events near you",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className="antialiased">{children}</body>
    </html>
  );
}
