import { Fragment, type ReactNode } from "react";

// troca cada {nome} do texto pelo valor; o valor pode ser um elemento (um número em negrito, por exemplo)
export function fill(template: string, values: Record<string, ReactNode>): ReactNode {
  return template.split(/\{(\w+)\}/).map((part, i) =>
    i % 2 === 1 ? <Fragment key={i}>{values[part] ?? `{${part}}`}</Fragment> : part,
  );
}

// a mesma troca, para quando o resultado precisa ser texto (atributo title, por exemplo)
export function fillText(template: string, values: Record<string, string | number>): string {
  return template.replace(/\{(\w+)\}/g, (_, key: string) => String(values[key] ?? `{${key}}`));
}
