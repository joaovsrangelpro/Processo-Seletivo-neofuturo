"use client";

import { useRef, useState, type FormEvent } from "react";

import { addTagToContact, ApiError, removeTagFromContact } from "@/lib/api";
import type { Tag } from "@/lib/types";
import styles from "./detail.module.css";

interface TagManagerProps {
  contactId: number;
  initialTags: Tag[];
  availableTags: Tag[] | null;
}

export function TagManager({ contactId, initialTags, availableTags }: TagManagerProps) {
  const [tags, setTags] = useState(initialTags);
  const [selectedTag, setSelectedTag] = useState("");
  const [pending, setPending] = useState<number | "add" | null>(null);
  const [error, setError] = useState<string | null>(null);
  const inFlight = useRef(false);
  const options = availableTags?.filter(tag => !tags.some(item => item.id === tag.id)) ?? [];

  async function addTag(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const tagId = Number(selectedTag);
    if (inFlight.current || !options.some(tag => tag.id === tagId)) return;

    inFlight.current = true;
    setPending("add");
    setError(null);
    try {
      const association = await addTagToContact(contactId, tagId);
      setTags(current => [...current, {
        id: association.tag_id,
        name: association.tag_name,
      }].sort((left, right) => left.name.localeCompare(right.name, "pt-BR")));
      setSelectedTag("");
    } catch (error) {
      setError(error instanceof ApiError && error.status === 409
        ? "Esta tag já está associada ao contato."
        : "Não foi possível adicionar a tag. Tente novamente.");
    } finally {
      inFlight.current = false;
      setPending(null);
    }
  }

  async function removeTag(tagId: number) {
    if (inFlight.current) return;
    inFlight.current = true;
    setPending(tagId);
    setError(null);
    try {
      await removeTagFromContact(contactId, tagId);
      setTags(current => current.filter(tag => tag.id !== tagId));
    } catch {
      setError("Não foi possível remover a tag. Tente novamente.");
    } finally {
      inFlight.current = false;
      setPending(null);
    }
  }

  return (
    <section className={styles.section} aria-labelledby="tags-title">
      <h2 id="tags-title">Tags</h2>
      {tags.length ? (
        <ul className={styles.tagList}>
          {tags.map(tag => (
            <li className={styles.tag} key={tag.id}>
              <span className={styles.tagName}>{tag.name}</span>
              <button
                className={styles.tagRemove}
                type="button"
                aria-label={`Remover tag ${tag.name}`}
                title={`Remover tag ${tag.name}`}
                disabled={pending !== null}
                onClick={() => removeTag(tag.id)}
              >
                <span aria-hidden="true">{pending === tag.id ? "..." : "×"}</span>
              </button>
            </li>
          ))}
        </ul>
      ) : (
        <p className={styles.muted}>Nenhuma tag associada.</p>
      )}
      {availableTags === null ? (
        <p className={styles.error} role="alert">Não foi possível carregar as tags disponíveis.</p>
      ) : options.length ? (
        <form className={styles.controlRow} onSubmit={addTag} aria-busy={pending !== null}>
          <label className={styles.field}>
            <span>Tag existente</span>
            <select
              value={selectedTag}
              onChange={event => setSelectedTag(event.target.value)}
              disabled={pending !== null}
            >
              <option value="">Selecionar tag</option>
              {options.map(tag => <option key={tag.id} value={tag.id}>{tag.name}</option>)}
            </select>
          </label>
          <button className={styles.primaryButton} disabled={!selectedTag || pending !== null}>
            {pending === "add" ? "Adicionando..." : "Adicionar tag"}
          </button>
        </form>
      ) : (
        <p className={`${styles.muted} ${styles.actionSpacing}`}>
          {availableTags.length ? "Todas as tags já estão associadas." : "Nenhuma tag disponível."}
        </p>
      )}
      {pending !== null && <p className={styles.muted} role="status">Atualizando tags...</p>}
      {error && <p className={styles.error} role="alert">{error}</p>}
    </section>
  );
}
