"use client";
import { useEffect, useState } from "react";

// true from the first render in which `cond` was true, and stays true. Used to load a mode's data the
// first time the mode opens and then keep it, so switching tabs does not refetch.
export default function useLatched(cond) {
  const [on, setOn] = useState(Boolean(cond));
  useEffect(() => {
    if (cond) setOn(true);
  }, [cond]);
  return on || Boolean(cond);
}
