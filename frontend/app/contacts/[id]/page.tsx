import Link from "next/link";

import styles from "../../page.module.css";

interface ContactPlaceholderProps {
  params: Promise<{ id: string }>;
}

export default async function ContactPlaceholder({
  params,
}: ContactPlaceholderProps) {
  const { id } = await params;

  return (
    <div className={styles.page}>
      <header className={styles.appHeader}>
        <div className={styles.headerInner}>
          <span className={styles.brandMark} aria-hidden="true" />
          <span className={styles.brand}>Gestão de contatos</span>
        </div>
      </header>
      <main className={styles.content}>
        <div className={styles.titleBlock}>
          <p className={styles.eyebrow}>Contato #{id}</p>
          <h1>Detalhes do contato</h1>
        </div>
        <nav className={styles.detailSection} aria-label="Navegação do contato">
          <Link className={styles.backLink} href="/">
            Voltar para contatos
          </Link>
        </nav>
      </main>
    </div>
  );
}
