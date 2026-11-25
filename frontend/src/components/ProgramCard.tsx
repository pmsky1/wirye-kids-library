"use client";

import React from "react";
import { CalendarIcon, ClockIcon, MapPinIcon, ExternalLinkIcon, SparklesIcon } from "./Icons";

export interface Program {
  id: string;
  source: string;
  library_name: string;
  region: string;
  title: string;
  target_age_group: string;
  target_label: string;
  target_raw: string;
  day_type?: string;
  day_label?: string;
  is_new?: boolean;
  is_expired?: boolean;
  fee: string;
  capacity?: string;
  apply_start?: string;
  apply_end?: string;
  event_start?: string;
  event_end?: string;
  event_time_info?: string;
  location?: string;
  status: string;
  status_label: string;
  detail_url: string;
  apply_url?: string;
}

interface ProgramCardProps {
  program: Program;
}

export default function ProgramCard({ program }: ProgramCardProps) {
  const isPreschool = program.target_age_group === "PRESCHOOL";
  const isApply = program.status === "APPLY";
  const isReady = program.status === "READY";
  const isWait = program.status === "WAIT";
  const isWeekend = program.day_type === "WEEKEND";
  const isNew = Boolean(program.is_new);
  const isExpired = Boolean(program.is_expired);

  // Clean title: remove repetitive library prefix (e.g., '거마', '글마루', '위례') and collapse newlines/tabs
  const cleanTitle = program.title
    .replace(/^(거마|글마루|위례|중앙|송파위례도서관|위례도서관)\s*/gi, "")
    .replace(/\s+/g, " ")
    .trim();

  // Clean target text: collapse multiple spaces and newlines
  const cleanTarget = (program.target_raw || "상세 공지 확인")
    .replace(/\s+/g, " ")
    .trim();

  // Clean location & time
  const cleanLocation = (program.location || "")
    .replace(/\s+/g, " ")
    .trim();

  const cleanTimeInfo = (program.event_time_info || "")
    .replace(/\s+/g, " ")
    .trim();

  const stripEmoji = (text?: string) =>
    (text || "").replace(/^[\p{Extended_Pictographic}\uFE0F\u200D\s]+/gu, "").trim();

  const cleanDayLabel = stripEmoji(program.day_label) || "주말";
  const cleanTargetLabel = stripEmoji(program.target_label) || cleanTarget;
  const cleanStatusLabel = stripEmoji(program.status_label);

  // Region color mapping
  const regionBadges: Record<string, { bg: string; text: string; border: string }> = {
    송파: { bg: "bg-indigo-50", text: "text-indigo-700", border: "border-indigo-100" },
    하남: { bg: "bg-emerald-50", text: "text-emerald-700", border: "border-emerald-100" },
    성남: { bg: "bg-amber-50", text: "text-amber-800", border: "border-amber-200" },
  };

  const currentRegion = regionBadges[program.region] || {
    bg: "bg-gray-50",
    text: "text-gray-700",
    border: "border-gray-200",
  };

  return (
    <div
      className={`relative flex flex-col justify-between p-4 rounded-2xl transition duration-150 hover:shadow-md ${
        isExpired
          ? "bg-gray-50/70 border border-gray-200 opacity-60 grayscale-[40%]"
          : isNew
          ? "bg-gradient-to-b from-violet-50/30 via-white to-white border border-violet-200 ring-1 ring-violet-400/20 shadow-sm"
          : isWeekend && isPreschool
          ? "border border-blue-200 ring-1 ring-blue-400/15 shadow-sm bg-white"
          : "border border-gray-200/90 shadow-sm bg-white"
      }`}
    >
      <div>
        {/* Top Badges Header: Clean Single-line row */}
        <div className="flex items-center justify-between gap-1.5 mb-2 text-[11px]">
          <div className="flex items-center gap-1.5 flex-wrap min-w-0">
            {/* NEW Badge */}
            {isNew && !isExpired && (
              <span className="whitespace-nowrap px-1.5 py-0.5 rounded-md text-[10px] font-black bg-gradient-to-r from-violet-600 to-fuchsia-600 text-white shadow-xs">
                NEW
              </span>
            )}

            {/* Weekend / Weekday Badge */}
            {isWeekend ? (
              <span className="whitespace-nowrap px-1.5 py-0.5 rounded-md text-[10px] font-black bg-blue-50 text-blue-700 border border-blue-200">
                {cleanDayLabel}
              </span>
            ) : null}

            {/* Institution Badge */}
            <span
              className={`whitespace-nowrap px-1.5 py-0.5 rounded-md text-[10px] font-bold border ${currentRegion.bg} ${currentRegion.text} ${currentRegion.border}`}
            >
              {program.library_name}
            </span>

            {/* Target Age Badge */}
            <span
              className={`whitespace-nowrap px-1.5 py-0.5 rounded-md text-[10px] font-bold border ${
                isPreschool
                  ? "bg-rose-50 text-rose-700 border-rose-200"
                  : program.target_age_group === "ELEMENTARY"
                  ? "bg-violet-50 text-violet-700 border-violet-200"
                  : program.target_age_group === "ALL" || program.target_age_group === "FAMILY"
                  ? "bg-teal-50 text-teal-700 border-teal-200"
                  : "bg-gray-50 text-gray-700 border-gray-200"
              }`}
            >
              {program.target_age_group === "ALL" ? "누구나" : cleanTargetLabel}
            </span>
          </div>

          {/* Status Badge */}
          <span
            className={`whitespace-nowrap shrink-0 px-2 py-0.5 rounded-full text-[11px] font-black ${
              isApply
                ? "bg-emerald-500 text-white shadow-xs"
                : isReady
                ? "bg-sky-500 text-white shadow-xs"
                : isWait
                ? "bg-orange-500 text-white shadow-xs"
                : "bg-gray-200 text-gray-500"
            }`}
          >
            {isApply ? "접수중" : isReady ? "접수예정" : isWait ? "대기접수" : cleanStatusLabel || "마감"}
          </span>
        </div>

        {/* Cleaned Title */}
        <h3
          className={`text-sm font-extrabold leading-snug line-clamp-2 transition ${
            isExpired
              ? "text-gray-400 line-through"
              : isNew
              ? "text-gray-900 hover:text-violet-600"
              : "text-gray-900 hover:text-blue-600"
          }`}
          title={cleanTitle}
        >
          {cleanTitle}
        </h3>

        {/* Target Details: Compact single-line text */}
        <p className="mt-1.5 text-[11px] text-gray-600 truncate">
          <span className="font-bold text-gray-700">대상:</span> {cleanTarget}
        </p>

        {/* Schedule & Timing: Compact 2 lines */}
        <div className="mt-2 space-y-1 text-[11px] text-gray-500">
          {(program.event_start || cleanTimeInfo) && (
            <div className={`flex items-center gap-1.5 ${isWeekend ? "text-blue-900 font-medium" : ""}`}>
              <CalendarIcon className={`w-3.5 h-3.5 shrink-0 ${isWeekend ? "text-blue-600" : "text-gray-400"}`} />
              <span className="truncate">
                {program.event_start ? `${program.event_start} ~ ${program.event_end || ""}` : ""}
                {cleanTimeInfo ? ` (${cleanTimeInfo})` : ""}
              </span>
            </div>
          )}

          {program.apply_start && (
            <div className="flex items-center gap-1.5 text-amber-800 font-medium">
              <ClockIcon className="w-3.5 h-3.5 text-amber-500 shrink-0" />
              <span className="truncate">
                접수: {program.apply_start} ~ {program.apply_end || ""}
              </span>
            </div>
          )}
        </div>
      </div>

      {/* Bottom Info & Action Buttons */}
      <div className="mt-3 pt-2.5 border-t border-gray-100">
        <div className="flex items-center justify-between text-[11px] mb-2 text-gray-500">
          <span>{program.capacity ? `정원: ${program.capacity}` : "정원제"}</span>
          <span className="font-bold text-emerald-700 bg-emerald-50 px-1.5 py-0.2 rounded border border-emerald-100">
            {program.fee || "무료"}
          </span>
        </div>

        <div className="grid grid-cols-2 gap-1.5">
          <a
            href={program.detail_url}
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center justify-center gap-1 py-1.5 px-2 rounded-xl bg-slate-100 hover:bg-slate-200 text-slate-700 text-xs font-bold border border-slate-200 transition active:scale-95 shadow-xs"
          >
            <span>상세안내</span>
            <ExternalLinkIcon className="w-3 h-3 text-slate-400" />
          </a>

          <a
            href={program.apply_url || program.detail_url}
            target="_blank"
            rel="noopener noreferrer"
            className={`flex items-center justify-center gap-1 py-1.5 px-2 rounded-xl text-xs font-black text-white transition shadow-xs active:scale-95 ${
              isApply
                ? "bg-emerald-600 hover:bg-emerald-700"
                : isReady
                ? "bg-amber-500 hover:bg-amber-600 text-white"
                : "bg-gray-800 hover:bg-gray-900"
            }`}
          >
            <span>{isApply ? "신청하기" : isReady ? "오픈예정" : "신청확인"}</span>
            <ExternalLinkIcon className="w-3 h-3" />
          </a>
        </div>
      </div>
    </div>
  );
}
