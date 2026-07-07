import { cn } from "@/lib/utils";

export function Card({ className, children }: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <section
      className={cn(
        "rounded-lg border border-border bg-surface p-4 shadow-glow backdrop-blur-xl",
        className
      )}
    >
      {children}
    </section>
  );
}
