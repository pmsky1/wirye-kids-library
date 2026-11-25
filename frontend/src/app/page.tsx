"use client";

import React, { useState, useEffect, useMemo } from "react";
import ProgramCard, { Program } from "@/components/ProgramCard";
import ProgramListView from "@/components/ProgramListView";
import BookmarkletModal from "@/components/BookmarkletModal";
import CrawlerHealthModal from "@/components/CrawlerHealthModal";
import {
  SparklesIcon,
  SearchIcon,
  RefreshIcon,
  BookmarkIcon,
  CheckCircleIcon,
  AlertCircleIcon,
  CalendarIcon,
  MapPinIcon,
  GridIcon,
  ListIcon,
  SortAscIcon,
  SortDescIcon,
} from "@/components/Icons";

const API_BASE = "http://localhost:8000";
const IS_STATIC = process.env.NEXT_PUBLIC_STATIC_MODE === "true";
const BASE_PATH = process.env.NEXT_PUBLIC_BASE_PATH || "";

const matchesAgeFilter = (p: Program, ageFilter: string): boolean => {
  if (ageFilter === "ALL") return true;
  if (ageFilter === "OPEN") {
    return p.target_age_group === "ALL" || p.target_age_group === "FAMILY";
  }
  // '누구나'(ALL) 및 '가족/보호자 동반'(FAMILY) 프로그램은 유아/초등 어느 필터에서도 함께 노출
  if (p.target_age_group === "ALL" || p.target_age_group === "FAMILY") {
    return true;
  }
  if (p.target_age_group === ageFilter) return true;

  // 유아~초등 연령대를 모두 아우르는 경우(예: 4~9세, 7세~2학년, 6세~초6) 양쪽 필터에 모두 노출
  const combined = `${p.target_raw || ""} ${p.title || ""}`.toLowerCase();
  if (ageFilter === "ELEMENTARY" && p.target_age_group === "PRESCHOOL") {
    return /(?:초등|초\s*[1-6]|(?:^|[^\d])[1-6]학년|(?:^|[^\d])(?:8|9|10|11|12|13)세|201[4-8]년생)/.test(combined);
  }
  if (ageFilter === "PRESCHOOL" && p.target_age_group === "ELEMENTARY") {
    return /(?:유아|유치|미취학|(?:^|[^\d])[4-7]세|202[0-3]년생)/.test(combined);
  }
  return false;
};

interface StatsData {
  generated_at?: string;
  total: number;
  active_total?: number;
  new_count?: number;
  expired_count?: number;
  preschool_count: number;
  infant_count: number;
  elementary_count: number;
  family_count: number;
  apply_count: number;
  ready_count: number;
  weekend_count?: number;
  weekday_count?: number;
  crawler_logs?: Array<{
    source: string;
    library_name: string;
    last_attempt_at: string;
    last_success_at: string | null;
    status: string;
    item_count: number;
    error_message: string | null;
  }>;
}

