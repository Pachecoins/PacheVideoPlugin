import { redirect } from "next/navigation";

export default function ProPage() {
  // Pro is now granted by Mercado Pago's verified subscription status.
  // Keep old links useful without exposing a public demo entitlement.
  redirect("/app#planes");
}
