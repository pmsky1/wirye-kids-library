"use client";

import React from "react";
import { CheckCircleIcon, AlertCircleIcon, RefreshIcon } from "./Icons";

interface CrawlerLog {
  source: string;
  library_name: string;
  last_attempt_at: string;
  last_success_at: string | null;
  status: string;
  item_count: number;
  error_message: string | null;
}

interface CrawlerHealthModalProps {
  isOpen: boolean;
  onClose: () => void;
  logs: CrawlerLog[];
  onRefresh: () => void;
  isRefreshing: boolean;
  isStaticMode?: boolean;
  generatedAt?: string;
}

export default function CrawlerHealthModal({
  isOpen,
  onClose,
  logs,
  onRefresh,
  isRefreshing,
  isStaticMode = false,
  generatedAt
}: CrawlerHealthModalProps) {
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm animate-fade-in">
      <div className="bg-white text-gray-900 rounded-3xl max-w-xl w-full p-6 sm:p-8 shadow-2xl border border-gray-100 max-h-[90vh] overflow-y-auto">
        <div className="flex items-center justify-between pb-4 border-b border-gray-100">
          <div>
            <h2 className="text-xl font-bold tracking-tight">도서관별 수집 연동 상태</h2>
            <p className="text-xs text-gray-500">
              {isStaticMode
                ? `GitHub Actions 자동 수집 기준${generatedAt ? ` (${generatedAt})` : ""}`
                : "지자체 도서관 사이트 개편 및 수집 모니터링 현황"}
            </p>
          </div>
          <button
            onClick={onClose}
            className="w-8 h-8 rounded-full bg-gray-100 hover:bg-gray-200 text-gray-500 flex items-center justify-center transition"
          >
            ✕
          </button>
        </div>

        <div className="mt-6 space-y-3">
          {logs && logs.length > 0 ? (
            logs.map((log) => {
              const isOk = log.status === "OK";
              const isWarning = log.status === "WARNING";
              const isSchema = log.status === "SCHEMA_MISMATCH";

              return (
                <div
                  key={log.source}
                  className={`p-4 rounded-2xl border transition ${
                    isOk
                      ? "bg-emerald-50/40 border-emerald-200"
                      : isSchema
                      ? "bg-amber-50 border-amber-300"
                      : "bg-red-50 border-red-200"
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2.5">
                      {isOk ? (
                        <div className="w-8 h-8 rounded-xl bg-emerald-100 text-emerald-600 flex items-center justify-center">
                          <CheckCircleIcon className="w-5 h-5" />
                        </div>
                      ) : (
                        <div className="w-8 h-8 rounded-xl bg-amber-100 text-amber-600 flex items-center justify-center">
                          <AlertCircleIcon className="w-5 h-5" />
                        </div>
                      )}
                      <div>
                        <h4 className="text-sm font-bold text-gray-900">{log.library_name}</h4>
                        <p className="text-[11px] text-gray-500">코드: {log.source}</p>
                      </div>
                    </div>
                    <span
                      className={`px-2.5 py-1 rounded-full text-xs font-bold ${
                        isOk
                          ? "bg-emerald-100 text-emerald-700"
                          : isSchema
                          ? "bg-amber-100 text-amber-700"
                          : "bg-red-100 text-red-700"
                      }`}
                    >
                      {isOk ? "정상 연동" : isSchema ? "구조 변경 감지" : "점검 필요"}
                    </span>
                  </div>

                  <div className="mt-3 pt-3 border-t border-gray-100 grid grid-cols-2 gap-2 text-xs text-gray-600">
                    <div>
                      <span className="text-gray-400">수집된 강좌: </span>
                      <span className="font-semibold text-gray-800">{log.item_count}개</span>
                    </div>
                    <div>
                      <span className="text-gray-400">최근 성공: </span>
                      <span className="font-semibold text-gray-800">{log.last_success_at || "기록 없음"}</span>
                    </div>
                  </div>

                  {log.error_message && (
                    <div className="mt-2 text-xs text-amber-800 bg-amber-100/60 p-2.5 rounded-xl font-medium">
                      ⚠️ {log.error_message}
                    </div>
                  )}
                </div>
              );
            })
          ) : (
            <div className="text-center py-8 text-gray-400 text-sm">연동 로그가 없습니다.</div>
          )}
        </div>

        <div className="mt-6 p-4 rounded-2xl bg-gray-50 text-xs text-gray-600 space-y-1">
          <p className="font-bold text-gray-800">🛡️ 사이트 개편 대비 예외처리 원칙</p>
          <p>1. 특정 도서관 사이트 개편 시에도 나머지 도서관 크롤러는 멈추지 않고 독립 작동합니다.</p>
          <p>2. 새로운 수집이 실패해도 기존에 저장된 데이터는 삭제되지 않고 안전하게 보존됩니다.</p>
          <p>3. 구조 변경이 감지되면 상단 상태 뱃지에 즉시 경고가 표시됩니다.</p>
        </div>

        <div className="mt-6 flex items-center justify-between">
          <button
            onClick={onRefresh}
            disabled={isRefreshing}
            className="flex items-center gap-2 px-4 py-2.5 rounded-xl bg-gray-100 hover:bg-gray-200 text-gray-700 text-xs font-semibold transition"
          >
            <RefreshIcon className={`w-4 h-4 ${isRefreshing ? "animate-spin" : ""}`} />
            {isStaticMode
              ? isRefreshing
                ? "데이터 다시 읽는 중..."
                : "최신 배포 데이터 다시 읽기"
              : isRefreshing
              ? "수집 진행 중..."
              : "지금 다시 수집하기"}
          </button>
          <button
            onClick={onClose}
            className="px-5 py-2.5 rounded-xl bg-gray-900 hover:bg-black text-white text-xs font-semibold transition"
          >
            닫기
          </button>
        </div>
      </div>
    </div>
  );
}
