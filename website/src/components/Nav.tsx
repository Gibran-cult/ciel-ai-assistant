"use client";

import { useEffect, useRef, useState } from "react";
import { links, nav as sections } from "@/content/site";

const PANEL_ID = "menu-utama";

// A plain bar above the 3D layer. Below 768px the four section links and Masuk fold into one
// panel under the bar; while it is open, Tab cycles inside the menu and Escape closes it.
export default function Nav() {
  const [open, setOpen] = useState(false);
  const buttonRef = useRef<HTMLButtonElement>(null);
  const panelRef = useRef<HTMLElement>(null);

  // A second press hands focus back to the button. A link click does not: the reader has just
  // been sent to a section, and pulling focus back up to the bar would undo that.
  const close = (restoreFocus: boolean) => {
    setOpen(false);
    if (restoreFocus) buttonRef.current?.focus();
  };

  useEffect(() => {
    if (!open) return;
    const button = buttonRef.current;
    const panel = panelRef.current;
    if (!button || !panel) return;

    const panelItems = () => Array.from(panel.querySelectorAll<HTMLElement>("a[href], button:not([disabled])"));
    panelItems()[0]?.focus();

    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        setOpen(false);
        button.focus();
        return;
      }
      if (e.key !== "Tab" || e.altKey || e.ctrlKey || e.metaKey) return;
      // The menu button stays in the cycle because it is the visible way to close the panel.
      const cycle = [button, ...panelItems()];
      const at = cycle.indexOf(document.activeElement as HTMLElement);
      e.preventDefault();
      const next = e.shiftKey ? (at <= 0 ? cycle.length - 1 : at - 1) : (at + 1) % cycle.length;
      cycle[next].focus();
    };
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, [open]);

  // Widening past the breakpoint hides the panel, so the open state goes with it.
  useEffect(() => {
    const wide = window.matchMedia("(min-width: 48rem)");
    const onChange = () => {
      if (wide.matches) setOpen(false);
    };
    wide.addEventListener("change", onChange);
    return () => wide.removeEventListener("change", onChange);
  }, []);

  const stroke = "origin-[12px_12px] transition-transform duration-[220ms] ease-out-expo";

  return (
    <header className="relative z-[2]">
      <div className="mx-auto flex h-[72px] w-full max-w-[1440px] items-center px-[var(--gutter)]">
        <a href="#atas" onClick={() => setOpen(false)} className="flex min-h-11 items-center gap-2.5">
          <svg width="28" height="28" viewBox="0 0 32 32" aria-hidden="true">
            <path d="M24.89 10.6A11.8 11.8 0 1 0 24.89 21.4H20.57A8.2 8.2 0 1 1 20.57 10.6Z" fill="var(--blue-text)" />
            <path d="M28.39 10.6A11.8 11.8 0 0 1 28.39 21.4H24.07A8.2 8.2 0 0 0 24.07 10.6Z" fill="var(--yellow)" />
          </svg>
          {/* The unlayered `a` colour in globals.css beats Tailwind's layered utilities, so link text takes its colour from an inner span. */}
          <span className="font-mark text-[1.625rem] font-medium leading-none tracking-[-0.01em] text-ink">Ciel</span>
        </a>

        <nav aria-label="Utama" className="ml-[clamp(28px,4vw,56px)] hidden md:block">
          <ul className="flex items-center gap-x-[clamp(20px,2.4vw,34px)]">
            {sections.map((s) => (
              <li key={s.href}>
                <a href={s.href} className="group inline-flex min-h-11 items-center">
                  <span className="text-[1.0625rem] font-medium text-muted transition-colors duration-[160ms] ease-out-expo group-hover:text-ink group-focus-visible:text-ink">
                    {s.label}
                  </span>
                </a>
              </li>
            ))}
          </ul>
        </nav>

        {/* .btn-secondary sets its own display outside any layer, so the breakpoint lives on this wrapper. */}
        <div className="ml-auto hidden md:flex">
          <a href={links.login} className="btn-secondary">
            Masuk
          </a>
        </div>

        <button
          ref={buttonRef}
          type="button"
          aria-expanded={open}
          aria-controls={PANEL_ID}
          onClick={() => {
            if (open) close(true);
            else setOpen(true);
          }}
          className="-mr-2 ml-auto inline-flex size-11 items-center justify-center rounded-full text-ink [-webkit-tap-highlight-color:transparent] hover:bg-surface-2 active:bg-surface-2 md:hidden"
        >
          <span className="sr-only">{open ? "Tutup menu" : "Buka menu"}</span>
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" aria-hidden="true">
            <path d="M4 12h16" className={`${stroke} ${open ? "translate-y-0 rotate-45" : "-translate-y-[3px] rotate-0"}`} />
            <path d="M4 12h16" className={`${stroke} ${open ? "translate-y-0 -rotate-45" : "translate-y-[3px] rotate-0"}`} />
          </svg>
        </button>
      </div>

      <nav
        id={PANEL_ID}
        ref={panelRef}
        aria-label="Utama"
        hidden={!open}
        className="absolute inset-x-0 top-full rounded-b-[22px] bg-surface md:hidden"
      >
        <div className="mx-auto w-full max-w-[1440px] px-[var(--gutter)] pb-7 pt-2">
          <ul>
            {sections.map((s) => (
              <li key={s.href}>
                <a
                  href={s.href}
                  onClick={() => close(false)}
                  className="-mx-3 flex min-h-13 items-center rounded-md px-3 [-webkit-tap-highlight-color:transparent] hover:bg-surface-2 active:bg-surface-2"
                >
                  <span className="text-[1.25rem] font-medium text-ink">{s.label}</span>
                </a>
              </li>
            ))}
          </ul>
          <div className="mt-5 flex">
            <a href={links.login} onClick={() => close(false)} className="btn-secondary">
              Masuk
            </a>
          </div>
        </div>
      </nav>
    </header>
  );
}
