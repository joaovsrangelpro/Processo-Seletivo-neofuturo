"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { useTransition } from "react";

import type { Tag } from "@/lib/types";
import styles from "../page.module.css";

interface TagFilterProps {
  tags: Tag[];
  selectedTag?: string;
}

export function TagFilter({ tags, selectedTag = "" }: TagFilterProps) {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [isPending, startTransition] = useTransition();

  function updateTag(tag: string) {
    const params = new URLSearchParams(searchParams.toString());
    params.delete("page");

    if (tag) {
      params.set("tag", tag);
    } else {
      params.delete("tag");
    }

    const query = params.toString();
    startTransition(() => router.push(query ? `/?${query}` : "/"));
  }

  return (
    <label className={styles.filterField}>
      <span>Filtrar por tag</span>
      <select
        value={selectedTag}
        onChange={(event) => updateTag(event.target.value)}
        disabled={isPending}
      >
        <option value="">Todas as tags</option>
        {tags.map((tag) => (
          <option key={tag.id} value={tag.name}>
            {tag.name}
          </option>
        ))}
      </select>
    </label>
  );
}
