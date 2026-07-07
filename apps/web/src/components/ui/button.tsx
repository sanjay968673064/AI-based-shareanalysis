import { cn } from "@/lib/utils";

type ButtonProps = React.ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "primary" | "ghost";
};

export function Button({ className, variant = "primary", ...props }: ButtonProps) {
  return (
    <button
      className={cn(
        "inline-flex h-10 items-center justify-center gap-2 rounded-md px-3 text-sm font-medium transition focus:outline-none focus:ring-2 focus:ring-accent/50",
        variant === "primary" && "bg-accent text-black hover:bg-accent/90",
        variant === "ghost" && "border border-border bg-white/5 text-foreground hover:bg-white/10",
        className
      )}
      {...props}
    />
  );
}
