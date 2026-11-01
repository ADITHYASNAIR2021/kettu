"use client";

import { useEffect, useMemo } from "react";

/** A blob: URL for an audio Blob, revoked when the blob changes or the component unmounts. */
export function useObjectUrl(blob: Blob | null): string | null {
  const url = useMemo(() => (blob ? URL.createObjectURL(blob) : null), [blob]);
  useEffect(() => () => {
    if (url) URL.revokeObjectURL(url);
  }, [url]);
  return url;
}
