/**
 * The API stores naive UTC datetimes (e.g. "2026-11-18T09:30:00" with no "Z").
 * JavaScript would read that as LOCAL time and shift it, so we force UTC here
 * and then display in the viewer's own timezone.
 */
export function parseServerDate(value: string | null | undefined): Date | null {
  if (!value) return null;
  const hasZone = /([zZ]|[+-]\d{2}:?\d{2})$/.test(value);
  const d = new Date(hasZone ? value : `${value}Z`);
  return Number.isNaN(d.getTime()) ? null : d;
}

export function formatDateTime(value: string | null | undefined): string {
  const d = parseServerDate(value);
  if (!d) return "—";
  return d.toLocaleString("en-US", {
    month: "short", day: "numeric", year: "numeric", hour: "2-digit", minute: "2-digit",
  });
}

export function formatDate(value: string | null | undefined): string {
  const d = parseServerDate(value);
  if (!d) return "—";
  return d.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
}

export function titleCase(s: string): string {
  return s.toLowerCase().replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

export function plural(n: number, one: string, many = `${one}s`): string {
  return `${n.toLocaleString("en-US")} ${n === 1 ? one : many}`;
}