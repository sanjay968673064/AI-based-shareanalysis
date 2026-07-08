import { Dashboard } from "@/components/dashboard";
import { AuthGate } from "@/lib/auth";

export default function Home() {
  return (
    <AuthGate>
      <Dashboard />
    </AuthGate>
  );
}
