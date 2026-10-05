import styles from "./page.module.css";

export default function Loading() {
  return (
    <div className={styles.page}>
      <header className={styles.appHeader}>
        <div className={styles.headerInner}>
          <span className={styles.brandMark} aria-hidden="true" />
          <span className={styles.brand}>Gestão de contatos</span>
        </div>
      </header>
      <main className={styles.content} aria-busy="true" aria-live="polite">
        <div className={styles.titleBlock}>
          <p className={styles.eyebrow}>Visão geral</p>
          <h1>Contatos</h1>
        </div>
        <div className={styles.listSection}>
          <div className={styles.loadingTable}>
            <p className={styles.loadingLabel}>Carregando contatos...</p>
            {Array.from({ length: 5 }, (_, index) => (
              <div className={styles.skeletonRow} key={index} />
            ))}
          </div>
        </div>
      </main>
    </div>
  );
}
