"use client";

import { useCallback, useRef, useState } from "react";
import { toast } from "sonner";
import { ApiError } from "./api";

interface Options<R> {
  /** Toast text (or a function of the result) shown on success. */
  success?: string | ((result: R) => string);
  /** Prefix for the error toast, e.g. "Couldn't save the template". */
  errorTitle?: string;
}

/**
 * Wraps one button's async action with its OWN pending state.
 * Only the component that calls this re-renders into a loading state —
 * nothing else on the page is blocked (the whole point of leaving Streamlit).
 *
 *   const save = useAction(api.saveSendingWindow, { success: "Sending window saved" });
 *   <Button loading={save.pending} onClick={() => save.run(8, 22)}>Save</Button>
 */
export function useAction<A extends unknown[], R>(
  fn: (...args: A) => Promise<R>,
  options: Options<R> = {},
) {
  const [pending, setPending] = useState(false);
  const fnRef = useRef(fn);
  fnRef.current = fn;
  const optsRef = useRef(options);
  optsRef.current = options;

  const run = useCallback(async (...args: A): Promise<R | undefined> => {
    setPending(true);
    try {
      const result = await fnRef.current(...args);
      const s = optsRef.current.success;
      if (s) toast.success(typeof s === "function" ? s(result) : s);
      return result;
    } catch (e) {
      const message = e instanceof ApiError || e instanceof Error ? e.message : "Something went wrong";
      const title = optsRef.current.errorTitle;
      toast.error(title ? `${title}: ${message}` : message, { duration: 8000 });
      return undefined;
    } finally {
      setPending(false);
    }
  }, []);

  return { run, pending };
}
