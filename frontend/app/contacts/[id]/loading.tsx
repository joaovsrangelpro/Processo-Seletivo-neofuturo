import shell from "../../page.module.css";

export default function LoadingContact() {
  return (
    <div className={shell.page}>
      <header className={shell.appHeader}>
        <div className={shell.headerInner}>
          <span className={shell.brandMark} aria-hidden="true" />
          <span className={shell.brand}>Gestão de contatos</span>
        </div>
      </header>
      <main className={shell.content} aria-busy="true" aria-live="polite">
        <p className={shell.loadingLabel}>Carregando contato...</p>
        <div className={shell.loadingTable} aria-hidden="true">
          <div className={shell.skeletonRow} />
          <div className={shell.skeletonRow} />
          <div className={shell.skeletonRow} />
        </div>
      </main>
    </div>
  );
}
