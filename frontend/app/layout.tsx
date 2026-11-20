import type { Metadata } from "next";
import { IBM_Plex_Sans } from "next/font/google";
import "./globals.css";
import { Providers } from "@/components/Providers";
import { Sidebar } from "@/components/shell/Sidebar";

const ui = IBM_Plex_Sans({
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
  variable: "--font-ui",
  display: "swap",
});

export const metadata: Metadata = {
  title: "Outreach Agent",
  description: "Control panel for the AI Home Services Outreach Agent",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={ui.variable}>
      <body>
        <Providers>
          <Sidebar />
          <div className="lg:pl-60">
            <main className="mx-auto max-w-[1180px] px-5 py-8 lg:px-10 lg:py-10">{children}</main>
          </div>
        </Providers>
      </body>
    </html>
  );
}
