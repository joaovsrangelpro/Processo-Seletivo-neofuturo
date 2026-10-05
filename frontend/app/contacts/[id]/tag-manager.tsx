import type { Tag } from "@/lib/types";
import styles from "./detail.module.css";

interface TagManagerProps {
  contactId: number;
  initialTags: Tag[];
  availableTags: Tag[] | null;
}

export function TagManager({ initialTags, availableTags }: TagManagerProps) {
  return (
    <section className={styles.section} aria-labelledby="tags-title">
      <h2 id="tags-title">Tags</h2>
      {initialTags.length ? (
        <ul className={styles.tagList}>
          {initialTags.map(tag => (
            <li className={styles.tag} key={tag.id}>
              <span className={styles.tagName}>{tag.name}</span>
            </li>
          ))}
        </ul>
      ) : (
        <p className={styles.muted}>Nenhuma tag associada.</p>
      )}
      {availableTags === null && (
        <p className={styles.muted}>Não foi possível carregar as tags disponíveis.</p>
      )}
    </section>
  );
}
