"use client";

import clsx from "clsx";
import { ChevronDown } from "lucide-react";
import { useRef, useState } from "react";
import { toast } from "sonner";
import { mutate } from "swr";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Notice } from "@/components/ui/Notice";
import { Skeleton } from "@/components/ui/Skeleton";
import { Textarea } from "@/components/ui/Field";
import { api } from "@/lib/api";
import { formatDateTime } from "@/lib/format";
import { useTemplates } from "@/lib/hooks";
import { TEMPLATE_VARIABLES, TEMPLATE_VARIANTS, type Campaign, type Template } from "@/lib/types";
import { useAction } from "@/lib/useAction";

const VARIANT_LABEL: Record<string, string> = {
  pixel_found: "Pixel found",
  pixel_missing: "Pixel missing",
  pixel_unknown: "Pixel unknown",
  followup_1: "Follow-up 1",
  followup_2: "Follow-up 2",
};

const PLACEHOLDER =
  "{first_name}\n\n" +
  "I noticed {business_name} in {city}, {state} might be missing the Meta Pixel on your website. {website_observation}\n\n" +
  "Want a free trial? Just reply.";

export function TemplateEditor({ campaign }: { campaign: Campaign }) {
  const { data: templates, error } = useTemplates(campaign.id);
  const [variant, setVariant] = useState<string>(TEMPLATE_VARIANTS[0]);
  const [drafts, setDrafts] = useState<Record<string, string>>({});
  const [showHistory, setShowHistory] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const save = useAction(api.saveTemplateVersion, { errorTitle: "Couldn’t save the template" });

  if (error && !templates) return <Notice tone="danger">{error.message}</Notice>;
  if (!templates) {
    return (
      <div className="space-y-3">
        <Skeleton className="h-9 w-full" />
        <Skeleton className="h-40 w-full" />
      </div>
    );
  }

  // Newest first (the API sorts by updated_at desc).
  const versions = templates.filter((t) => t.variant === variant);
  const latest: Template | undefined = versions[0];
  const savedBody = latest?.body ?? "";
  const hasDraft = drafts[variant] !== undefined;
  const value = hasDraft ? drafts[variant] : savedBody;
  const dirty = hasDraft && drafts[variant] !== savedBody;
  const empty = value.trim() === "";

  const used = Array.from(value.matchAll(/\{([^{}\s]+)\}/g), (m) => m[1]);
  const unknown = Array.from(new Set(used.filter((v) => !(TEMPLATE_VARIABLES as readonly string[]).includes(v))));

  function setValue(text: string) {
    setDrafts((d) => ({ ...d, [variant]: text }));
  }

  function insertVariable(name: string) {
    const el = textareaRef.current;
    const token = `{${name}}`;
    const start = el?.selectionStart ?? value.length;
    const end = el?.selectionEnd ?? value.length;
    setValue(value.slice(0, start) + token + value.slice(end));
    requestAnimationFrame(() => {
      if (!el) return;
      el.focus();
      const pos = start + token.length;
      el.setSelectionRange(pos, pos);
    });
  }

  async function onSave() {
    const created = await save.run(campaign.id, variant, value);
    if (!created) return;
    await mutate<Template[]>(`/campaigns/${campaign.id}/templates`, (current) => [created, ...(current ?? [])]);
    setDrafts((d) => {
      const { [variant]: _removed, ...rest } = d;
      return rest;
    });
    toast.success(`Saved a new version of “${VARIANT_LABEL[variant] ?? variant}”. Past sends still reference the old version.`);
  }

  return (
    <div className="space-y-4">
      <div>
        <h3 className="text-[15px] font-semibold">Email templates</h3>
        <p className="mt-0.5 text-sm text-ink-soft">
          Write your own offer, pitch and call to action below. Approved variables are filled in automatically for each
          lead. A variant with no saved template can’t be sent, and those emails are skipped.
        </p>
      </div>

      <div role="tablist" aria-label="Template variant" className="flex flex-wrap gap-2">
        {TEMPLATE_VARIANTS.map((v) => {
          const saved = templates.some((t) => t.variant === v);
          const selected = v === variant;
          const unsaved = drafts[v] !== undefined && drafts[v] !== (templates.find((t) => t.variant === v)?.body ?? "");
          return (
            <button
              key={v}
              type="button"
              role="tab"
              aria-selected={selected}
              onClick={() => {
                setVariant(v);
                setShowHistory(false);
              }}
              className={clsx(
                "flex h-9 items-center gap-2 rounded-lg border px-3 text-sm font-semibold transition-colors",
                selected ? "border-ink bg-ink text-white" : "border-line-strong bg-surface text-ink-soft hover:border-ink-mute hover:text-ink",
              )}
            >
              <span
                aria-hidden
                className={clsx("h-2 w-2 rounded-full", saved ? "bg-ok" : selected ? "bg-white/50" : "bg-warn")}
              />
              {VARIANT_LABEL[v] ?? v}
              <span className="sr-only">{saved ? " (template saved)" : " (no template yet)"}</span>
              {unsaved && <span className="text-xs font-normal opacity-80">unsaved</span>}
            </button>
          );
        })}
      </div>

      <div role="tabpanel" className="space-y-3">
        <div>
          <p className="mb-1.5 text-[13px] font-semibold text-ink-soft">Insert a variable at the cursor</p>
          <div className="flex flex-wrap gap-1.5">
            {TEMPLATE_VARIABLES.map((v) => (
              <button
                key={v}
                type="button"
                onClick={() => insertVariable(v)}
                className="rounded-md border border-line-strong bg-sunken px-2 py-1 font-mono text-[12.5px] text-ink-soft transition-colors hover:border-accent-bright hover:text-ink"
              >
                {`{${v}}`}
              </button>
            ))}
          </div>
        </div>

        <Notice tone="warn">
          <code className="font-mono">{"{first_name}"}</code> already includes the full greeting (for example “Hi John,”), so
          don’t add “Hi” before it in your template.
        </Notice>

        <Textarea
          ref={textareaRef}
          aria-label={`${VARIANT_LABEL[variant] ?? variant} email body`}
          rows={10}
          value={value}
          placeholder={PLACEHOLDER}
          onChange={(e) => setValue(e.target.value)}
        />

        {unknown.length > 0 && (
          <p role="status" className="text-[13px] text-warn">
            Not an approved variable: {unknown.map((u) => `{${u}}`).join(", ")}
          </p>
        )}

        <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
          <Button variant="primary" loading={save.pending} disabled={!dirty || empty} onClick={onSave}>
            Save as new version
          </Button>
          {hasDraft && dirty && (
            <Button variant="ghost" onClick={() => setDrafts(({ [variant]: _r, ...rest }) => rest)}>
              Discard changes
            </Button>
          )}
          <p className="text-[13px] text-ink-mute">
            {latest ? `Current version last updated ${formatDateTime(latest.updated_at)}` : "No template saved for this variant yet."}
          </p>
        </div>
      </div>

      {versions.length > 1 && (
        <div className="rounded-lg border border-line">
          <button
            type="button"
            aria-expanded={showHistory}
            onClick={() => setShowHistory((s) => !s)}
            className="flex w-full items-center justify-between px-4 py-2.5 text-left text-sm font-semibold"
          >
            Version history ({versions.length})
            <ChevronDown className={clsx("h-4 w-4 text-ink-mute transition-transform", showHistory && "rotate-180")} aria-hidden />
          </button>
          {showHistory && (
            <ul className="divide-y divide-line border-t border-line">
              {versions.map((v, i) => (
                <li key={v.id} className="space-y-2 px-4 py-3">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <p className="flex items-center gap-2 text-sm font-medium">
                      {formatDateTime(v.updated_at)}
                      {i === 0 && <Badge tone="success">Current</Badge>}
                    </p>
                    {i > 0 && (
                      <Button size="sm" onClick={() => setValue(v.body)}>
                        Use in editor
                      </Button>
                    )}
                  </div>
                  <pre className="whitespace-pre-wrap break-words rounded-md bg-sunken px-3 py-2 font-mono text-[13px] leading-5 text-ink-soft">
                    {v.body}
                  </pre>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}
