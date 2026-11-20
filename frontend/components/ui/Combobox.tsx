"use client";

import clsx from "clsx";
import { Check, ChevronDown } from "lucide-react";
import { useEffect, useId, useMemo, useRef, useState } from "react";
import { controlClass } from "./Field";

interface ComboboxProps {
  id?: string;
  options: string[];
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  disabled?: boolean;
  className?: string;
  emptyText?: string;
}

/**
 * A select you can type into. Typing filters the list and matches ANYWHERE
 * in the option text (like the old dashboard's city picker).
 * Keys: Up/Down to move, Enter to pick, Esc to close.
 */
export function Combobox({
  id,
  options,
  value,
  onChange,
  placeholder,
  disabled,
  className,
  emptyText = "No match",
}: ComboboxProps) {
  const listId = useId();
  const listRef = useRef<HTMLUListElement>(null);
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [typed, setTyped] = useState(false);
  const [active, setActive] = useState(0);

  const filtered = useMemo(() => {
    const q = typed ? query.trim().toLowerCase() : "";
    return q ? options.filter((o) => o.toLowerCase().includes(q)) : options;
  }, [options, query, typed]);

  // Keep the highlighted row visible while moving with the keyboard.
  useEffect(() => {
    if (!open) return;
    const el = listRef.current?.children[active] as HTMLElement | undefined;
    el?.scrollIntoView({ block: "nearest" });
  }, [active, open]);

  function openList() {
    setOpen(true);
    setTyped(false);
    setQuery(value);
    setActive(Math.max(0, options.indexOf(value)));
  }

  function close() {
    setOpen(false);
    setTyped(false);
  }

  function pick(option: string) {
    onChange(option);
    close();
  }

  return (
    <div className={clsx("relative", className)}>
      <input
        id={id}
        role="combobox"
        aria-expanded={open}
        aria-controls={listId}
        aria-autocomplete="list"
        aria-activedescendant={open && filtered[active] ? `${listId}-${active}` : undefined}
        autoComplete="off"
        disabled={disabled}
        placeholder={placeholder}
        value={open ? query : value}
        className={clsx(controlClass, "h-10 pl-3 pr-9")}
        onFocus={(e) => {
          openList();
          e.currentTarget.select();
        }}
        onClick={() => {
          if (!open) openList();
        }}
        onBlur={close}
        onChange={(e) => {
          setQuery(e.target.value);
          setTyped(true);
          setActive(0);
          if (!open) setOpen(true);
        }}
        onKeyDown={(e) => {
          if (e.key === "ArrowDown") {
            e.preventDefault();
            if (!open) openList();
            else setActive((i) => Math.min(i + 1, Math.max(filtered.length - 1, 0)));
          } else if (e.key === "ArrowUp") {
            e.preventDefault();
            setActive((i) => Math.max(i - 1, 0));
          } else if (e.key === "Enter") {
            if (open && filtered[active]) {
              e.preventDefault();
              pick(filtered[active]);
            }
          } else if (e.key === "Escape") {
            if (open) {
              e.preventDefault();
              close();
            }
          } else if (e.key === "Tab") {
            close();
          }
        }}
      />
      <ChevronDown
        className="pointer-events-none absolute right-3 top-1/2 h-4 w-4 -translate-y-1/2 text-ink-mute"
        aria-hidden
      />

      {open && (
        <ul
          id={listId}
          ref={listRef}
          role="listbox"
          className="absolute z-30 mt-1 max-h-60 w-full overflow-auto rounded-lg border border-line bg-surface py-1 shadow-pop"
        >
          {filtered.length === 0 ? (
            <li role="presentation" className="px-3 py-2 text-sm text-ink-mute">
              {emptyText}
            </li>
          ) : (
            filtered.map((option, i) => (
              <li
                key={option}
                id={`${listId}-${i}`}
                role="option"
                aria-selected={option === value}
                // mousedown (not click) so the input doesn't blur and close the list first
                onMouseDown={(e) => {
                  e.preventDefault();
                  pick(option);
                }}
                onMouseEnter={() => setActive(i)}
                className={clsx(
                  "flex cursor-pointer items-center justify-between px-3 py-2 text-sm",
                  i === active && "bg-sunken",
                  option === value && "font-semibold",
                )}
              >
                {option}
                {option === value && <Check className="h-4 w-4 text-accent" aria-hidden />}
              </li>
            ))
          )}
        </ul>
      )}
    </div>
  );
}
