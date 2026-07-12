import type { Metadata } from "next";
import { Archivo, Inter, JetBrains_Mono } from "next/font/google";
import "./globals.css";

const archivo = Archivo({
  subsets: ["latin"],
  weight: ["600", "700"],
  variable: "--font-archivo",
});
const inter = Inter({ subsets: ["latin"], variable: "--font-inter" });
const jetbrains = JetBrains_Mono({
  subsets: ["latin"],
  variable: "--font-jetbrains",
});

export const metadata: Metadata = {
  title: "TrustRail",
  description:
    "Forward it. We'll tell you if the market actually said it.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body
        className={`${archivo.variable} ${inter.variable} ${jetbrains.variable} font-body min-h-screen flex flex-col`}
      >
        <main className="flex-1">{children}</main>
        <footer className="border-t border-hairline py-4 text-center text-sm text-info">
          Hackathon prototype — not affiliated with SEBI.
        </footer>
      </body>
    </html>
  );
}
