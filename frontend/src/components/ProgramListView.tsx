"use client";

import React from "react";
import { Program } from "./ProgramCard";
import {
  ExternalLinkIcon,
  CalendarIcon,
  ClockIcon,
  ArrowsUpDownIcon,
  SortAscIcon,
  SortDescIcon,
} from "./Icons";

interface ProgramListViewProps {
  programs: Program[];
  sortBy?: "default" | "event_date" | "apply_date";
  sortOrder?: "asc" | "desc";
  onSortChange?: (field: "event_date" | "apply_date") => void;
}

export default function ProgramListView({
  programs,
  sortBy = "default",
  sortOrder = "asc",
  onSortChange,
}: ProgramListViewProps) {
  if (programs.length === 0) return null;

  return (
    <div className="bg-white rounded-3xl border border-gray-200/90 shadow-sm overflow-x-clip">
      {/* Desktop Table Header (Sticky below top navbar) */}
      <div className="hidden lg:grid sticky top-14 z-20 rounded-t-3xl grid-cols-12 gap-3 px-5 py-3.5 bg-slate-50/95 backdrop-blur-sm border-b border-gray-200 text-xs font-black text-gray-500 uppercase tracking-wider items-center select-none shadow-xs">
        <div className="col-span-2">상태 / 신규</div>
        <div className="col-span-2">도서관 (권역)</div>
        <div className="col-span-4">프로그램명 / 대상 연령</div>

        {/* Sortable Column: 행사 일정 / 요일 */}
        <div className="col-span-2">
          <button
            type="button"
            onClick={() => onSortChange && onSortChange("event_date")}
            className={`flex items-center gap-1.5 px-2.5 py-1 -mx-2.5 rounded-xl transition font-black text-left w-full group ${
              sortBy === "event_date"
                ? "bg-blue-100 text-blue-900 ring-1 ring-blue-300"
                : "hover:bg-slate-200/80 hover:text-gray-900"
            }`}
            title="클릭하여 행사 일정 기준 빠른순/늦은순으로 정렬합니다"
          >
            <span>행사 일정 / 요일</span>
            {sortBy === "event_date" ? (
              sortOrder === "asc" ? (
                <span className="flex items-center gap-0.5 text-[10px] text-blue-700 font-extrabold bg-blue-200/70 px-1.5 py-0.2 rounded-md">
                  <SortAscIcon className="w-3 h-3" /> 빠른순
                </span>
              ) : (
                <span className="flex items-center gap-0.5 text-[10px] text-blue-700 font-extrabold bg-blue-200/70 px-1.5 py-0.2 rounded-md">
                  <SortDescIcon className="w-3 h-3" /> 늦은순
                </span>
              )
            ) : (
              <ArrowsUpDownIcon className="w-3 h-3 text-gray-400 group-hover:text-gray-600 shrink-0" />
            )}
          </button>
        </div>

        {/* Sortable Column: 접수 기간 / 신청 */}
        <div className="col-span-2 flex justify-end">
          <button
            type="button"
            onClick={() => onSortChange && onSortChange("apply_date")}
            className={`flex items-center gap-1.5 px-2.5 py-1 -mx-2.5 rounded-xl transition font-black group ${
              sortBy === "apply_date"
                ? "bg-amber-100 text-amber-900 ring-1 ring-amber-300"
                : "hover:bg-slate-200/80 hover:text-gray-900"
            }`}
            title="클릭하여 접수 시작일 기준 빠른순/늦은순으로 정렬합니다"
          >
            <span>접수 기간 / 신청</span>
            {sortBy === "apply_date" ? (
              sortOrder === "asc" ? (
                <span className="flex items-center gap-0.5 text-[10px] text-amber-800 font-extrabold bg-amber-200/70 px-1.5 py-0.2 rounded-md">
                  <SortAscIcon className="w-3 h-3" /> 빠른순
                </span>
              ) : (
                <span className="flex items-center gap-0.5 text-[10px] text-amber-800 font-extrabold bg-amber-200/70 px-1.5 py-0.2 rounded-md">
                  <SortDescIcon className="w-3 h-3" /> 늦은순
                </span>
              )
            ) : (
              <ArrowsUpDownIcon className="w-3 h-3 text-gray-400 group-hover:text-gray-600 shrink-0" />
            )}
          </button>
        </div>
      </div>

      {/* Rows */}
      <div className="divide-y divide-gray-100 rounded-b-3xl overflow-hidden">
        {programs.map((program) => {
          const isApply = program.status === "APPLY";
          const isReady = program.status === "READY";
          const isWait = program.status === "WAIT";
          const isWeekend = program.day_type === "WEEKEND";
          const isNew = Boolean(program.is_new);
          const isExpired = Boolean(program.is_expired);
          const isPreschool = program.target_age_group === "PRESCHOOL";

          const cleanTitle = program.title
            .replace(/^(거마|글마루|위례|중앙|송파위례도서관|위례도서관)\s*/gi, "")
            .replace(/\s+/g, " ")
            .trim();

          const cleanTarget = (program.target_raw || "상세 공지 확인")
            .replace(/\s+/g, " ")
            .trim();

          // Region badge color
          const regionColor: Record<string, string> = {
            송파: "bg-indigo-50 text-indigo-700 border-indigo-200",
            하남: "bg-emerald-50 text-emerald-700 border-emerald-200",
            성남: "bg-amber-50 text-amber-800 border-amber-200",
          };

          return (
            <div
              key={program.id}
              className={`p-4 lg:px-5 lg:py-3 transition duration-150 hover:bg-slate-50/80 ${
                isExpired
                  ? "bg-gray-50/60 opacity-60 grayscale-[30%]"
                  : isApply
                  ? "bg-emerald-50/15"
                  : isNew
                  ? "bg-violet-50/15"
                  : ""
              }`}
            >
              {/* Desktop Row Grid */}
              <div className="hidden lg:grid grid-cols-12 gap-3 items-center text-xs">
                {/* 1. Status & NEW (col-span-2) */}
                <div className="col-span-2 flex items-center gap-1.5 flex-wrap">
                  <span
                    className={`whitespace-nowrap px-2.5 py-1 rounded-full text-[11px] font-black border ${
                      isApply
                        ? "bg-emerald-50 text-emerald-700 border-emerald-300"
                        : isReady
                        ? "bg-amber-50 text-amber-800 border-amber-300"
                        : isWait
                        ? "bg-yellow-50 text-yellow-800 border-yellow-300"
                        : "bg-gray-100 text-gray-600 border-gray-200"
                    }`}
                  >
                    {isApply ? "⚡ 접수중" : isReady ? "⏰ 접수예정" : isWait ? "⏳ 대기접수" : "마감"}
                  </span>

                  {isNew && !isExpired && (
                    <span className="whitespace-nowrap px-2 py-0.5 rounded-md text-[10px] font-black bg-gradient-to-r from-violet-600 to-fuchsia-600 text-white shadow-sm">
                      ✨ NEW
                    </span>
                  )}
                </div>

                {/* 2. Library & Region (col-span-2) */}
                <div className="col-span-2 flex items-center gap-1.5 min-w-0">
                  <span
                    className={`whitespace-nowrap px-1.5 py-0.5 rounded text-[10px] font-bold border ${
                      regionColor[program.region] || "bg-gray-100 text-gray-700 border-gray-200"
                    }`}
                  >
                    {program.region}
                  </span>
                  <span className="font-extrabold text-gray-800 truncate" title={program.library_name}>
                    {program.library_name}
                  </span>
                </div>

                {/* 3. Title & Target Age (col-span-4) */}
                <div className="col-span-4 min-w-0 pr-2">
                  <div className="flex items-center gap-1.5 flex-wrap mb-0.5">
                    <span
                      className={`whitespace-nowrap px-2 py-0.5 rounded-full text-[10px] font-extrabold ${
                        isPreschool
                          ? "bg-rose-100 text-rose-800"
                          : program.target_age_group === "ELEMENTARY"
                          ? "bg-violet-100 text-violet-800"
                          : program.target_age_group === "ALL" || program.target_age_group === "FAMILY"
                          ? "bg-teal-100 text-teal-800"
                          : "bg-blue-50 text-blue-800"
                      }`}
                    >
                      {program.target_age_group === "ALL" ? "🌟 누구나" : program.target_label || cleanTarget}
                    </span>
                    {isWeekend && (
                      <span className="whitespace-nowrap px-2 py-0.5 rounded-full text-[10px] font-extrabold bg-blue-100 text-blue-900 border border-blue-200">
                        🎉 주말
                      </span>
                    )}
                  </div>
                  <a
                    href={program.detail_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="font-black text-gray-900 hover:text-blue-600 transition truncate block text-sm"
                    title={cleanTitle}
                  >
                    {cleanTitle}
                  </a>
                </div>

                {/* 4. Event Date & Time (col-span-2) */}
                <div className="col-span-2 text-gray-600 space-y-0.5 min-w-0">
                  <div className="flex items-center gap-1 text-[11px] font-semibold text-gray-800">
                    <CalendarIcon className="w-3.5 h-3.5 text-blue-600 shrink-0" />
                    <span className="truncate">
                      {program.event_start
                        ? program.event_end && program.event_end !== program.event_start
                          ? `${program.event_start} ~ ${program.event_end.slice(5)}`
                          : program.event_start
                        : "일정 공지 참조"}
                    </span>
                  </div>
                  {program.event_time_info && (
                    <div className="flex items-center gap-1 text-[10px] text-gray-500">
                      <ClockIcon className="w-3 h-3 text-gray-400 shrink-0" />
                      <span className="truncate">{program.event_time_info}</span>
                    </div>
                  )}
                </div>

                {/* 5. Apply Period & Action (col-span-2) */}
                <div className="col-span-2 flex items-center justify-end gap-2.5">
                  <div className="text-right min-w-0">
                    <div className="text-[10px] font-bold text-amber-700 flex items-center justify-end gap-1">
                      <ClockIcon className="w-3 h-3 text-amber-500 shrink-0" />
                      <span>접수기간</span>
                    </div>
                    <div className="text-[11px] font-bold text-gray-800 whitespace-nowrap" title={`${program.apply_start || ""} ~ ${program.apply_end || ""}`}>
                      {program.apply_start ? (
                        <span>
                          {program.apply_start.slice(5, 10)}
                          {program.apply_end ? ` ~ ${program.apply_end.slice(5, 10)}` : "~"}
                        </span>
                      ) : (
                        "상세참조"
                      )}
                    </div>
                  </div>

                  <a
                    href={program.apply_url || program.detail_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className={`whitespace-nowrap px-3 py-1.5 rounded-xl text-xs font-black text-white transition flex items-center gap-1 shadow-xs ${
                      isApply
                        ? "bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-700 hover:to-teal-700 shadow-emerald-600/25"
                        : isReady
                        ? "bg-gradient-to-r from-amber-500 to-orange-500 hover:from-amber-600 hover:to-orange-600"
                        : "bg-gray-700 hover:bg-gray-800"
                    }`}
                  >
                    <span>{isApply ? "신청" : isReady ? "대기" : "확인"}</span>
                    <ExternalLinkIcon className="w-3 h-3" />
                  </a>
                </div>
              </div>

              {/* Mobile / Tablet Compact Card Row */}
              <div className="lg:hidden space-y-2">
                <div className="flex items-center justify-between gap-2">
                  <div className="flex items-center gap-1.5 flex-wrap">
                    <span
                      className={`whitespace-nowrap px-2 py-0.5 rounded-full text-[10px] font-black border ${
                        isApply
                          ? "bg-emerald-50 text-emerald-700 border-emerald-300"
                          : isReady
                          ? "bg-amber-50 text-amber-800 border-amber-300"
                          : isWait
                          ? "bg-yellow-50 text-yellow-800 border-yellow-300"
                          : "bg-gray-100 text-gray-600 border-gray-200"
                      }`}
                    >
                      {isApply ? "⚡ 접수중" : isReady ? "⏰ 접수예정" : isWait ? "⏳ 대기접수" : "마감"}
                    </span>

                    {isNew && !isExpired && (
                      <span className="whitespace-nowrap px-1.5 py-0.5 rounded text-[10px] font-black bg-gradient-to-r from-violet-600 to-fuchsia-600 text-white">
                        ✨ NEW
                      </span>
                    )}

                    <span
                      className={`whitespace-nowrap px-1.5 py-0.5 rounded text-[10px] font-bold border ${
                        regionColor[program.region] || "bg-gray-100 text-gray-700 border-gray-200"
                      }`}
                    >
                      {program.region}
                    </span>
                    <span className="text-xs font-bold text-gray-700 truncate">
                      {program.library_name}
                    </span>
                  </div>

                  {isWeekend && (
                    <span className="whitespace-nowrap px-2 py-0.5 rounded-full text-[10px] font-extrabold bg-blue-100 text-blue-900 border border-blue-200">
                      🎉 주말
                    </span>
                  )}
                </div>

                <a
                  href={program.detail_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="font-black text-gray-900 hover:text-blue-600 transition block text-sm leading-snug"
                >
                  {cleanTitle}
                </a>

                {/* Bottom Row: Clear Apply Period & Event Schedule + Action Button */}
                <div className="flex items-center justify-between text-xs pt-2 border-t border-gray-100 gap-2">
                  <div className="space-y-0.5 min-w-0 flex-1">
                    {/* 1. 접수 기간 (학부모에게 가장 중요한 정보 강조) */}
                    {program.apply_start ? (
                      <div className="flex items-center gap-1 text-[11px] font-bold text-amber-800 truncate">
                        <ClockIcon className="w-3.5 h-3.5 text-amber-500 shrink-0" />
                        <span>
                          접수: {program.apply_start.slice(0, 16)}
                          {program.apply_end ? ` ~ ${program.apply_end.slice(5, 16)}` : ""}
                        </span>
                      </div>
                    ) : (
                      <div className="flex items-center gap-1 text-[11px] text-gray-500 truncate">
                        <ClockIcon className="w-3.5 h-3.5 text-gray-400 shrink-0" />
                        <span>접수: 상세 일정 참조</span>
                      </div>
                    )}

                    {/* 2. 행사 일정 및 대상 */}
                    <div className="flex items-center gap-1.5 text-[10px] text-gray-500 truncate">
                      <CalendarIcon className="w-3 h-3 text-blue-500 shrink-0" />
                      <span>
                        행사:{" "}
                        {program.event_start
                          ? program.event_end && program.event_end !== program.event_start
                            ? `${program.event_start} ~ ${program.event_end.slice(5)}`
                            : program.event_start
                          : "상세 공지"}
                      </span>
                      <span className="text-gray-300">|</span>
                      <span className="font-semibold text-rose-700">
                        {program.target_age_group === "ALL" ? "🌟 누구나" : program.target_label || cleanTarget}
                      </span>
                    </div>
                  </div>

                  {/* Action Button */}
                  <a
                    href={program.apply_url || program.detail_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className={`whitespace-nowrap px-3 py-1.5 rounded-xl text-xs font-black text-white transition flex items-center gap-1 shrink-0 shadow-xs active:scale-95 ${
                      isApply
                        ? "bg-emerald-600 hover:bg-emerald-700"
                        : isReady
                        ? "bg-amber-500 hover:bg-amber-600"
                        : "bg-gray-700 hover:bg-gray-800"
                    }`}
                  >
                    <span>{isApply ? "원클릭 신청" : "상세보기"}</span>
                    <ExternalLinkIcon className="w-3 h-3" />
                  </a>
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
