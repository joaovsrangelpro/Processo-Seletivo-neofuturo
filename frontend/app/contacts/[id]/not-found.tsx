import Link from "next/link";
import shell from "../../page.module.css";

export default function ContactNotFound() {
  return (
    <div className={shell.page}>
      <header className={shell.appHeader}>
        <div className={shell.headerInner}>
          <span className={shell.brandMark} aria-hidden="true" />
          <span className={shell.brand}>Gestão de contatos</span>
        </div>
      </header>
      <main className={shell.content}>
        <h1>Contato não encontrado.</h1>
        <div className={shell.detailSection}>
          <Link className={shell.backLink} href="/">Voltar para contatos</Link>
        </div>
      </main>
    </div>
  );
}
