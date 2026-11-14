"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { translate } from "./i18n";

const Ctx = createContext(null);
const KEY = "tanaw.lang";

export function LangProvider({ children }) {
  const [lang, setLangState] = useState("en");

  useEffect(() => {
    let next = null;
    try {
      const fromUrl = new URLSearchParams(window.location.search).get("lang");
      if (fromUrl === "en" || fromUrl === "fil") next = fromUrl;
      else next = window.localStorage.getItem(KEY);
    } catch {
      /* storage blocked: stay on English */
    }
    if (next === "en" || next === "fil") setLangState(next);
  }, []);

  const setLang = useCallback((l) => {
    setLangState(l);
    try {
      window.localStorage.setItem(KEY, l);
    } catch {
      /* ignore */
    }
  }, []);

  useEffect(() => {
    document.documentElement.lang = lang === "fil" ? "fil" : "en";
  }, [lang]);

  const t = useCallback((key, vars) => translate(lang, key, vars), [lang]);
  const value = useMemo(() => ({ lang, setLang, t }), [lang, setLang, t]);
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useLang() {
  const v = useContext(Ctx);
  if (v) return v;
  return { lang: "en", setLang: () => {}, t: (k, vars) => translate("en", k, vars) };
}
