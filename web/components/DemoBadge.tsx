export function DemoBadge({ text }: { text: string }) {
  return (
    <span className="rounded-full border border-dashed border-accent px-3.5 py-1.5 text-xs font-semibold whitespace-nowrap text-accent">
      {text}
    </span>
  );
}
