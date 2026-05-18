"use client";
import type { DaySnapshot } from "@/lib/types";

export function Timeline({
  snapshots,
  currentDay,
  onSelect,
}: {
  snapshots: DaySnapshot[];
  currentDay: number;
  onSelect: (day: number) => void;
}) {
  return (
    <div className="panel p-3">
      <div className="text-xs text-muted mb-2">Day-by-day timeline</div>
      <div className="flex gap-1 flex-wrap">
        {snapshots.map((s) => (
          <button
            key={s.day}
            onClick={() => onSelect(s.day)}
            className={
              "px-2 py-1 rounded text-xs " +
              (s.day === currentDay
                ? "bg-blue-600 text-white"
                : "bg-line text-muted hover:bg-[#2a323d]")
            }
            title={s.highlights[0]?.summary || ""}
          >
            D{s.day}
          </button>
        ))}
      </div>
    </div>
  );
}
