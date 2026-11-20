"use client";

import clsx from "clsx";
import { Ban, LayoutDashboard, Mail, Megaphone, Send, SlidersHorizontal, Users } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useHealth, useMode } from "@/lib/hooks";

const NAV = [
  { href: "/", label: "Overview", icon: LayoutDashboard },
  { href: "/operations", label: "Operations", icon: SlidersHorizontal },
  { href: "/campaigns", label: "Campaigns", icon: Megaphone },
  { href: "/leads", label: "Leads", icon: Users },
  { href: "/sender-accounts", label: "Sender Accounts", icon: Mail },
  { href: "/suppression", label: "Suppression List", icon: Ban },
] as const;

function isActive(pathname: string, href: string) {
  return href === "/" ? pathname === "/" : pathname === href || pathname.startsWith(`${href}/`);
}

function Brand() {
  return (
    <div className="flex items-center gap-2.5">
      <span className="grid h-8 w-8 place-items-center rounded-lg bg-accent-bright text-white">
        <Send className="h-4 w-4" aria-hidden />
      </span>
      <div className="leading-tight">
        <p className="text-[15px] font-semibold text-white">Outreach Agent</p>
        <p className="text-xs text-rail-mute">Home services, US market</p>
      </div>
    </div>
  );
}

function ModeAndHealth() {
  const { data: mode } = useMode();
  const { data: health, error: healthError } = useHealth();
  const online = !!health && !healthError;
  const production = mode?.mode === "PRODUCTION";

  return (
    <div className="space-y-3">
      {mode && (
        <Link
          href="/operations"
          className={clsx(
            "block rounded-lg px-3 py-2.5 transition-colors",
            production ? "bg-accent-bright text-white hover:bg-accent" : "bg-rail-hover text-rail-text hover:bg-[#1F2F4A]",
          )}
        >
          <p className="text-[13px] font-semibold">{production ? "Production mode" : "Test mode"}</p>
          <p className={clsx("text-xs", production ? "text-white/85" : "text-rail-mute")}>
            {production ? "Emails go to real prospects" : "Emails go to your own inbox"}
          </p>
        </Link>
      )}
      <p className="flex items-center gap-2 px-1 text-xs text-rail-mute">
        <span
          aria-hidden
          className={clsx("h-2 w-2 rounded-full", online ? "bg-[#3DBE7A]" : health === undefined && !healthError ? "bg-rail-mute" : "bg-[#F0624D]")}
        />
        {online ? "API connected" : healthError ? "API offline" : "Connecting…"}
      </p>
    </div>
  );
}

export function Sidebar() {
  const pathname = usePathname();

  return (
    <>
      {/* Desktop: fixed left rail */}
      <aside className="fixed inset-y-0 left-0 z-20 hidden w-60 flex-col justify-between bg-rail px-4 py-5 lg:flex">
        <div>
          <div className="px-1 pb-6">
            <Brand />
          </div>
          <nav aria-label="Main">
            <ul className="space-y-0.5">
              {NAV.map(({ href, label, icon: Icon }) => {
                const active = isActive(pathname, href);
                return (
                  <li key={href}>
                    <Link
                      href={href}
                      aria-current={active ? "page" : undefined}
                      className={clsx(
                        "flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors",
                        active ? "bg-rail-hover text-white" : "text-rail-text hover:bg-rail-hover hover:text-white",
                      )}
                    >
                      <Icon className={clsx("h-[18px] w-[18px]", active ? "text-accent-bright" : "text-rail-mute")} aria-hidden />
                      {label}
                    </Link>
                  </li>
                );
              })}
            </ul>
          </nav>
        </div>
        <ModeAndHealth />
      </aside>

      {/* Below lg: compact top bar with a scrollable nav */}
      <header className="sticky top-0 z-20 bg-rail px-4 pb-2 pt-3 lg:hidden">
        <div className="flex items-center justify-between">
          <Brand />
        </div>
        <nav aria-label="Main" className="-mx-1 mt-3 overflow-x-auto">
          <ul className="flex gap-1 px-1">
            {NAV.map(({ href, label }) => {
              const active = isActive(pathname, href);
              return (
                <li key={href} className="shrink-0">
                  <Link
                    href={href}
                    aria-current={active ? "page" : undefined}
                    className={clsx(
                      "block rounded-lg px-3 py-1.5 text-sm font-medium",
                      active ? "bg-rail-hover text-white" : "text-rail-text",
                    )}
                  >
                    {label}
                  </Link>
                </li>
              );
            })}
          </ul>
        </nav>
      </header>
    </>
  );
}
