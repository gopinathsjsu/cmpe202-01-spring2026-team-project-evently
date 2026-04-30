"use client";

import { useRef, useState } from "react";

import { ApiError, apiFetch } from "@/lib/api";

type EventImageResponse = {
  event_id: number;
  image_url: string;
};

type Props = {
  eventId: number;
  className?: string;
  label?: string;
  onUploaded?: (imageUrl: string) => void;
};

function errorMessage(err: unknown): string {
  if (err instanceof ApiError) {
    return typeof err.detail === "string"
      ? err.detail
      : JSON.stringify(err.detail);
  }
  return err instanceof Error ? err.message : "Failed to update image.";
}

export function EventImageUploadButton({
  eventId,
  className,
  label = "Change Image",
  onUploaded,
}: Props) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;

    setUploading(true);
    setError(null);
    try {
      const form = new FormData();
      form.append("file", file);
      const response = await apiFetch<EventImageResponse>(`/events/${eventId}/image`, {
        method: "POST",
        body: form,
      });
      onUploaded?.(response.image_url);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setUploading(false);
      if (inputRef.current) {
        inputRef.current.value = "";
      }
    }
  }

  return (
    <div className="space-y-1">
      <label
        className={
          className ??
          "inline-flex cursor-pointer items-center justify-center rounded-md border border-gray-300 bg-white px-3 py-2 text-xs font-medium text-gray-700 transition hover:bg-gray-50"
        }
      >
        <input
          ref={inputRef}
          type="file"
          accept="image/jpeg,image/png,image/gif"
          className="hidden"
          disabled={uploading}
          onChange={handleChange}
        />
        {uploading ? "Uploading..." : label}
      </label>
      {error && <p className="text-xs text-red-600">{error}</p>}
    </div>
  );
}
