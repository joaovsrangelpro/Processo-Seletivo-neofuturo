import Link from "next/link";

import { ImportForm } from "./import-form";
import shell from "../page.module.css";
import detail from "../contacts/[id]/detail.module.css";

export default function ImportPage() {
  return (
    <div className={shell.page}>
      <header className={shell.appHeader}>
        <div className={shell.headerInner}>
          <span className={shell.brandMark} aria-hidden="true" />
          <span className={shell.brand}>Gestão de contatos</span>
        </div>
      </header>
      <main className={shell.content}>
        <nav className={detail.backNav} aria-label="Navegação da importação">
          <Link className={shell.backLink} href="/">
            <span aria-hidden="true">← </span>Voltar para contatos
          </Link>
        </nav>
        <div className={shell.titleRow}>
          <div className={shell.titleBlock}>
            <p className={shell.eyebrow}>Importação em lote</p>
            <h1>Importar contatos</h1>
          </div>
        </div>
        <ImportForm />
      </main>
    </div>
  );
}
