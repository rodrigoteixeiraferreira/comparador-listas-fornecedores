"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

type Item = { href: string; label: string; count?: number };

// as abas do painel; a da página aberta fica sublinhada na cor de destaque
export function NavLinks({ items }: { items: Item[] }) {
  const pathname = usePathname();
  return (
    <nav className="flex gap-7 text-[0.95rem]">
      {items.map((item, i) => {
        const active = i === 0 ? pathname === item.href : pathname.startsWith(item.href);
        return (
          <Link
            key={item.href}
            href={item.href}
            className={`-mb-px border-b-2 pb-3 transition-colors ${
              active ? "border-accent font-semibold text-ink" : "border-transparent text-ink-2 hover:text-ink"
            }`}
          >
            {item.label}
            {item.count !== undefined && <span className="ml-1.5 text-ink-3">({item.count})</span>}
          </Link>
        );
      })}
    </nav>
  );
}
