import clsx from "clsx";

interface CapacityGaugeProps {
  sent: number;
  followupsDue: number;
  remaining: number;
  total: number;
}

/**
 * One bar that answers "what is today’s capacity going to be spent on?".
 * Left to right: already sent, follow-ups that must go out, room left for
 * new leads, and (hatched) capacity held back by throttling.
 */
export function CapacityGauge({ sent, followupsDue, remaining, total }: CapacityGaugeProps) {
  if (total <= 0) {
    return <p className="text-sm text-ink-mute">No active sender accounts, so there is no capacity today.</p>;
  }

  const followupsInBar = Math.min(followupsDue, remaining);
  const room = Math.max(0, remaining - followupsDue);
  const held = Math.max(0, total - sent - remaining);

  const segments = [
    { key: "sent", label: "Sent today", shown: sent, bar: sent, className: "bg-ink" },
    { key: "followups", label: "Follow-ups due", shown: followupsDue, bar: followupsInBar, className: "bg-accent-bright" },
    { key: "room", label: "Room for new leads", shown: room, bar: room, className: "bg-ok" },
    { key: "held", label: "Held back by throttling", shown: held, bar: held, className: "" },
  ];

  const summary = segments.map((s) => `${s.label}: ${s.shown}`).join(", ");

  return (
    <div>
      <p className="mb-2 text-sm text-ink-soft">
        <span className="num text-[22px] font-semibold leading-7 text-ink">{remaining}</span> left of{" "}
        <span className="num font-medium text-ink">{total}</span> emails today
      </p>

      <div role="img" aria-label={`Today’s capacity. ${summary}`} className="flex h-3.5 gap-0.5 overflow-hidden rounded-full bg-sunken">
        {segments
          .filter((s) => s.bar > 0)
          .map((s) => (
            <span
              key={s.key}
              title={`${s.label}: ${s.shown}`}
              className={clsx("h-full first:rounded-l-full last:rounded-r-full", s.className)}
              style={{
                flexGrow: s.bar,
                flexBasis: 0,
                ...(s.key === "held"
                  ? { backgroundImage: "repeating-linear-gradient(45deg,#BAC3D2 0,#BAC3D2 3px,#E8ECF2 3px,#E8ECF2 6px)" }
                  : null),
              }}
            />
          ))}
      </div>

      <ul className="mt-3 flex flex-wrap gap-x-5 gap-y-1.5 text-[13px] text-ink-soft">
        {segments
          .filter((s) => s.shown > 0 || s.key !== "held")
          .map((s) => (
            <li key={s.key} className="flex items-center gap-2">
              <span
                aria-hidden
                className={clsx("h-2.5 w-2.5 rounded-sm", s.className)}
                style={
                  s.key === "held"
                    ? { backgroundImage: "repeating-linear-gradient(45deg,#BAC3D2 0,#BAC3D2 2px,#E8ECF2 2px,#E8ECF2 4px)" }
                    : undefined
                }
              />
              {s.label} <span className="num font-semibold text-ink">{s.shown}</span>
            </li>
          ))}
      </ul>
    </div>
  );
}
