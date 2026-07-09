"use client";

import { useRouter, useSearchParams } from "next/navigation";

const RADII = [25, 50, 100, 250];

export function SearchFilters() {
  const router = useRouter();
  const params = useSearchParams();

  function update(key: string, value: string) {
    const next = new URLSearchParams(params.toString());
    if (value) next.set(key, value);
    else next.delete(key);
    router.push(`/search?${next.toString()}`);
  }

  return (
    <div
      className="flex flex-wrap items-end gap-4 rounded-xl border border-slate-200 bg-white p-4"
      role="group"
      aria-label="Filter results"
    >
      <div>
        <label htmlFor="radius" className="mb-1 block text-xs font-medium text-slate-600">
          Radius (miles)
        </label>
        <select
          id="radius"
          value={params.get("radius") ?? "50"}
          onChange={(e) => update("radius", e.target.value)}
          className="rounded-md border border-slate-300 px-3 py-2 text-sm"
        >
          {RADII.map((r) => (
            <option key={r} value={r}>
              {r} mi
            </option>
          ))}
        </select>
      </div>
      <div>
        <label htmlFor="minStars" className="mb-1 block text-xs font-medium text-slate-600">
          Min. CMS stars
        </label>
        <select
          id="minStars"
          value={params.get("minStars") ?? "0"}
          onChange={(e) => update("minStars", e.target.value)}
          className="rounded-md border border-slate-300 px-3 py-2 text-sm"
        >
          <option value="0">Any</option>
          <option value="3">3+</option>
          <option value="4">4+</option>
          <option value="5">5 only</option>
        </select>
      </div>
      <div>
        <label htmlFor="insurance" className="mb-1 block text-xs font-medium text-slate-600">
          Pay with
        </label>
        <select
          id="insurance"
          value={params.get("insurance") ?? "cash"}
          onChange={(e) => update("insurance", e.target.value)}
          className="rounded-md border border-slate-300 px-3 py-2 text-sm"
        >
          <option value="cash">Cash / self-pay</option>
          <option value="ppo">Typical PPO (est.)</option>
          <option value="hdhp">High-deductible (est.)</option>
          <option value="uninsured">Uninsured (cash)</option>
        </select>
      </div>
      <div>
        <label htmlFor="sort" className="mb-1 block text-xs font-medium text-slate-600">
          Sort by
        </label>
        <select
          id="sort"
          value={params.get("sort") ?? "distance"}
          onChange={(e) => update("sort", e.target.value)}
          className="rounded-md border border-slate-300 px-3 py-2 text-sm"
        >
          <option value="distance">Distance</option>
          <option value="price">Lowest price</option>
          <option value="quality">Highest quality</option>
        </select>
      </div>
      <div>
        <label htmlFor="maxPrice" className="mb-1 block text-xs font-medium text-slate-600">
          Max est. price ($)
        </label>
        <input
          id="maxPrice"
          type="number"
          min={0}
          step={500}
          placeholder="No limit"
          defaultValue={params.get("maxPrice") ?? ""}
          onBlur={(e) => update("maxPrice", e.target.value)}
          className="w-28 rounded-md border border-slate-300 px-3 py-2 text-sm"
        />
      </div>
    </div>
  );
}