"use client";

import React, { useEffect, useId, useRef, useState } from "react";
import { classifyError, searchPlaces } from "../utils/api";
import { useLang } from "../utils/LangContext";
import { useReportLimits } from "../utils/LimitsContext";

// U4 "Find my barangay": a combobox over /places/search. Arrow keys move, Enter picks, Esc closes.
export default function SearchBox({ onSelect, inputRef, highlight = false }) {
  const { t } = useLang();
  const uid = useId();
  const listId = `${uid}-list`;
  const [q, setQ] = useState("");
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(-1);
  const [res, setRes] = useState({ state: "idle", items: [], data: null, error: null });
  const timer = useRef(null);
  useReportLimits("search", t("search.label"), res.data);

  useEffect(() => {
    const term = q.trim();
    if (term.length < 2) {
      setRes({ state: "idle", items: [], data: null, error: null });
      return undefined;
    }
    let cancelled = false;
    setRes((r) => ({ ...r, state: "loading" }));
    clearTimeout(timer.current);
    timer.current = setTimeout(() => {
      searchPlaces(term, 8)
        .then((d) => {
          if (!cancelled) {
            setRes({ state: "ready", items: d.results ?? [], data: d, error: null });
            setActive((d.results ?? []).length ? 0 : -1);
          }
        })
        .catch((e) => {
          if (!cancelled) setRes({ state: classifyError(e), items: [], data: null, error: e });
        });
    }, 200);
    return () => {
      cancelled = true;
      clearTimeout(timer.current);
    };
  }, [q]);

  function pick(item) {
    if (!item) return;
    setOpen(false);
    setQ("");
    onSelect(item);
  }

  function onKeyDown(e) {
    const n = res.items.length;
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setOpen(true);
      if (n) setActive((a) => (a + 1) % n);
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      if (n) setActive((a) => (a <= 0 ? n - 1 : a - 1));
    } else if (e.key === "Enter") {
      if (open && active >= 0 && res.items[active]) {
        e.preventDefault();
        pick(res.items[active]);
      }
    } else if (e.key === "Escape") {
      if (open) {
        e.preventDefault();
        e.stopPropagation();
        setOpen(false);
      }
    }
  }

  const showList = open && q.trim().length >= 2;
  const detail = res.error?.detail && typeof res.error.detail === "object" ? res.error.detail.message : null;
  return (
    <div className="relative w-full">
      <label
        htmlFor={`${uid}-in`}
        className={`flex h-[46px] w-full items-center gap-2.5 rounded-xl border bg-white px-3.5 shadow-[0_2px_8px_rgba(20,30,40,0.12)] ${
          highlight ? "border-[#1E5B3A] ring-2 ring-[#1E5B3A]/30" : "border-[#DCE3DB]"
        }`}
      >
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#1E5B3A" strokeWidth="2.2" aria-hidden="true" className="shrink-0">
          <circle cx="11" cy="11" r="7" />
          <path d="M20 20l-4-4" />
        </svg>
        <span className="sr-only">{t("search.label")}</span>
        <input
          id={`${uid}-in`}
          ref={inputRef}
          type="search"
          role="combobox"
          aria-expanded={showList}
          aria-controls={listId}
          aria-autocomplete="list"
          aria-activedescendant={showList && active >= 0 ? `${uid}-opt-${active}` : undefined}
          autoComplete="off"
          value={q}
          placeholder={t("search.v2.placeholder")}
          onChange={(e) => {
            setQ(e.target.value);
            setOpen(true);
          }}
          onFocus={() => setOpen(true)}
          onBlur={() => setTimeout(() => setOpen(false), 120)}
          onKeyDown={onKeyDown}
          className="min-w-0 flex-1 border-0 bg-transparent text-[14px] text-[#16231B] placeholder:text-[#4A5850] focus:outline-none"
          data-testid="search-input"
        />
      </label>
      {showList && (
        <ul
          id={listId}
          role="listbox"
          aria-label={t("search.results")}
          className="absolute left-0 right-0 top-full z-[1500] mt-1.5 max-h-72 overflow-auto rounded-xl border border-[#DCE3DB] bg-white text-sm text-[#16231B] shadow-[0_6px_24px_rgba(20,30,40,0.14)]"
          data-testid="search-results"
        >
          {res.state === "loading" && <li className="px-3.5 py-2.5 text-xs text-[#4A5850]">{t("state.loading.title")}</li>}
          {res.state === "ready" && res.items.length === 0 && <li className="px-3.5 py-2.5 text-xs text-[#4A5850]">{t("search.none")}</li>}
          {["offline", "error", "upstream", "unavailable", "invalid"].includes(res.state) && (
            <li className="px-3.5 py-2.5 text-xs text-[#7A5B00]">
              {t(`state.${res.state}.title`)}. {detail ?? t(`state.${res.state}.body`)}
            </li>
          )}
          {res.items.map((r, i) => (
            <li
              key={r.id}
              id={`${uid}-opt-${i}`}
              role="option"
              aria-selected={i === active}
              onMouseDown={(e) => {
                e.preventDefault();
                pick(r);
              }}
              onMouseEnter={() => setActive(i)}
              className={`cursor-pointer px-3.5 py-2 text-[13px] ${i === active ? "bg-[#E3EFE7] text-[#123B25]" : "text-[#16231B] hover:bg-[#F2F5F1]"}`}
            >
              <span className="font-semibold">{r.name}</span>
              <span className="ml-2 text-xs text-[#4A5850]">
                {t(`search.level.${r.level}`)}
                {r.city && r.city !== r.name ? ` · ${r.city === r.province ? t("search.townOf", { town: r.city }) : r.city}` : ""}
                {r.province ? ` · ${r.province}` : ""}
                {r.inStudyArea === false ? ` · ${t("search.outside")}` : ""}
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