export default function Home() {
  const [programs, setPrograms] = useState<Program[]>([]);
  const [stats, setStats] = useState<StatsData | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  // Filters: default to WEEKEND, PRESCHOOL, and hide expired programs!
  const [selectedDayType, setSelectedDayType] = useState<string>("WEEKEND");
  const [selectedAge, setSelectedAge] = useState<string>("PRESCHOOL");
  const [selectedRegion, setSelectedRegion] = useState<string>("ALL");
  const [selectedLibrary, setSelectedLibrary] = useState<string>("ALL");
  const [selectedStatus, setSelectedStatus] = useState<string>("ALL");
  const [searchQuery, setSearchQuery] = useState<string>("");
  const [onlyNew, setOnlyNew] = useState<boolean>(false);
  const [includeExpired, setIncludeExpired] = useState<boolean>(false);
  const [viewMode, setViewMode] = useState<"card" | "list">("card");
  const [sortBy, setSortBy] = useState<"default" | "event_date" | "apply_date">("default");
  const [sortOrder, setSortOrder] = useState<"asc" | "desc">("asc");

  const handleSortChange = (field: "event_date" | "apply_date") => {
    if (sortBy === field) {
      setSortOrder((prev) => (prev === "asc" ? "desc" : "asc"));
    } else {
      setSortBy(field);
      setSortOrder("asc");
    }
  };

  // Client-only clock to avoid Next.js Cache Components prerender warning on new Date()
  const [clientClock, setClientClock] = useState<{ todayStr: string; nowTimeStr: string } | null>(null);

  // Load view mode from localStorage & initialize client clock on mount
  useEffect(() => {
    const now = new Date();
    const pad = (n: number) => String(n).padStart(2, "0");
    const todayStr = `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`;
    const nowTimeStr = `${todayStr} ${pad(now.getHours())}:${pad(now.getMinutes())}`;
    setClientClock({ todayStr, nowTimeStr });

    if (typeof window !== "undefined") {
      const saved = localStorage.getItem("wirye_kids_view_mode");
      if (saved === "list" || saved === "card") {
        setViewMode(saved);
      }
    }
  }, []);

  const handleChangeViewMode = (mode: "card" | "list") => {
    setViewMode(mode);
    if (typeof window !== "undefined") {
      localStorage.setItem("wirye_kids_view_mode", mode);
    }
  };

  // Modals
  const [isBookmarkletOpen, setIsBookmarkletOpen] = useState(false);
  const [isHealthOpen, setIsHealthOpen] = useState(false);

  // Fetch data
  const fetchData = async (cacheBust = false) => {
    try {
      setLoading(true);
      const q = cacheBust ? `?t=${Date.now()}` : "";
      const [progsRes, statsRes] = IS_STATIC
        ? await Promise.all([
            fetch(`${BASE_PATH}/data/programs.json${q}`),
            fetch(`${BASE_PATH}/data/stats.json${q}`),
          ])
        : await Promise.all([
            fetch(`${API_BASE}/api/programs?include_expired=${includeExpired}`),
            fetch(`${API_BASE}/api/stats`),
          ]);

      if (progsRes.ok) {
        const pdata = await progsRes.json();
        setPrograms(pdata.programs || []);
      }
      if (statsRes.ok) {
        const sdata = await statsRes.json();
        setStats(sdata);
      }
    } catch (e) {
      console.error("API Fetch Error:", e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, [includeExpired]);

  const handleManualRefresh = async () => {
    try {
      setRefreshing(true);
      if (IS_STATIC) {
        await fetchData(true);
        setRefreshing(false);
        return;
      }
      await fetch(`${API_BASE}/api/refresh`, { method: "POST" });
      setTimeout(async () => {
        await fetchData();
        setRefreshing(false);
      }, 3000);
    } catch (e) {
      setRefreshing(false);
    }
  };

  // Short library display name for compact UI chips
  const shortenLibraryName = (name: string) => {
    return name
      .replace(/^송파어린이영어도서관$/, "어린이영어")
      .replace(/^송파글마루도서관$/, "글마루")
      .replace(/^송파어린이도서관$/, "어린이도서관")
      .replace(/^송파위례도서관$/, "송파위례")
      .replace(/^성남위례도서관$/, "성남위례")
      .replace(/^송파어린이문화회관$/, "어린이문화회관")
      .replace(/^위례교육센터\(영어캠프\)$/, "위례영어캠프")
      .replace(/^위례교육센터\(송파런\)$/, "위례송파런")
      .replace(/^헤드교육센터\(송파런\)$/, "헤드교육센터")
      .replace(/^풍납교육센터\(송파런\)$/, "풍납교육센터")
      .replace(/^송파진로체험지원센터$/, "진로체험센터")
      .replace(/^가든파이브\(송파구\)$/, "가든파이브")
      .replace(/^소나무언덕2호도서관$/, "소나무2호")
      .replace(/^소나무언덕3호도서관$/, "소나무3호")
      .replace(/^소나무언덕4호도서관$/, "소나무4호")
      .replace(/^송이골작은도서관$/, "송이골")
      .replace(/^소나무언덕잠실본동도서관$/, "잠실본동")
      .replace(/^잠실본동도서관$/, "잠실본동")
      .replace(/^송파런 영어캠프$/, "송파런 영어")
      .replace(/^잠실청소년센터$/, "잠실청소년")
      .replace(/^송파청소년센터$/, "송파청소년")
      .replace(/^오금청소년센터$/, "오금청소년")
      .replace(/^마천청소년센터$/, "마천청소년")
      .replace(/^송파문화예술회관$/, "문화예술회관")
      .replace(/^석촌호수 아뜰리에$/, "아뜰리에")
      .replace(/^송파구립민속예술단$/, "민속예술단")
      .replace(/^송파소식\(송파구청\)$/, "송파소식")
      .replace(/^거마도서관$/, "거마")
      .replace(/^하남위례도서관$/, "하남위례")
      .replace(/도서관$/, "");
  };

  // Available institutions/libraries based on the selected region
  const availableLibraries = useMemo(() => {
    const counts: Record<string, number> = {};
    programs.forEach((p) => {
      if (!includeExpired) {
        if (p.is_expired || p.status === "CLOSED") return;
        if (clientClock) {
          const applyEnd = (p.apply_end || "").trim();
          if (applyEnd.length >= 16 && applyEnd.slice(0, 16) < clientClock.nowTimeStr) return;
          if (applyEnd.length === 10 && applyEnd < clientClock.todayStr) return;
          const eventEnd = (p.event_end || p.event_start || "").trim();
          if (eventEnd.length >= 10 && eventEnd.slice(0, 10) < clientClock.todayStr) return;
        }
      }
      if (selectedRegion === "ALL" || p.region === selectedRegion) {
        counts[p.library_name] = (counts[p.library_name] || 0) + 1;
      }
    });

    return Object.entries(counts)
      .map(([name, count]) => ({ name, count }))
      .sort((a, b) => b.count - a.count);
  }, [programs, selectedRegion, includeExpired, clientClock]);

  // Filtered and Sorted list (⚡ 지금 접수 가능한 것 최우선 정렬!)
  const filteredPrograms = useMemo(() => {
    const list = programs.filter((p) => {
      // 0. 마감/만료 강좌 및 접수기간이 지난 강좌는 기본 화면에서 원천 제외
      if (!includeExpired) {
        if (p.is_expired || p.status === "CLOSED") return false;
        if (clientClock) {
          const applyEnd = (p.apply_end || "").trim();
          if (applyEnd.length >= 16 && applyEnd.slice(0, 16) < clientClock.nowTimeStr) return false;
          if (applyEnd.length === 10 && applyEnd < clientClock.todayStr) return false;
          const eventEnd = (p.event_end || p.event_start || "").trim();
          if (eventEnd.length >= 10 && eventEnd.slice(0, 10) < clientClock.todayStr) return false;
        }
      }
      // 1. Only NEW filter if toggled
      if (onlyNew && !p.is_new) {
        return false;
      }
      // 2. Day Type filter (WEEKEND / WEEKDAY / ALL)
      if (selectedDayType !== "ALL" && p.day_type !== selectedDayType) {
        return false;
      }
      // 3. Age Group filter (누구나/가족 동반 및 겸용 연령대는 유아/초등 모두 포함)
      if (!matchesAgeFilter(p, selectedAge)) {
        return false;
      }
      // 4. Region filter
      if (selectedRegion !== "ALL" && p.region !== selectedRegion) {
        return false;
      }
      // 4-1. Specific Institution (Library/Facility) filter
      if (selectedLibrary !== "ALL" && p.library_name !== selectedLibrary) {
        return false;
      }
      // 5. Status filter
      if (selectedStatus !== "ALL" && p.status !== selectedStatus) {
        return false;
      }
      // 6. Keyword Search
      if (searchQuery.trim()) {
        const q = searchQuery.toLowerCase();
        const matchesTitle = p.title.toLowerCase().includes(q);
        const matchesTarget = (p.target_raw || "").toLowerCase().includes(q);
        const matchesLib = p.library_name.toLowerCase().includes(q);
        if (!matchesTitle && !matchesTarget && !matchesLib) return false;
      }
      return true;
    });

    // 상태 우선순위 가중치:
    // 1순위: APPLY (⚡ 지금 즉시 접수중! 지금 바로 신청 가능한 것)
    // 2순위: READY (⏰ 접수예정, 조만간 열릴 것)
    // 3순위: WAIT (⏳ 대기접수)
    // 4순위: CLOSED / 기타 (마감/종료)
    const getStatusWeight = (status: string) => {
      switch (status) {
        case "APPLY":
          return 1;
        case "READY":
          return 2;
        case "WAIT":
          return 3;
        default:
          return 4;
      }
    };

    const isPeriodProgram = (p: Program) => {
      const start = (p.event_start || "").slice(0, 10);
      const end = (p.event_end || "").slice(0, 10);
      // 일정 기간(시작~종료가 다른 다일 행사/강좌) 또는 특정 날짜 없는 상시/정기 운영을 후순위 배치
      return !start || Boolean(end && start !== end);
    };

    return list.sort((a, b) => {
      // 1. 날짜별 사용자 선택 정렬 (행사일순 / 접수일순)
      if (sortBy === "event_date") {
        const periodDiff = Number(isPeriodProgram(a)) - Number(isPeriodProgram(b));
        if (periodDiff !== 0) return sortOrder === "asc" ? periodDiff : -periodDiff;
        const dateA = a.event_start || "9999-99-99";
        const dateB = b.event_start || "9999-99-99";
        if (dateA !== dateB) {
          return sortOrder === "asc" ? dateA.localeCompare(dateB) : dateB.localeCompare(dateA);
        }
        const wA = getStatusWeight(a.status);
        const wB = getStatusWeight(b.status);
        return wA - wB;
      }

      if (sortBy === "apply_date") {
        const dateA = a.apply_start || "9999-99-99";
        const dateB = b.apply_start || "9999-99-99";
        if (dateA !== dateB) {
          return sortOrder === "asc" ? dateA.localeCompare(dateB) : dateB.localeCompare(dateA);
        }
        const wA = getStatusWeight(a.status);
        const wB = getStatusWeight(b.status);
        return wA - wB;
      }

      // 2. 기본 추천 정렬 (접수중/예정 우선 -> 단일일 우선/일정기간 후순위 -> 2일 신규 -> 주말 -> 행사일/접수일순)
      const wA = getStatusWeight(a.status);
      const wB = getStatusWeight(b.status);
      if (wA !== wB) return wA - wB;

      // 일정 기간(장기 강좌, 전시, 방학 특강 등)은 단일 행사일 아래에 배치
      const periodDiff = Number(isPeriodProgram(a)) - Number(isPeriodProgram(b));
      if (periodDiff !== 0) return periodDiff;

      // 신규 업데이트 등록 강좌 우선
      const newA = a.is_new ? 1 : 0;
      const newB = b.is_new ? 1 : 0;
      if (newA !== newB) return newB - newA;

      // 주말 프로그램 우선
      const weekendA = a.day_type === "WEEKEND" ? 1 : 0;
      const weekendB = b.day_type === "WEEKEND" ? 1 : 0;
      if (weekendA !== weekendB) return weekendB - weekendA;

      // 다가오는 행사일 / 신청 시작일 오름차순
      const eventA = a.event_start || "9999-99-99";
      const eventB = b.event_start || "9999-99-99";
      if (eventA !== eventB) return eventA.localeCompare(eventB);
      if (a.apply_start && b.apply_start) {
        return a.apply_start.localeCompare(b.apply_start);
      }
      return 0;
    });
  }, [programs, includeExpired, clientClock, onlyNew, selectedDayType, selectedAge, selectedRegion, selectedLibrary, selectedStatus, searchQuery, sortBy, sortOrder]);

  // Check overall crawler status
  const isAllCrawlersOk = useMemo(() => {
    if (!stats?.crawler_logs || stats.crawler_logs.length === 0) return true;
    return stats.crawler_logs.every((l) => l.status === "OK");
  }, [stats]);

  // Count active new programs
  const newProgramsCount = useMemo(() => {
    return programs.filter((p) => p.is_new && !p.is_expired).length;
  }, [programs]);

  // Handle preset card click: independently toggles each filter for multi-selection
  const handleCardClick = (preset: "NEW" | "WEEKEND" | "PRESCHOOL" | "APPLY") => {
    if (preset === "NEW") {
      setOnlyNew((prev) => !prev);
    } else if (preset === "WEEKEND") {
      setSelectedDayType((prev) => (prev === "WEEKEND" ? "ALL" : "WEEKEND"));
    } else if (preset === "PRESCHOOL") {
      setSelectedAge((prev) => (prev === "PRESCHOOL" ? "ALL" : "PRESCHOOL"));
    } else if (preset === "APPLY") {
      setSelectedStatus((prev) => (prev === "APPLY" ? "ALL" : "APPLY"));
    }
  };

  return (
    <div className="min-h-screen bg-slate-50 text-gray-900 selection:bg-amber-100">
      {/* Top Navbar: Clean & Premium Branding */}
      <header className="sticky top-0 z-30 bg-white/90 backdrop-blur-md border-b border-gray-200">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 h-14 flex items-center justify-between">
          <div className="flex items-center gap-3">
            {/* Brand Logo Symbol */}
            <div className="w-8 h-8 rounded-xl bg-gradient-to-tr from-blue-600 via-indigo-600 to-violet-600 text-white flex items-center justify-center shadow-sm shadow-indigo-500/25">
              <SparklesIcon className="w-4 h-4 text-cyan-200" />
            </div>
            <div className="flex items-baseline gap-2">
              <span className="text-lg font-black tracking-tight text-gray-950 font-sans">
                WiKids<span className="text-blue-600 font-extrabold text-sm ml-1">위키즈</span>
              </span>
              <span className="hidden sm:inline-block text-[11px] font-semibold text-gray-400 border-l border-gray-200 pl-2">
                위례 주말 키즈 큐레이션
              </span>
            </div>
          </div>

          <div className="flex items-center gap-2">
            {/* Crawler Health Status */}
            <button
              onClick={() => setIsHealthOpen(true)}
              className={`flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-bold border transition ${
                isAllCrawlersOk
                  ? "bg-emerald-50 text-emerald-700 border-emerald-200 hover:bg-emerald-100"
                  : "bg-amber-50 text-amber-800 border-amber-300 hover:bg-amber-100"
              }`}
              title="공공기관 수집 연동 상태 보기"
            >
              <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
              <span className="hidden sm:inline">
                {IS_STATIC ? (stats?.generated_at ? `자동수집 ${stats.generated_at.slice(5, 16)}` : "자동 수집 정상") : "실시간 연동 정상"}
              </span>
            </button>

            {/* Booster Modal Trigger */}
            <button
              onClick={() => setIsBookmarkletOpen(true)}
              className="flex items-center gap-1 px-2.5 py-1 rounded-lg bg-amber-50 text-amber-900 border border-amber-200 text-xs font-bold hover:bg-amber-100 transition"
              title="수강신청 자동완성 부스터 안내"
            >
              <SparklesIcon className="w-3.5 h-3.5 text-amber-600" />
              <span>예약 부스터</span>
            </button>

            {/* Refresh Button */}
            <button
              onClick={handleManualRefresh}
              disabled={refreshing}
              title="도서관 정보 다시 수집"
              className="p-1.5 rounded-lg bg-gray-100 hover:bg-gray-200 text-gray-600 transition"
            >
              <RefreshIcon className={`w-3.5 h-3.5 ${refreshing ? "animate-spin" : ""}`} />
            </button>
          </div>
        </div>
      </header>

      {/* Main Container */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 py-4 sm:py-5 space-y-4">
        {/* Compact Integrated Filter Bar */}
        <div className="bg-white p-3.5 sm:p-4 rounded-2xl border border-gray-200 shadow-sm space-y-3">
          {/* Row 1: Key Filters (Region, Day, Age, Status, NEW Toggle, Search) */}
          <div className="flex flex-wrap items-center justify-between gap-2.5">
            <div className="flex flex-wrap items-center gap-2">
              {/* Region Segment */}
              <div className="flex items-center bg-gray-100 p-0.5 rounded-xl border border-gray-200/80 text-xs">
                {[
                  { key: "ALL", label: "🏢 전체" },
                  { key: "송파", label: "📍 송파" },
                  { key: "성남", label: "📍 성남" },
                  { key: "하남", label: "📍 하남" },
                ].map((r) => (
                  <button
                    key={r.key}
                    type="button"
                    onClick={() => {
                      setSelectedRegion(r.key);
                      setSelectedLibrary("ALL");
                    }}
                    className={`px-2.5 py-1 rounded-lg font-black transition ${
                      selectedRegion === r.key
                        ? "bg-white text-gray-900 shadow-xs"
                        : "text-gray-600 hover:text-gray-900"
                    }`}
                  >
                    {r.label}
                  </button>
                ))}
              </div>

              {/* Day Type Toggle (All / Weekend / Weekday) - Default: WEEKEND */}
              <div className="flex items-center bg-gray-100 p-0.5 rounded-xl border border-gray-200/80 text-xs">
                {[
                  { key: "ALL", label: "전체" },
                  { key: "WEEKEND", label: "🎉 주말" },
                  { key: "WEEKDAY", label: "평일" },
                ].map((d) => (
                  <button
                    key={d.key}
                    type="button"
                    onClick={() => setSelectedDayType(d.key)}
                    className={`px-2.5 py-1 rounded-lg font-black transition ${
                      selectedDayType === d.key
                        ? "bg-blue-600 text-white shadow-xs"
                        : "text-gray-600 hover:text-gray-900"
                    }`}
                  >
                    {d.label}
                  </button>
                ))}
              </div>

              {/* Target Age Segment (All / Preschool / Elementary / Open) - Default: PRESCHOOL */}
              <div className="flex items-center bg-gray-100 p-0.5 rounded-xl border border-gray-200/80 text-xs">
                {[
                  { key: "ALL", label: "전체" },
                  { key: "PRESCHOOL", label: "🎈 유아(4~7세)" },
                  { key: "ELEMENTARY", label: "🎒 초등" },
                  { key: "OPEN", label: "🌟 누구나" },
                ].map((a) => (
                  <button
                    key={a.key}
                    type="button"
                    onClick={() => setSelectedAge(a.key)}
                    className={`px-2.5 py-1 rounded-lg font-black transition ${
                      selectedAge === a.key
                        ? "bg-rose-500 text-white shadow-xs"
                        : "text-gray-600 hover:text-gray-900"
                    }`}
                  >
                    {a.label}
                  </button>
                ))}
              </div>

              {/* Quick Status Toggle (접수중만 보기) */}
              <button
                type="button"
                onClick={() => setSelectedStatus((prev) => (prev === "APPLY" ? "ALL" : "APPLY"))}
                className={`px-2.5 py-1.5 rounded-xl text-xs font-black transition border flex items-center gap-1 ${
                  selectedStatus === "APPLY"
                    ? "bg-emerald-600 text-white border-emerald-600 shadow-xs"
                    : "bg-white text-emerald-800 border-emerald-200 hover:bg-emerald-50"
                }`}
              >
                <span>⚡ 접수중만</span>
              </button>

              {/* Quick NEW Toggle (2일 신규) */}
              <button
                type="button"
                onClick={() => setOnlyNew((prev) => !prev)}
                className={`px-2.5 py-1.5 rounded-xl text-xs font-black transition border flex items-center gap-1 ${
                  onlyNew
                    ? "bg-violet-600 text-white border-violet-600 shadow-xs"
                    : "bg-white text-violet-800 border-violet-200 hover:bg-violet-50"
                }`}
              >
                <span>✨ 2일 신규</span>
                {newProgramsCount > 0 && (
                  <span className={`text-[10px] px-1 rounded ${onlyNew ? "bg-violet-700 text-white" : "bg-violet-100 text-violet-800"}`}>
                    {newProgramsCount}
                  </span>
                )}
              </button>
            </div>

            {/* Keyword Search */}
            <div className="relative w-full sm:w-48 lg:w-56">
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="도서관명, 강좌명 검색"
                className="w-full pl-8 pr-7 py-1.5 rounded-xl border border-gray-200 text-xs font-medium focus:outline-none focus:ring-1 focus:ring-blue-500 bg-gray-50 focus:bg-white"
              />
              <SearchIcon className="w-3.5 h-3.5 text-gray-400 absolute left-2.5 top-2.5" />
              {searchQuery && (
                <button
                  onClick={() => setSearchQuery("")}
                  className="absolute right-2.5 top-2 text-xs text-gray-400 hover:text-gray-600 font-bold"
                >
                  ✕
                </button>
              )}
            </div>
          </div>

          {/* Row 2: Institution (Library/Facility) Chips (No scrollbar, natural flex-wrap) */}
          <div className="pt-2 border-t border-gray-100 flex flex-wrap items-center gap-1.5 text-xs">
            <span className="text-[11px] font-bold text-gray-400 shrink-0">기관:</span>
            <button
              type="button"
              onClick={() => setSelectedLibrary("ALL")}
              className={`px-2.5 py-1 rounded-lg text-xs font-black transition ${
                selectedLibrary === "ALL"
                  ? "bg-gray-900 text-white shadow-xs"
                  : "bg-gray-100 text-gray-600 hover:bg-gray-200"
              }`}
            >
              전체 기관
            </button>
            {availableLibraries.map((lib) => (
              <button
                key={lib.name}
                type="button"
                onClick={() => setSelectedLibrary(lib.name)}
                title={lib.name}
                className={`px-2.5 py-1 rounded-lg text-xs font-black transition flex items-center gap-1 ${
                  selectedLibrary === lib.name
                    ? "bg-blue-600 text-white shadow-xs"
                    : "bg-gray-100 text-gray-700 hover:bg-blue-50 hover:text-blue-700"
                }`}
              >
                <span>{shortenLibraryName(lib.name)}</span>
                <span
                  className={`text-[10px] px-1 rounded ${
                    selectedLibrary === lib.name ? "bg-blue-700 text-white" : "bg-white text-gray-500"
                  }`}
                >
                  {lib.count}
                </span>
              </button>
            ))}

            {/* Reset Filters button if any active */}
            {(onlyNew || selectedDayType !== "WEEKEND" || selectedAge !== "PRESCHOOL" || selectedRegion !== "ALL" || selectedLibrary !== "ALL" || selectedStatus !== "ALL" || searchQuery) && (
              <button
                onClick={() => {
                  setOnlyNew(false);
                  setSelectedDayType("WEEKEND");
                  setSelectedAge("PRESCHOOL");
                  setSelectedRegion("ALL");
                  setSelectedLibrary("ALL");
                  setSelectedStatus("ALL");
                  setSearchQuery("");
                }}
                className="text-[11px] text-gray-400 hover:text-gray-700 underline font-semibold ml-auto"
              >
                필터 초기화
              </button>
            )}
          </div>
        </div>

        {/* Results Header: Perfectly Aligned SaaS Toolbar */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2.5 px-1 pt-1">
          {/* Left: Program Count */}
          <div className="flex items-center justify-between sm:justify-start gap-3">
            <div className="text-xs sm:text-sm font-black text-gray-900 whitespace-nowrap">
              {includeExpired ? "전체 (마감포함)" : "신청 가능"}{" "}
              <span className="text-blue-600 font-black">{filteredPrograms.length}</span>개
            </div>

            {/* Expired Toggle on mobile: positioned next to count for clean balance */}
            <label className="sm:hidden whitespace-nowrap flex items-center gap-1.5 cursor-pointer text-xs font-semibold text-gray-500 hover:text-gray-800 transition">
              <input
                type="checkbox"
                checked={includeExpired}
                onChange={(e) => setIncludeExpired(e.target.checked)}
                className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
              />
              <span>
                마감 포함
                {stats?.expired_count ? ` (${stats.expired_count})` : ""}
              </span>
            </label>
          </div>

          {/* Right: Controls Group (Sort + View Mode + Expired) - Aligned in one clean line */}
          <div className="flex items-center justify-between sm:justify-end gap-2 sm:gap-2.5 flex-wrap sm:flex-nowrap">
            {/* Quick Sort Segment */}
            <div className="flex items-center bg-gray-100 p-0.5 rounded-xl border border-gray-200/80 text-xs shrink-0">
              <button
                type="button"
                onClick={() => setSortBy("default")}
                className={`whitespace-nowrap px-2 sm:px-2.5 py-1 rounded-lg font-black transition ${
                  sortBy === "default"
                    ? "bg-white text-gray-900 shadow-xs"
                    : "text-gray-600 hover:text-gray-900"
                }`}
                title="추천 정렬"
              >
                ⚡ 추천순
              </button>
              <button
                type="button"
                onClick={() => handleSortChange("event_date")}
                className={`whitespace-nowrap flex items-center gap-0.5 px-2 sm:px-2.5 py-1 rounded-lg font-black transition ${
                  sortBy === "event_date"
                    ? "bg-blue-600 text-white shadow-xs"
                    : "text-gray-600 hover:text-gray-900"
                }`}
                title="행사일 기준 정렬"
              >
                <span>📅 행사일</span>
                {sortBy === "event_date" && (
                  sortOrder === "asc" ? <SortAscIcon className="w-3 h-3 text-white" /> : <SortDescIcon className="w-3 h-3 text-white" />
                )}
              </button>
              <button
                type="button"
                onClick={() => handleSortChange("apply_date")}
                className={`whitespace-nowrap flex items-center gap-0.5 px-2 sm:px-2.5 py-1 rounded-lg font-black transition ${
                  sortBy === "apply_date"
                    ? "bg-amber-500 text-white shadow-xs"
                    : "text-gray-600 hover:text-gray-900"
                }`}
                title="접수일 기준 정렬"
              >
                <span>⏰ 접수일</span>
                {sortBy === "apply_date" && (
                  sortOrder === "asc" ? <SortAscIcon className="w-3 h-3 text-white" /> : <SortDescIcon className="w-3 h-3 text-white" />
                )}
              </button>
            </div>

            {/* View Mode Toggle (Card vs List) */}
            <div className="flex items-center bg-gray-100 p-0.5 rounded-xl border border-gray-200/80 text-xs shrink-0">
              <button
                type="button"
                onClick={() => handleChangeViewMode("card")}
                title="카드형으로 보기"
                className={`whitespace-nowrap flex items-center gap-1 px-2.5 py-1 rounded-lg font-black transition ${
                  viewMode === "card"
                    ? "bg-white text-gray-900 shadow-xs"
                    : "text-gray-500 hover:text-gray-900"
                }`}
              >
                <GridIcon className="w-3.5 h-3.5" />
                <span>카드</span>
              </button>
              <button
                type="button"
                onClick={() => handleChangeViewMode("list")}
                title="목록형으로 보기"
                className={`whitespace-nowrap flex items-center gap-1 px-2.5 py-1 rounded-lg font-black transition ${
                  viewMode === "list"
                    ? "bg-white text-blue-700 shadow-xs"
                    : "text-gray-500 hover:text-gray-900"
                }`}
              >
                <ListIcon className="w-3.5 h-3.5" />
                <span>목록</span>
              </button>
            </div>

            {/* Expired Toggle on desktop */}
            <label className="hidden sm:flex whitespace-nowrap items-center gap-1.5 cursor-pointer text-xs font-semibold text-gray-500 hover:text-gray-800 transition shrink-0 pl-1">
              <input
                type="checkbox"
                checked={includeExpired}
                onChange={(e) => setIncludeExpired(e.target.checked)}
                className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
              />
              <span>
                마감 포함
                {stats?.expired_count ? ` (${stats.expired_count})` : ""}
              </span>
            </label>
          </div>
        </div>

        {/* Program Cards or Compact List View */}
        {loading ? (
          <div className="py-24 text-center">
            <RefreshIcon className="w-8 h-8 text-blue-500 animate-spin mx-auto mb-3" />
            <p className="text-sm font-bold text-gray-600">
              최신 활성 프로그램을 불러오는 중입니다...
            </p>
          </div>
        ) : filteredPrograms.length > 0 ? (
          viewMode === "card" ? (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
              {filteredPrograms.map((program) => (
                <ProgramCard key={program.id} program={program} />
              ))}
            </div>
          ) : (
            <ProgramListView
              programs={filteredPrograms}
              sortBy={sortBy}
              sortOrder={sortOrder}
              onSortChange={handleSortChange}
            />
          )
        ) : (
          <div className="py-20 text-center bg-white rounded-3xl border border-dashed border-gray-300 p-8">
            <div className="w-12 h-12 rounded-2xl bg-blue-50 text-blue-500 flex items-center justify-center mx-auto mb-3">
              <CalendarIcon className="w-6 h-6" />
            </div>
            <h3 className="text-base font-bold text-gray-800">
              현재 신청 가능한{" "}
              {selectedDayType === "WEEKEND" ? "주말 " : selectedDayType === "WEEKDAY" ? "평일 " : ""}
              {selectedAge === "PRESCHOOL"
                ? "유아(누구나 포함) "
                : selectedAge === "ELEMENTARY"
                ? "초등(누구나 포함) "
                : selectedAge === "OPEN"
                ? "누구나 참여 가능한 "
                : ""}
              프로그램이 없습니다.
            </h3>
            <p className="text-xs text-gray-500 mt-1 max-w-sm mx-auto">
              [전체 일정 보기]를 눌러 평일 프로그램까지 확인하시거나 다른 연령대를 선택해 보세요.
            </p>
            <div className="mt-4 flex items-center justify-center gap-2">
              <button
                onClick={() => setSelectedDayType("ALL")}
                className="px-4 py-2 rounded-xl bg-blue-600 text-white text-xs font-bold hover:bg-blue-700 transition"
              >
                전체 일정 보기 (주말 + 평일)
              </button>
              <button
                onClick={() => {
                  setSelectedDayType("ALL");
                  setSelectedAge("ALL");
                  setSelectedRegion("ALL");
                  setSelectedLibrary("ALL");
                  setSelectedStatus("ALL");
                  setSearchQuery("");
                  setOnlyNew(false);
                }}
                className="px-4 py-2 rounded-xl bg-gray-100 text-gray-700 text-xs font-semibold hover:bg-gray-200 transition"
              >
                필터 전체 초기화
              </button>
            </div>
          </div>
        )}
      </main>

      {/* Modals */}
      <BookmarkletModal
        isOpen={isBookmarkletOpen}
        onClose={() => setIsBookmarkletOpen(false)}
      />
      <CrawlerHealthModal
        isOpen={isHealthOpen}
        onClose={() => setIsHealthOpen(false)}
        logs={stats?.crawler_logs || []}
        onRefresh={handleManualRefresh}
        isRefreshing={refreshing}
        isStaticMode={IS_STATIC}
        generatedAt={stats?.generated_at}
      />
    </div>
  );
}
