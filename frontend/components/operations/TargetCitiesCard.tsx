"use client";

import { MapPin, Plus, X } from "lucide-react";
import { useState, type FormEvent } from "react";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Field, Input } from "@/components/ui/Field";
import { Notice } from "@/components/ui/Notice";
import { Skeleton } from "@/components/ui/Skeleton";
import { api } from "@/lib/api";
import { useSettings } from "@/lib/hooks";
import { useAction } from "@/lib/useAction";

export function TargetCitiesCard() {
  const { data, error, mutate } = useSettings();
  const [search, setSearch] = useState("");
  const [newCity, setNewCity] = useState("");
  const [newState, setNewState] = useState("");
  const [formError, setFormError] = useState<string | null>(null);
  const [removingIndex, setRemovingIndex] = useState<number | null>(null);

  const add = useAction(api.addTargetCity, { errorTitle: "Couldn’t add the city" });
  const remove = useAction(api.removeTargetCity, { errorTitle: "Couldn’t remove the city" });

  const cities = data?.target_cities ?? [];
  const query = search.trim().toLowerCase();
  // Keep each city’s index in the FULL list: the API removes by that index.
  const visible = cities
    .map((c, index) => ({ ...c, index }))
    .filter((c) => (query ? c.city.toLowerCase().includes(query) : true));

  async function onRemove(index: number) {
    setRemovingIndex(index);
    const result = await remove.run(index);
    setRemovingIndex(null);
    if (result) await mutate(result, { revalidate: false });
  }

  async function onAdd(e: FormEvent) {
    e.preventDefault();
    const city = newCity.trim();
    const state = newState.trim().toUpperCase();
    if (!city || !state) {
      setFormError("Enter both a city name and a 2-letter state code.");
      return;
    }
    if (!/^[A-Z]{2}$/.test(state)) {
      setFormError("The state code is 2 letters, like TX or AZ.");
      return;
    }
    if (cities.some((c) => c.city.toLowerCase() === city.toLowerCase() && c.state === state)) {
      setFormError(`${city}, ${state} is already in your list.`);
      return;
    }
    setFormError(null);
    const result = await add.run(city, state);
    if (!result) return;
    await mutate(result, { revalidate: false });
    setNewCity("");
    setNewState("");
    // Lets the user see the city they just added.
    setSearch("");
  }

  return (
    <Card
      title="Target cities"
      description="Cities the pipeline discovers leads in. Search to check whether a city is already added, or add a new one below."
    >
      {error && !data ? (
        <Notice tone="danger">{error.message}</Notice>
      ) : !data ? (
        <div className="space-y-3">
          <Skeleton className="h-10 w-full" />
          <Skeleton className="h-32 w-full" />
        </div>
      ) : (
        <div className="space-y-5">
          <div>
            <Field label="Search cities">
              {(id) => (
                <Input
                  id={id}
                  type="search"
                  placeholder="Type a city name to check or filter"
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                />
              )}
            </Field>
            <p className="mt-2 text-[13px] text-ink-mute" aria-live="polite">
              {query
                ? `${visible.length} of ${cities.length} cities match`
                : `${cities.length} ${cities.length === 1 ? "city" : "cities"} saved`}
            </p>
          </div>

          {visible.length > 0 ? (
            <ul className="max-h-72 divide-y divide-line overflow-y-auto rounded-lg border border-line">
              {visible.map((c) => (
                <li key={`${c.city}-${c.state}-${c.index}`} className="flex items-center justify-between gap-3 px-3 py-1.5">
                  <span className="flex min-w-0 items-center gap-2 text-sm">
                    <MapPin className="h-4 w-4 shrink-0 text-ink-mute" aria-hidden />
                    <span className="truncate">
                      {c.city}, {c.state}
                    </span>
                  </span>
                  <Button
                    variant="ghost"
                    size="sm"
                    icon={<X className="h-3.5 w-3.5" aria-hidden />}
                    loading={removingIndex === c.index}
                    disabled={remove.pending && removingIndex !== c.index}
                    onClick={() => onRemove(c.index)}
                    aria-label={`Remove ${c.city}, ${c.state}`}
                  >
                    Remove
                  </Button>
                </li>
              ))}
            </ul>
          ) : query ? (
            <p className="text-sm text-ink-soft">Not added yet. You can add it below.</p>
          ) : (
            <p className="text-sm text-ink-soft">No cities saved yet. Add your first one below.</p>
          )}

          <form onSubmit={onAdd} className="border-t border-line pt-5">
            <div className="flex flex-wrap items-start gap-4">
              <Field label="City name" className="w-full sm:w-64">
                {(id) => (
                  <Input id={id} placeholder="e.g. Phoenix" value={newCity} onChange={(e) => setNewCity(e.target.value)} />
                )}
              </Field>
              <Field label="State code" className="w-28">
                {(id) => (
                  <Input
                    id={id}
                    placeholder="e.g. AZ"
                    maxLength={2}
                    value={newState}
                    onChange={(e) => setNewState(e.target.value.toUpperCase())}
                  />
                )}
              </Field>
              <div className="pt-[27px]">
                <Button type="submit" variant="primary" icon={<Plus className="h-4 w-4" aria-hidden />} loading={add.pending}>
                  Add city
                </Button>
              </div>
            </div>
            {formError && (
              <p role="alert" className="mt-2 text-[13px] text-danger">
                {formError}
              </p>
            )}
          </form>
        </div>
      )}
    </Card>
  );
}
